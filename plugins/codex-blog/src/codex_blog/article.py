from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .frontmatter import read_markdown
from .models import BlogWriteRequest
from .utils import atomic_write_json, atomic_write_text, dedupe

UNFINISHED = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\[INTERNAL-LINK(?:[: ][^\]]*)?\]", re.IGNORECASE),
    re.compile(r"\[(?:IMAGE|CHART|VIDEO)(?:[^\]]*)\]", re.IGNORECASE),
    re.compile(r"\[(?:ANSWER-FIRST|INFO-GAIN|STAT)(?:[^\]]*)\]", re.IGNORECASE),
    re.compile(r"\[EVIDENCE-BACKED[^\]]*\]", re.IGNORECASE),
    re.compile(r"\[INSERT\b[^\]]*\]", re.IGNORECASE),
)
VISUAL_MARKUP = (
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),
    re.compile(r"<\s*(?:img|svg|picture|video)\b", re.IGNORECASE),
)
URL = re.compile(r"https?://[^\s)>\]]+")
NUMERIC_CLAIM = re.compile(
    r"(?<![\w/])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|percent|million|billion|万|亿|倍)?",
    re.IGNORECASE,
)
CONCLUSION_HEADING = re.compile(
    r"^(?:conclusion|final thoughts|key takeaways|next steps|what to do next|"
    r"结论与下一步|结论与建议|总结与建议|总结与下一步|"
    r"结论|总结|小结|结语|行动建议|下一步|まとめ|結論|결론|마무리|"
    r"conclusi[oó]n|conclus[aã]o|conclusione|fazit|schluss|recommandations?|"
    r"итоги|заключение|выводы|следующие шаги|الخلاصة|الخاتمة|الخطوات التالية|"
    r"สรุป|บทสรุป|ขั้นตอนถัดไป|conclusie|samenvatting|volgende stappen)\b",
    re.IGNORECASE,
)
KNOWN_CONCLUSION_LANGUAGES = {
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "nl",
    "pt",
    "ru",
    "th",
    "zh",
}


@dataclass(slots=True)
class ArticleReview:
    complete: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    frontmatter: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "frontmatter": self.frontmatter,
        }


def _visible_words(text: str) -> list[str]:
    plain = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    plain = re.sub(r"`[^`]+`", " ", plain)
    plain = re.sub(r"https?://\S+", " ", plain)
    script = re.compile(
        r"[\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff\u3040-\u30ff"
        r"\u3400-\u9fff\uac00-\ud7af]"
    )
    script_units = [
        character
        for character in script.findall(plain)
        if unicodedata.category(character).startswith(("L", "N"))
    ]
    spaced = script.sub(" ", plain)
    words = re.findall(r"\b[\w'-]+\b", spaced, flags=re.UNICODE)
    return words + script_units


