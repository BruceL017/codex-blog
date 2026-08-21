from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_blog.brain import (
    BrainStoreError,
    build_context,
    capture_source,
    forget_entry,
    init_store,
    promote_entry,
    remember_entry,
    scan_store,
    search_entries,
    show_entry,
    supersede_entry,
)
from codex_blog.cli import build_parser, main


def test_remember_creates_complete_auditable_record(tmp_path: Path) -> None:
    init_store("project", tmp_path)
    entry = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Canonical product name is Codex Blog.",
        entry_type="terminology",
        fact_state="supported",
        publication="public",
        source_refs=["docs:brand-guide#product-name"],
        topics=["brand"],
        entities=["Codex Blog"],
        locale="en",
        notes="Use the full name on first mention.",
    )

    assert entry["id"].startswith("kb_")
    assert entry["scope"] == "project"
    assert entry["statement"] == "Canonical product name is Codex Blog."
    assert entry["fact_state"] == "supported"
    assert entry["publication"] == "public"
    assert entry["source_refs"] == ["docs:brand-guide#product-name"]
    assert entry["provenance"]["kind"] == "user-approved"
    assert entry["history"][0]["action"] == "remembered"
    assert entry["created_at"] == entry["reviewed_at"]
    assert show_entry(entry["id"], tmp_path, scope="project")["id"] == entry["id"]


def test_unsupported_factual_state_is_not_silently_upgraded(tmp_path: Path) -> None:
    entry = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="The conversion rate doubled.",
        entry_type="fact",
        fact_state="verified",
        publication="internal",
    )

    assert entry["fact_state"] == "unverified"
    assert entry["source_refs"] == []
    assert entry["history"][-1]["detail"] == "fact state downgraded because no source reference was supplied"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notes", "token=ghp_abcdefghijklmnopqrstuvwxyz123456"),
        ("source_refs", ["https://example.test/?api_key=super-secret-value"]),
        ("topics", ["-----BEGIN PRIVATE KEY-----"]),
        ("entities", ["Bearer sk-test-secret-material"]),
        ("provenance_extra", {"captured": "password=hunter2-secret"}),
    ],
)
def test_brain_rejects_secrets_in_every_free_text_field(
    tmp_path: Path, field: str, value: object
) -> None:
    kwargs = {
        "scope": "project",
        "project_root": tmp_path,
        "statement": "Safe reusable statement.",
        "entry_type": "lesson",
        "fact_state": "not-applicable",
        "publication": "internal",
        field: value,
    }

    with pytest.raises(ValueError, match="credential or secret"):
        remember_entry(**kwargs)


def test_capture_proposes_by_default_and_auto_is_explicit(tmp_path: Path) -> None:
    source = tmp_path / "retrospective.md"
    source.write_text(
        "# Retrospective\n\n- lesson: Answer-first sections reduced editorial rework.\n",
        encoding="utf-8",
    )

    proposal = capture_source(source, scope="project", project_root=tmp_path)
    assert proposal["saved"] == []
    assert proposal["proposals"][0]["statement"] == "Answer-first sections reduced editorial rework."
    assert scan_store("project", tmp_path).entries == []

    captured = capture_source(source, scope="project", project_root=tmp_path, auto=True)
    assert len(captured["saved"]) == 1
    stored = show_entry(captured["saved"][0], tmp_path, scope="project")
    assert stored["provenance"]["kind"] == "automatic-capture"
    assert stored["source_refs"] == [str(source.resolve())]


def test_project_store_and_capture_refuse_symlinked_ancestors(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside_store = tmp_path / "outside-store"
    project.mkdir()
    outside_store.mkdir()
    try:
        (project / ".codex-blog").symlink_to(
            outside_store, target_is_directory=True
        )
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(BrainStoreError, match="symlink ancestor"):
        init_store("project", project)
    assert list(outside_store.iterdir()) == []

    outside_source = tmp_path / "outside-source"
    outside_source.mkdir()
    (outside_source / "notes.md").write_text(
        "- lesson: This source must not be followed.\n", encoding="utf-8"
    )
    linked_source = tmp_path / "linked-source"
    linked_source.symlink_to(outside_source, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink ancestor"):
        capture_source(
            linked_source / "notes.md",
            scope="global",
            project_root=project,
        )


def test_search_honors_publication_boundary_and_surfaces_scope_conflicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "plugin-data"))
    global_entry = remember_entry(
        scope="global",
        project_root=tmp_path,
        statement="Use sentence case for product headings.",
        entry_type="voice",
        fact_state="not-applicable",
        publication="public",
        topics=["headings"],
    )
    project_entry = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Use title case for product headings.",
        entry_type="voice",
        fact_state="not-applicable",
        publication="public",
        topics=["headings"],
    )
    remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Never expose the launch codename.",
        entry_type="decision",
        fact_state="not-applicable",
        publication="do-not-publish",
        topics=["headings"],
    )

    result = search_entries("headings", tmp_path, boundary="public")

    assert [row["id"] for row in result["entries"][:2]] == [
        project_entry["id"],
        global_entry["id"],
    ]
    assert all(row["publication"] == "public" for row in result["entries"])
    assert result["conflicts"] == [
        {"project_id": project_entry["id"], "global_id": global_entry["id"]}
    ]


