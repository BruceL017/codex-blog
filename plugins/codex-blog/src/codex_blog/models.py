from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .utils import dedupe, slugify, utc_now

FactState = Literal["verified", "engineering", "hypothesis", "failed", "unknown"]
StageStatus = Literal["pending", "complete", "degraded", "skipped", "blocked"]
ImageMode = Literal["deferred", "hero", "full"]
ImageDecision = Literal["not_asked", "asked", "declined", "hero", "full"]


@dataclass(slots=True)
class MaterialItem:
    title: str
    text: str
    fact_state: FactState = "unknown"
    fact_states: list[FactState] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    public_boundary: str = "confirm-before-publish"
    maturity: str = "unknown"
    contribution_types: list[str] = field(default_factory=list)
    search_intent: str = ""
    search_queries: list[str] = field(default_factory=list)
    current_product_state: str = ""
    current_product_anchor: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "MaterialItem":
        state = str(value.get("fact_state", "unknown"))
        if state not in {"verified", "engineering", "hypothesis", "failed", "unknown"}:
            state = "unknown"
        raw_states = value.get("fact_states", [])
        fact_states = [
            item for item in (str(raw) for raw in raw_states) if item in {"verified", "engineering", "hypothesis", "failed", "unknown"}
        ]
        if not fact_states:
            fact_states = [state]
        return cls(
            title=str(value.get("title", "Material")).strip() or "Material",
            text=str(value.get("text", "")).strip(),
            fact_state=state,  # type: ignore[arg-type]
            fact_states=fact_states,  # type: ignore[arg-type]
            source_refs=dedupe([str(item) for item in value.get("source_refs", [])]),
            public_boundary=str(value.get("public_boundary", "confirm-before-publish")),
            maturity=str(value.get("maturity", "unknown")),
            contribution_types=dedupe(
                [str(item) for item in value.get("contribution_types", [])]
            ),
            search_intent=str(value.get("search_intent", "")).strip(),
            search_queries=dedupe(
                [str(item) for item in value.get("search_queries", [])]
            ),
            current_product_state=str(
                value.get("current_product_state", "")
            ).strip(),
            current_product_anchor=str(
                value.get("current_product_anchor", "")
            ).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SEOContentPacket:
    schema_version: int = 1
    topic: str = ""
    primary_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    search_intent: str = ""
    audience: str = ""
    language: str = ""
    template: str = ""
    word_count: int | None = None
    outline: list[str] = field(default_factory=list)
    content_gaps: list[str] = field(default_factory=list)
    information_gain: list[str] = field(default_factory=list)
    internal_links: list[dict[str, str]] = field(default_factory=list)
    competitor_urls: list[str] = field(default_factory=list)
    materials: list[MaterialItem] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    cluster_context: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SEOContentPacket":
        raw_word_count = value.get("word_count", value.get("word_count_target"))
        try:
            word_count = int(raw_word_count) if raw_word_count not in {None, ""} else None
        except (TypeError, ValueError):
            word_count = None
        raw_materials = value.get("materials", [])
        materials = [
            item if isinstance(item, MaterialItem) else MaterialItem.from_mapping(item)
            for item in raw_materials
            if isinstance(item, (dict, MaterialItem))
        ]
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            topic=str(value.get("topic", value.get("title", ""))).strip(),
            primary_keyword=str(value.get("primary_keyword", "")).strip(),
            secondary_keywords=dedupe(
                [str(item) for item in value.get("secondary_keywords", [])]
            ),
            search_intent=str(value.get("search_intent", "")).strip(),
            audience=str(value.get("audience", "")).strip(),
            language=str(value.get("language", value.get("locale", ""))).strip(),
            template=str(value.get("template", value.get("page_type", ""))).strip(),
            word_count=word_count,
            outline=dedupe([str(item) for item in value.get("outline", [])]),
            content_gaps=dedupe([str(item) for item in value.get("content_gaps", [])]),
            information_gain=dedupe(
                [str(item) for item in value.get("information_gain", [])]
            ),
            internal_links=[dict(item) for item in value.get("internal_links", []) if isinstance(item, dict)],
            competitor_urls=dedupe(
                [str(item) for item in value.get("competitor_urls", [])]
            ),
            materials=materials,
            sources=[dict(item) for item in value.get("sources", []) if isinstance(item, dict)],
            cluster_context=dict(value.get("cluster_context", {})),
            provenance=[dict(item) for item in value.get("provenance", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BlogWriteRequest:
    schema_version: int = 1
    topic: str = ""
    primary_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    search_intent: str = ""
    audience: str = ""
    language: str = ""
    template: str = ""
    word_count: int = 2200
    outline: list[str] = field(default_factory=list)
    content_gaps: list[str] = field(default_factory=list)
    information_gain: list[str] = field(default_factory=list)
    materials: list[MaterialItem] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    internal_links: list[dict[str, str]] = field(default_factory=list)
    competitor_urls: list[str] = field(default_factory=list)
    cluster_context: dict[str, Any] = field(default_factory=dict)
    site_context: dict[str, str] = field(default_factory=dict)
    brand_voice: dict[str, str] = field(default_factory=dict)
    image_mode: ImageMode = "deferred"
    preserved_image_references: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.primary_keyword or self.topic)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "BlogWriteRequest":
        packet = SEOContentPacket.from_mapping(value)
        image_mode = str(value.get("image_mode", "deferred"))
        image_mode = {
            "none": "deferred",
            "cover": "hero",
            "cover-and-inline": "full",
        }.get(image_mode, image_mode)
        if image_mode not in {"deferred", "hero", "full"}:
            image_mode = "deferred"
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            topic=packet.topic,
            primary_keyword=packet.primary_keyword,
            secondary_keywords=packet.secondary_keywords,
            search_intent=packet.search_intent,
            audience=packet.audience,
            language=packet.language,
            template=packet.template,
            word_count=packet.word_count or 2200,
            outline=packet.outline,
            content_gaps=packet.content_gaps,
            information_gain=packet.information_gain,
            materials=packet.materials,
            sources=packet.sources,
            internal_links=packet.internal_links,
            competitor_urls=packet.competitor_urls,
            cluster_context=packet.cluster_context,
            site_context=dict(value.get("site_context", {})),
            brand_voice=dict(value.get("brand_voice", {})),
            image_mode=image_mode,  # type: ignore[arg-type]
            preserved_image_references=dedupe(
                [str(item) for item in value.get("preserved_image_references", [])]
            ),
            conflicts=[str(item) for item in value.get("conflicts", [])],
            provenance=packet.provenance,
        )


@dataclass(slots=True)
class StageResult:
    name: str
    status: StageStatus = "pending"
    attempts: int = 0
    artifacts: list[str] = field(default_factory=list)
    warning: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunManifest:
    schema_version: int
    run_id: str
    status: str
    topic: str
    slug: str
    language: str
    template: str
    output_dir: str
    image_mode: ImageMode
    image_status: str
    image_decision: ImageDecision
    image_assets: list[dict[str, Any]]
    article_digest: str
    request_digest: str
    provenance: list[dict[str, str]]
    conflicts: list[str]
    article: str
    request: str
    stages: dict[str, StageResult]
    warnings: list[str]
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, request: BlogWriteRequest, output_dir: Path) -> "RunManifest":
        timestamp = utc_now()
        run_id = f"{request.slug}-{timestamp.replace(':', '').replace('+00:00', 'Z')}"
        return cls(
            schema_version=1,
            run_id=run_id,
            status="awaiting_article",
            topic=request.topic,
            slug=request.slug,
            language=request.language,
            template=request.template,
            output_dir=str(output_dir),
            image_mode=request.image_mode,
            image_status="not_requested" if request.image_mode == "deferred" else "pending",
            image_decision="not_asked" if request.image_mode == "deferred" else request.image_mode,
            image_assets=[],
            article_digest="",
            request_digest=request.digest(),
            provenance=[dict(item) for item in request.provenance],
            conflicts=list(request.conflicts),
            article=str(output_dir / f"{request.slug}.md"),
            request=str(output_dir / "request.json"),
            stages={
                "core_article": StageResult("core_article"),
                "schema": StageResult("schema"),
                "html": StageResult("html"),
                "pdf": StageResult("pdf"),
                "seo_geo": StageResult("seo_geo"),
                "facts_links": StageResult("facts_links"),
                "platform": StageResult("platform"),
                "report": StageResult("report"),
                "images": StageResult("images", status="skipped" if request.image_mode == "deferred" else "pending"),
            },
            warnings=[],
            created_at=timestamp,
            updated_at=timestamp,
        )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "RunManifest":
        image_mode = str(value.get("image_mode", "deferred"))
        if image_mode not in {"deferred", "hero", "full"}:
            image_mode = "deferred"
        image_decision = str(
            value.get(
                "image_decision",
                "not_asked" if image_mode == "deferred" else image_mode,
            )
        )
        if image_decision not in {"not_asked", "asked", "declined", "hero", "full"}:
            image_decision = "not_asked" if image_mode == "deferred" else image_mode
        stages = {
            name: StageResult(**stage)
            for name, stage in dict(value.get("stages", {})).items()
            if isinstance(stage, dict)
        }
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            run_id=str(value["run_id"]),
            status=str(value["status"]),
            topic=str(value["topic"]),
            slug=str(value["slug"]),
            language=str(value.get("language", "")),
            template=str(value.get("template", "")),
            output_dir=str(value["output_dir"]),
            image_mode=image_mode,  # type: ignore[arg-type]
            image_status=str(value.get("image_status", "not_requested")),
            image_decision=image_decision,  # type: ignore[arg-type]
            image_assets=[
                dict(item)
                for item in value.get("image_assets", [])
                if isinstance(item, dict)
            ],
            article_digest=str(value.get("article_digest", "")),
            request_digest=str(value.get("request_digest", "")),
            provenance=[
                dict(item) for item in value.get("provenance", []) if isinstance(item, dict)
            ],
            conflicts=[str(item) for item in value.get("conflicts", [])],
            article=str(value["article"]),
            request=str(value["request"]),
            stages=stages,
            warnings=[str(item) for item in value.get("warnings", [])],
            created_at=str(value["created_at"]),
            updated_at=str(value.get("updated_at", value["created_at"])),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stages"] = {name: stage.to_dict() for name, stage in self.stages.items()}
        return value