def _without_code(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", " ", text)


def _template_placeholders(text: str) -> list[str]:
    text = _without_code(text)
    definitions = {
        token.casefold()
        for token in re.findall(r"^\[([^\]\n]+)\]:\s*\S", text, re.MULTILINE)
    }
    placeholders: list[str] = []
    for match in re.finditer(r"\[([^\]\n]*)\](?!\s*(?:\(|:))", text):
        token = match.group(1).strip()
        if token.casefold() in definitions:
            continue
        if re.fullmatch(r"(?:S\d{3}|\d+|\^[\w.-]+|[xX])", token):
            continue
        normalized = token.casefold()
        exact = {
            "",
            "n",
            "a",
            "b",
            "x",
            "y",
            "url",
            "date",
            "year",
            "author",
            "audience",
            "topic",
            "process",
            "tool",
            "service",
            "event",
            "result",
            "name",
            "value",
        }
        cues = re.compile(
            r"\b(?:answer-first|info-gain|internal-link|stat|evidence-backed|"
            r"insert|brief|specific|actual|your|sentence|paragraph|explanation|"
            r"description|detail|result|action|question|step|example|metric|"
            r"data point|quote|organization|company|category|comparison|"
            r"alternative|capability|problem|solution|reason|outcome|keyword|"
            r"text|content|insight|finding|approach|recommendation)\b",
            re.IGNORECASE,
        )
        if normalized in exact or cues.search(token):
            placeholders.append(match.group(0))
    return dedupe(placeholders)


def _visual_references(frontmatter: dict[str, Any], body: str) -> tuple[list[str], bool]:
    publishable = _without_code(body)
    references = re.findall(r"!\[[^\]]*\]\(([^\s)]+)", publishable)
    references.extend(
        re.findall(
            r"<\s*(?:img|source|video)\b[^>]*\b(?:src|srcset)=[\"']([^\"']+)",
            publishable,
            re.IGNORECASE,
        )
    )
    for key in ("image", "hero", "coverImage", "cover_image", "ogImage", "og_image"):
        if frontmatter.get(key):
            references.append(str(frontmatter[key]))
    has_unreferenced_visual = bool(
        re.search(r"<\s*(?:svg|picture)\b", publishable, re.IGNORECASE)
    )
    return dedupe(references), has_unreferenced_visual


def review_article(path: Path, request: BlogWriteRequest) -> ArticleReview:
    try:
        frontmatter, body = read_markdown(path)
    except ValueError as exc:
        return ArticleReview(
            False,
            [str(exc)],
            [],
            {"visible_word_units": 0, "image_mode": request.image_mode},
            {},
        )
    errors: list[str] = []
    warnings: list[str] = []
    title = str(frontmatter.get("title", "")).strip()
    description = str(frontmatter.get("description", frontmatter.get("meta_description", ""))).strip()
    slug = str(frontmatter.get("slug", "")).strip()
    primary = str(frontmatter.get("primary_keyword", request.primary_keyword)).strip()
    for name, value in (("title", title), ("description", description), ("slug", slug), ("primary_keyword", primary)):
        if not value:
            errors.append(f"missing required SEO frontmatter: {name}")
    if slug and slug != request.slug:
        errors.append(f"frontmatter slug must match the normalized request slug: {request.slug}")
    h1 = re.findall(r"^#\s+\S.*$", body, re.MULTILINE)
    h2 = re.findall(r"^##\s+\S.*$", body, re.MULTILINE)
    if len(h1) != 1:
        errors.append(f"article must contain exactly one H1; found {len(h1)}")
    if len(h2) < 2:
        errors.append("article must contain at least two substantive H2 sections")
    if not body.strip():
        errors.append("article body is empty")
    intro = re.split(r"^##\s+", body, maxsplit=1, flags=re.MULTILINE)[0]
    if len(_visible_words(intro)) < 30:
        errors.append("opening section must contain at least 30 visible word units")
    sections = re.findall(
        r"^##\s+([^\n]+)\n(.*?)(?=^##\s+|\Z)", body, re.MULTILINE | re.DOTALL
    )
    thin_sections = [heading.strip() for heading, content in sections if len(_visible_words(content)) < 35]
    if thin_sections:
        errors.append(
            "H2 sections must contain at least 35 visible word units: "
            + ", ".join(thin_sections)
        )
    has_named_conclusion = any(
        CONCLUSION_HEADING.match(heading.strip()) for heading, _ in sections
    )
    language = request.language.casefold().replace("_", "-").split("-", 1)[0]
    fallback_closing = (
        language not in KNOWN_CONCLUSION_LANGUAGES
        and len(sections) >= 3
        and len(_visible_words(sections[-1][1])) >= 50
    )
    if sections and not (has_named_conclusion or fallback_closing):
        errors.append(
            "article must contain a substantive closing section in the requested language"
        )
    publishable_body = _without_code(body)
    for pattern in UNFINISHED:
        if pattern.search(publishable_body):
            errors.append(f"unfinished placeholder remains: {pattern.pattern}")
    placeholders = _template_placeholders(body)
    if placeholders:
        preview = ", ".join(placeholders[:3])
        errors.append(f"unfinished template placeholder remains: {preview}")
    if request.image_mode == "deferred":
        publishable_markup = _without_code(body)
        references, has_unreferenced_visual = _visual_references(frontmatter, body)
        allowed = set(request.preserved_image_references)
        new_references = [reference for reference in references if reference not in allowed]
        if new_references:
            errors.append(
                "new visual reference is forbidden while image_mode is deferred: "
                + ", ".join(new_references)
            )
        elif has_unreferenced_visual or (
            not allowed and any(pattern.search(publishable_markup) for pattern in VISUAL_MARKUP)
        ):
            errors.append("visual markup is forbidden while image_mode is deferred")
    searchable = f"{title}\n{body[:1500]}".casefold()
    if primary and primary.casefold() not in searchable:
        errors.append("primary keyword must appear naturally in the title, H1, or opening section")
    words = _visible_words(body)
    hard_floor = max(350, int(request.word_count * 0.60))
    advisory_floor = max(hard_floor, int(request.word_count * 0.85))
    if len(words) < hard_floor:
        errors.append(
            f"visible length {len(words)} is below the minimum complete-article floor {hard_floor}"
        )
    elif len(words) < advisory_floor:
        warnings.append(
            f"visible length {len(words)} is below the advisory target {advisory_floor}"
        )
    numeric_lines = [
        line.strip()
        for line in body.splitlines()
        if NUMERIC_CLAIM.search(line) and not URL.search(line) and not line.lstrip().startswith(("#", "```"))
    ]
    if numeric_lines:
        warnings.append(
            f"{len(numeric_lines)} line(s) contain numeric claims without an inline URL; verify or rewrite qualitatively"
        )
    if request.materials:
        hypotheses = sum(
            item.fact_state == "hypothesis" or "hypothesis" in item.fact_states
            for item in request.materials
        )
        failed = sum(
            item.fact_state == "failed" or "failed" in item.fact_states
            for item in request.materials
        )
        if hypotheses:
            warnings.append(f"input contains {hypotheses} hypothesis material item(s); do not state them as facts")
        if failed:
            warnings.append(f"input contains {failed} failed-path item(s); present only as cautions or lessons")
        restricted = sum(
            item.public_boundary.casefold()
            not in {"public", "公开", "可公开", "publishable"}
            for item in request.materials
        )
        if restricted:
            warnings.append(
                f"input contains {restricted} restricted material item(s); do not publish their claims without explicit verification and permission"
            )
    metrics = {
        "visible_word_units": len(words),
        "h1_count": len(h1),
        "h2_count": len(h2),
        "link_count": len(URL.findall(body)),
        "numeric_claim_lines_without_url": len(numeric_lines),
        "image_mode": request.image_mode,
        "closing_section_present": has_named_conclusion or fallback_closing,
        "named_conclusion_present": has_named_conclusion,
    }
    return ArticleReview(not errors, dedupe(errors), dedupe(warnings), metrics, frontmatter)


def build_schema(article_path: Path, request: BlogWriteRequest) -> dict[str, Any]:
    review = review_article(article_path, request)
    fm = review.frontmatter
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": fm.get("title", ""),
        "description": fm.get("description", fm.get("meta_description", "")),
        "inLanguage": fm.get("lang", request.language or "en"),
        "keywords": [request.primary_keyword, *request.secondary_keywords],
        "author": {
            "@type": "Person",
            "name": fm.get("author", request.brand_voice.get("author", "Editorial Team")),
        },
    }
    if fm.get("date"):
        schema["datePublished"] = fm["date"]
        schema["dateModified"] = fm.get("date_modified", fm["date"])
    if fm.get("canonical"):
        schema["mainEntityOfPage"] = {"@type": "WebPage", "@id": fm["canonical"]}
    if request.image_mode != "deferred" and fm.get("image"):
        schema["image"] = fm["image"]
    return schema


def write_schema(article_path: Path, request: BlogWriteRequest, destination: Path) -> Path:
    atomic_write_json(destination, build_schema(article_path, request))
    return destination


def write_review(path: Path, review: ArticleReview, stage_summary: dict[str, Any]) -> None:
    lines = [
        "# Codex Blog Review",
        "",
        f"Core article complete: **{'yes' if review.complete else 'no'}**",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(review.metrics, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Warnings",
        "",
    ]
    lines.extend(f"- {warning}" for warning in review.warnings)
    if not review.warnings:
        lines.append("- None")
    lines.extend(["", "## Stage results", ""])
    for name, result in stage_summary.items():
        lines.append(f"- `{name}`: {result.get('status')} ({result.get('attempts', 0)} attempt(s))")
        if result.get("error"):
            lines.append(f"  - {result['error']}")
    lines.append("")
    atomic_write_text(path, "\n".join(lines))
