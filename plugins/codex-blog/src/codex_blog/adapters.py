from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .frontmatter import parse_frontmatter
from .models import BlogWriteRequest, MaterialItem, SEOContentPacket
from .utils import dedupe, safe_json_load, safe_read_text

ACCEPTED_MATERIAL_TYPES = {
    "seo-session-materials",
    "seo-project-summary",
    "seo-project-summary-scoped",
    "seo-project-summary-partial",
    "seo-project-summary-scoped-partial",
    "web3-seo-session-materials",
}

FACT_STATE_MAP = {
    "已验证事实": "verified",
    "工程结论": "engineering",
    "待验证假设": "hypothesis",
    "失败方案": "failed",
}


def _section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^###\s+{re.escape(heading)}\s*$\n(.*?)(?=^###\s+|\Z)", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _bullets(text: str) -> list[str]:
    return dedupe(
        [re.sub(r"^[-*+]\s+", "", line).strip() for line in text.splitlines() if re.match(r"^[-*+]\s+", line)]
    )


def load_content_brief(path: Path) -> SEOContentPacket:
    if path.suffix.lower() == ".json":
        value = safe_json_load(path)
        if not isinstance(value, dict):
            raise ValueError("SEO brief JSON must be an object")
        packet = SEOContentPacket.from_mapping(value)
    else:
        raw = safe_read_text(path, label="SEO brief")
        frontmatter, body = parse_frontmatter(raw)
        primary_match = re.search(r"^##\s+(?:Content Brief|Content Outline):\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
        h1_match = re.search(r"\*\*H1:\*\*\s*(.+)", body)
        slug_match = re.search(r"\*\*URL Slug:\*\*\s*(\S+)", body)
        count_match = re.search(r"\*\*Target Word Count:\*\*\s*~?([\d,]+)", body)
        outline_block = _section(body, "Winning Outline")
        if not outline_block and primary_match:
            outline_block = body[primary_match.end():]
        outline = [
            re.sub(r"^#{1,6}\s+", "", line).strip()
            for line in outline_block.splitlines()
            if re.match(r"^#{2,6}\s+", line)
        ]
        competitor_urls = re.findall(r"https?://[^\s|)>]+", _section(body, "Competitor Analysis"))
        packet = SEOContentPacket(
            topic=str(frontmatter.get("topic", "")) or (h1_match.group(1).strip() if h1_match else ""),
            primary_keyword=str(frontmatter.get("primary_keyword", "")) or (primary_match.group(1).strip() if primary_match else ""),
            secondary_keywords=dedupe(list(frontmatter.get("secondary_keywords", [])) if isinstance(frontmatter.get("secondary_keywords"), list) else []),
            search_intent=_section(body, "Search Intent"),
            outline=outline,
            content_gaps=_bullets(_section(body, "Content Gaps and Opportunities")),
            information_gain=_bullets(_section(body, "Unique Angle and Information Gain")) or ([ _section(body, "Unique Angle and Information Gain") ] if _section(body, "Unique Angle and Information Gain") else []),
            competitor_urls=competitor_urls,
            word_count=int(count_match.group(1).replace(",", "")) if count_match else None,
            provenance=[{"kind": "seo-brief", "source": path.name}],
        )
        if slug_match:
            packet.provenance.append({"kind": "suggested-slug", "source": slug_match.group(1)})
    if not packet.topic:
        packet.topic = packet.primary_keyword
    return packet


def _find_cluster_post(value: dict[str, Any], post_id: str | None) -> dict[str, Any]:
    if isinstance(value.get("cluster_context"), dict):
        result = dict(value["cluster_context"])
        result.setdefault("_cluster_node_id", str(result.get("id", result.get("role", "context"))))
        return result
    if post_id:
        for cluster_index, cluster in enumerate(value.get("clusters", [])):
            if not isinstance(cluster, dict):
                continue
            for post_index, post in enumerate(cluster.get("posts", [])):
                if not isinstance(post, dict):
                    continue
                synthetic_id = f"cluster-{cluster_index}-post-{post_index}"
                aliases = {
                    synthetic_id,
                    str(post.get("id", "")),
                    str(post.get("slug", "")),
                    str(post.get("url", "")),
                    str(post.get("title", "")),
                    str(post.get("keyword", "")),
                }
                if post_id in aliases:
                    result = dict(post)
                    result.setdefault("cluster_name", cluster.get("name", ""))
                    result.setdefault("cluster_index", cluster_index)
                    result.setdefault("post_index", post_index)
                    result.setdefault("role", "spoke")
                    result["_cluster_node_id"] = synthetic_id
                    return result
        pillar = value.get("pillar")
        pillar_aliases = {
            "pillar",
            str(pillar.get("id", "")) if isinstance(pillar, dict) else "",
            str(pillar.get("slug", "")) if isinstance(pillar, dict) else "",
            str(pillar.get("url", "")) if isinstance(pillar, dict) else "",
            str(pillar.get("title", "")) if isinstance(pillar, dict) else "",
            str(pillar.get("keyword", "")) if isinstance(pillar, dict) else "",
        }
        if isinstance(pillar, dict) and post_id in pillar_aliases:
            result = dict(pillar)
            result["role"] = "pillar"
            result["_cluster_node_id"] = "pillar"
            return result
        raise ValueError(f"cluster post not found: {post_id}")
    if isinstance(value.get("pillar"), dict):
        result = dict(value["pillar"])
        result["role"] = "pillar"
        result["_cluster_node_id"] = "pillar"
        return result
    result = dict(value)
    result.setdefault("_cluster_node_id", str(result.get("id", "context")))
    return result


def _cluster_aliases(value: dict[str, Any]) -> dict[str, tuple[str, str]]:
    aliases: dict[str, tuple[str, str]] = {}

    def register(node_id: str, node: dict[str, Any]) -> None:
        url = str(node.get("url", "")).strip()
        for alias in (
            node_id,
            node.get("id", ""),
            node.get("slug", ""),
            node.get("url", ""),
            node.get("title", ""),
            node.get("keyword", ""),
        ):
            clean = str(alias).strip()
            if clean:
                aliases[clean] = (node_id, url)

    pillar = value.get("pillar")
    if isinstance(pillar, dict):
        register("pillar", pillar)
    for cluster_index, cluster in enumerate(value.get("clusters", [])):
        if not isinstance(cluster, dict):
            continue
        for post_index, post in enumerate(cluster.get("posts", [])):
            if isinstance(post, dict):
                register(f"cluster-{cluster_index}-post-{post_index}", post)
    return aliases


def _cluster_links(value: dict[str, Any], post: dict[str, Any]) -> list[dict[str, str]]:
    selected_id = str(post.get("_cluster_node_id", ""))
    aliases = _cluster_aliases(value)
    links: list[dict[str, str]] = []
    candidates = [
        item for item in post.get("outgoing_links", []) if isinstance(item, dict)
    ]
    for item in value.get("links", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("from", "")).strip()
        source_id = aliases.get(source, (source, ""))[0]
        if source and source_id != selected_id:
            continue
        candidates.append(item)
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        url = str(item.get("url", "")).strip()
        if not url:
            target = str(item.get("to", "")).strip()
            url = aliases.get(target, ("", ""))[1]
            if not url and (target.startswith("/") or target.startswith(("http://", "https://"))):
                url = target
        if not url:
            continue
        normalized = {
            "url": url,
            "anchor": str(item.get("anchor", "")).strip(),
            "type": str(item.get("type", "recommended")).strip() or "recommended",
        }
        key = (normalized["url"], normalized["anchor"], normalized["type"])
        if key not in seen:
            seen.add(key)
            links.append(normalized)
    return links


def load_cluster_plan(path: Path, *, post_id: str | None = None) -> SEOContentPacket:
    value = safe_json_load(path)
    if not isinstance(value, dict):
        raise ValueError("cluster plan must be a JSON object")
    post = _find_cluster_post(value, post_id)
    node_id = str(post.pop("_cluster_node_id", "context"))
    keyword = str(post.get("primary_keyword", post.get("keyword", ""))).strip()
    title = str(post.get("title", keyword)).strip()
    pillar = value.get("pillar", {}) if isinstance(value.get("pillar"), dict) else {}
    context = dict(post)
    context.setdefault("post_id", node_id)
    context.setdefault("primary_keyword", keyword)
    context.setdefault("word_count_target", post.get("wordCount", post.get("word_count_target")))
    if context.get("role") == "spoke":
        context.setdefault("pillar_title", pillar.get("title", ""))
        context.setdefault("pillar_url", pillar.get("url", ""))
    internal_links = _cluster_links(value, {**post, "_cluster_node_id": node_id})
    context["outgoing_links"] = internal_links
    packet = SEOContentPacket(
        topic=title or keyword,
        primary_keyword=keyword,
        secondary_keywords=dedupe([str(item) for item in post.get("secondary_keywords", [])]),
        search_intent=str(post.get("intent", value.get("intent", ""))),
        template=str(post.get("template", "")),
        word_count=int(post.get("word_count_target", post.get("wordCount", 0)) or 0) or None,
        internal_links=internal_links,
        cluster_context=context,
        provenance=[{"kind": "codex-seo-cluster", "source": path.name}],
    )
    return packet


def _controlled_value(block: str, label: str) -> str:
    match = re.search(rf"^-\s*{re.escape(label)}：\s*`?([^`\n]+)`?\s*$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _material_sections(body: str) -> Iterable[tuple[str, str, str]]:
    pattern = re.compile(
        r"^(?:##\s+(M\d{3})｜|###\s+(T\d{3})｜)([^\n]+)\n(.*?)(?=^(?:##\s+M\d{3}｜|###\s+T\d{3}｜)|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(body):
        yield match.group(1) or match.group(2), match.group(3).strip(), match.group(4).strip()


def load_extract_materials(path: Path) -> SEOContentPacket:
    raw = safe_read_text(path, label="extract-seo-materials input")
    frontmatter, body = parse_frontmatter(raw)
    document_type = str(frontmatter.get("document_type", ""))
    if document_type not in ACCEPTED_MATERIAL_TYPES:
        raise ValueError(f"unsupported extract-seo-materials document_type: {document_type or 'missing'}")
    try:
        version = int(frontmatter.get("schema_version", 0))
    except (TypeError, ValueError):
        version = 0
    if version not in {1, 2}:
        raise ValueError(f"unsupported extract-seo-materials schema_version: {version}")
    if str(frontmatter.get("generated_by", "")) != "extract-seo-materials":
        raise ValueError("extract-seo-materials generated_by marker is missing or invalid")
    is_project_summary = document_type.startswith("seo-project-summary")
    if is_project_summary:
        coverage = str(frontmatter.get("coverage_status", ""))
        expected_coverage = "partial" if document_type.endswith("-partial") else "complete"
        if coverage != expected_coverage:
            raise ValueError(
                f"coverage_status must be {expected_coverage} for {document_type}"
            )
    materials: list[MaterialItem] = []
    search_questions: list[str] = []
    search_intents: list[str] = []
    for ref, title, block in _material_sections(body):
        current_product_state = _controlled_value(block, "当前产品状态")
        current_product_anchor = _controlled_value(block, "当前产品锚点")
        if is_project_summary:
            if current_product_state != "已实现并保留":
                raise ValueError(f"{ref} 当前产品状态 must be 已实现并保留")
            if not current_product_anchor:
                raise ValueError(f"{ref} 当前产品锚点 is required")
        states: list[str] = []
        for chinese, normalized in FACT_STATE_MAP.items():
            if f"[{chinese}]" in block or chinese in _controlled_value(block, "事实状态"):
                states.append(normalized)
        state = states[0] if states else "unknown"
        public_boundary = _controlled_value(block, "公开边界") or "发布前确认"
        maturity = _controlled_value(block, "内容成熟度") or "unknown"
        search_intent = _controlled_value(block, "搜索意图")
        if search_intent:
            search_intents.extend(
                item.strip()
                for item in re.split(r"[、|;；]", search_intent)
                if item.strip()
            )
        source_refs = re.findall(r"\[S\d{3}\]", block)
        controlled_questions = _controlled_value(block, "用户可能搜索")
        questions = _bullets(_section(block, "用户可能如何搜索"))
        if controlled_questions:
            questions.extend(
                item.strip()
                for item in re.split(r"[、;；]", controlled_questions)
                if item.strip()
            )
        search_questions.extend(questions)
        materials.append(
            MaterialItem(
                title=title,
                text=block,
                fact_state=state,  # type: ignore[arg-type]
                fact_states=states or ["unknown"],  # type: ignore[arg-type]
                source_refs=dedupe(source_refs or [ref]),
                public_boundary=public_boundary,
                maturity=maturity,
                contribution_types=dedupe(_controlled_value(block, "贡献类型").split("、")),
                search_intent=search_intent,
                search_queries=dedupe(questions),
                current_product_state=current_product_state,
                current_product_anchor=current_product_anchor,
            )
        )
    declared_count = frontmatter.get("topic_count" if is_project_summary else "material_count")
    declared_name = "topic_count" if is_project_summary else "material_count"
    if declared_count is None:
        raise ValueError(f"{declared_name} is required")
    if declared_count is not None and int(declared_count) != len(materials):
        raise ValueError(
            f"{declared_name} mismatch: declared {declared_count}, parsed {len(materials)}"
        )
    topic = str(frontmatter.get("topic_filter", ""))
    if not topic or topic == "none":
        topic = str(frontmatter.get("session_topic", ""))
    if not topic and len(materials) == 1:
        topic = materials[0].title
    return SEOContentPacket(
        topic=topic,
        search_intent="、".join(dedupe(search_intents)),
        materials=materials,
        sources=[
            {
                "kind": document_type,
                "path": path.name,
                "coverage_status": str(frontmatter.get("coverage_status", "session")),
                "document_type": document_type,
                "schema_version": str(version),
                "topic_filter": str(frontmatter.get("topic_filter", "")),
                "generated_at": str(frontmatter.get("generated_at", "")),
                "generated_by": "extract-seo-materials",
                "resolved_source_mode": str(
                    frontmatter.get("resolved_source_mode", "")
                ),
            }
        ],
        content_gaps=dedupe(
            [
                item
                for material in materials
                for item in _bullets(_section(material.text, "当前素材缺口"))
            ]
        ),
        information_gain=dedupe(
            search_questions
            + [
                item
                for material in materials
                for item in _bullets(_section(material.text, "推荐内容角度"))
            ]
        ),
        provenance=[
            {
                "kind": "extract-seo-materials",
                "source": path.name,
                "document_type": document_type,
                "schema_version": str(version),
                "coverage_status": str(
                    frontmatter.get("coverage_status", "session")
                ),
                "topic_filter": str(frontmatter.get("topic_filter", "")),
                "generated_at": str(frontmatter.get("generated_at", "")),
            }
        ],
    )


def load_site_context(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    site: dict[str, str] = {}
    brand: dict[str, str] = {}
    for name, destination in (("SITE.md", site), ("BRAND.md", brand), ("VOICE.md", brand), ("PERSONA.md", brand)):
        path = root / name
        if path.is_file() and not path.is_symlink():
            destination[name.lower().removesuffix(".md")] = safe_read_text(
                path, max_bytes=256 * 1024, label="site context"
            )
    return site, brand


def _merge_scalar(target: dict[str, Any], key: str, value: Any, source: str, conflicts: list[str]) -> None:
    if value is None or value == "" or value == 0 or value == []:
        return
    if target.get(key) not in {None, "", 0} and target[key] != value:
        conflicts.append(f"{key}: kept higher-priority value over {source}")
        return
    target[key] = value


def _merge_string_list(
    key: str,
    explicit: dict[str, Any],
    lower_values: list[str],
    conflicts: list[str],
) -> list[str]:
    selected = dedupe([str(item) for item in explicit.get(key, [])])
    lower = dedupe(lower_values)
    if selected:
        if lower and lower != selected:
            conflicts.append(f"{key}: kept explicit list over adapter values")
        return selected
    return lower


def _mapping_list(values: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for value in values or []:
        if isinstance(value, dict) and value not in result:
            result.append(dict(value))
    return result


def _merge_mapping_list(
    key: str,
    explicit: dict[str, Any],
    lower_values: list[dict[str, Any]],
    conflicts: list[str],
) -> list[dict[str, Any]]:
    selected = _mapping_list(explicit.get(key, []))
    lower = _mapping_list(lower_values)
    if selected:
        if lower and lower != selected:
            conflicts.append(f"{key}: kept explicit list over adapter values")
        return selected
    return lower


def normalize_request(
    *,
    explicit: dict[str, Any],
    brief: SEOContentPacket | None = None,
    cluster: SEOContentPacket | None = None,
    material_packets: list[SEOContentPacket] | None = None,
    site_context: dict[str, str] | None = None,
    brand_voice: dict[str, str] | None = None,
) -> BlogWriteRequest:
    conflicts: list[str] = []
    target: dict[str, Any] = {}
    packets = [packet for packet in [brief, cluster] if packet]
    material_packets = material_packets or []
    # Higher-priority explicit values are installed first. Lower-priority sources
    # may only fill gaps; conflicts are retained for the run report.
    for key in (
        "topic", "primary_keyword", "search_intent", "audience", "language", "template", "word_count", "image_mode"
    ):
        _merge_scalar(target, key, explicit.get(key), "explicit", conflicts)
    for packet in packets:
        source = packet.provenance[0].get("kind", "SEO packet") if packet.provenance else "SEO packet"
        for key in ("topic", "primary_keyword", "search_intent", "audience", "language", "template", "word_count"):
            _merge_scalar(target, key, getattr(packet, key), source, conflicts)
    for packet in material_packets:
        source = packet.provenance[0].get("kind", "materials") if packet.provenance else "materials"
        for key in ("topic", "primary_keyword", "search_intent", "audience", "language"):
            _merge_scalar(target, key, getattr(packet, key), source, conflicts)
    target["secondary_keywords"] = _merge_string_list(
        "secondary_keywords",
        explicit,
        [item for packet in packets for item in packet.secondary_keywords],
        conflicts,
    )
    target["outline"] = _merge_string_list(
        "outline",
        explicit,
        [item for packet in packets for item in packet.outline],
        conflicts,
    )
    target["content_gaps"] = _merge_string_list(
        "content_gaps",
        explicit,
        [item for packet in packets + material_packets for item in packet.content_gaps],
        conflicts,
    )
    target["information_gain"] = _merge_string_list(
        "information_gain",
        explicit,
        [item for packet in packets + material_packets for item in packet.information_gain],
        conflicts,
    )
    packet_materials = [
        item.to_dict() if hasattr(item, "to_dict") else {
            "title": item.title,
            "text": item.text,
            "fact_state": item.fact_state,
            "fact_states": item.fact_states,
            "source_refs": item.source_refs,
            "public_boundary": item.public_boundary,
            "maturity": item.maturity,
            "contribution_types": item.contribution_types,
        }
        for packet in material_packets
        for item in packet.materials
    ]
    target["materials"] = explicit.get("materials") or packet_materials
    if explicit.get("materials") and packet_materials:
        conflicts.append("materials: kept explicit list over adapter values")
    target["sources"] = _merge_mapping_list(
        "sources",
        explicit,
        [dict(item) for packet in packets + material_packets for item in packet.sources],
        conflicts,
    )
    target["internal_links"] = _merge_mapping_list(
        "internal_links",
        explicit,
        [dict(item) for packet in packets for item in packet.internal_links],
        conflicts,
    )
    target["competitor_urls"] = _merge_string_list(
        "competitor_urls",
        explicit,
        [item for packet in packets for item in packet.competitor_urls],
        conflicts,
    )
    lower_cluster = cluster.cluster_context if cluster else {}
    target["cluster_context"] = dict(explicit.get("cluster_context") or lower_cluster)
    if explicit.get("cluster_context") and lower_cluster != explicit["cluster_context"]:
        conflicts.append("cluster_context: kept explicit object over adapter value")
    target["site_context"] = dict(explicit.get("site_context") or site_context or {})
    target["brand_voice"] = dict(explicit.get("brand_voice") or brand_voice or {})
    target["preserved_image_references"] = dedupe(
        [str(item) for item in explicit.get("preserved_image_references", [])]
    )
    target["conflicts"] = conflicts
    target["provenance"] = _merge_mapping_list(
        "provenance",
        explicit,
        [dict(item) for packet in packets + material_packets for item in packet.provenance],
        conflicts,
    )
    request = BlogWriteRequest.from_mapping(target)
    if not request.topic:
        request.topic = request.primary_keyword
    if not request.primary_keyword:
        request.primary_keyword = request.topic
    if not request.topic:
        raise ValueError("topic or primary keyword is required")
    return request