def test_context_is_public_only_and_untrusted(tmp_path: Path) -> None:
    remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Use Codex Blog in public copy.",
        entry_type="terminology",
        fact_state="not-applicable",
        publication="public",
    )
    remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Internal launch date is Friday.",
        entry_type="fact",
        fact_state="unverified",
        publication="internal",
    )

    context = build_context(tmp_path)

    assert "Use Codex Blog in public copy." in context
    assert "Internal launch date is Friday." not in context
    assert "untrusted reference data" in context
    assert "publication: public" in context


def test_promotion_copies_origin_and_supersede_preserves_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path / "plugin-data"))
    old = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Call the feature Draft Mode.",
        entry_type="terminology",
        fact_state="not-applicable",
        publication="public",
    )
    new = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Call the feature Authoring Mode.",
        entry_type="terminology",
        fact_state="not-applicable",
        publication="public",
    )

    promoted = promote_entry(old["id"], tmp_path)
    assert promoted["scope"] == "global"
    assert promoted["id"] != old["id"]
    assert promoted["provenance"]["origin_id"] == old["id"]
    assert show_entry(old["id"], tmp_path, scope="project")["id"] == old["id"]

    supersede_entry(old["id"], new["id"], tmp_path, scope="project")
    old_after = show_entry(old["id"], tmp_path, scope="project")
    new_after = show_entry(new["id"], tmp_path, scope="project")
    assert old_after["superseded_by"] == [new["id"]]
    assert new_after["supersedes"] == [old["id"]]
    assert old_after["history"][-1]["action"] == "superseded"
    assert new_after["history"][-1]["action"] == "supersedes"


def test_forget_requires_exact_id_scope_and_confirmation(tmp_path: Path) -> None:
    entry = remember_entry(
        scope="project",
        project_root=tmp_path,
        statement="Temporary editorial decision.",
        entry_type="decision",
        fact_state="not-applicable",
        publication="internal",
    )

    with pytest.raises(ValueError, match="confirmation"):
        forget_entry(entry["id"], tmp_path, scope="project", confirmation="wrong")
    with pytest.raises(KeyError):
        forget_entry(entry["id"], tmp_path, scope="global", confirmation=entry["id"])

    forgotten = forget_entry(
        entry["id"], tmp_path, scope="project", confirmation=entry["id"]
    )
    assert forgotten == {"id": entry["id"], "scope": "project"}
    with pytest.raises(KeyError):
        show_entry(entry["id"], tmp_path, scope="project")


def test_corrupt_records_are_reported_and_never_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / ".codex-blog" / "brain"
    entries = root / "entries"
    entries.mkdir(parents=True)
    corrupt = entries / "kb_0123456789abcdef.json"
    corrupt.write_text("{not-json", encoding="utf-8")

    scan = scan_store("project", tmp_path)
    assert scan.entries == []
    assert scan.errors and str(corrupt) in scan.errors[0]

    with pytest.raises(BrainStoreError, match="invalid record"):
        remember_entry(
            scope="project",
            project_root=tmp_path,
            statement="Do not overwrite the damaged record.",
            entry_type="decision",
            fact_state="not-applicable",
            publication="internal",
        )
    assert corrupt.read_text(encoding="utf-8") == "{not-json"

    assert main(["brain", "context", "--project-root", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Brain skipped for this run" in captured.err
    assert str(corrupt) in captured.err
    assert corrupt.read_text(encoding="utf-8") == "{not-json"


def test_cli_exposes_full_contract_and_compatibility_aliases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    for argv, command in (
        (["brain", "init", "project"], "init"),
        (["brain", "capture", "run.md"], "capture"),
        (["brain", "remember", "A reusable statement"], "remember"),
        (["brain", "search", "reusable"], "search"),
        (["brain", "show", "kb_0123456789abcdef"], "show"),
        (["brain", "list", "fact"], "list"),
        (["brain", "promote", "kb_0123456789abcdef"], "promote"),
        (
            ["brain", "supersede", "kb_0123456789abcdef", "kb_fedcba9876543210"],
            "supersede",
        ),
        (
            [
                "brain",
                "forget",
                "kb_0123456789abcdef",
                "--scope",
                "project",
                "--confirm",
                "kb_0123456789abcdef",
            ],
            "forget",
        ),
        (["brain", "add", "--title", "Compatibility", "--content", "Works"], "add"),
        (["brain", "context"], "context"),
    ):
        assert parser.parse_args(argv).brain_command == command

    assert main(["brain", "init", "project", "--project-root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["scope"] == "project"
