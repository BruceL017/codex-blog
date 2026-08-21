from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_blog import cluster
from codex_blog.cli import main as cli_main
from codex_blog.models import StageResult
from codex_blog.pipeline import CoreArticleError, load_manifest, save_manifest


def _plan(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "version": "2.2.4",
                "seed_keyword": "content operations",
                "language": "en",
                "pillar": {
                    "title": "Content Operations Guide",
                    "keyword": "content operations",
                    "url": "/content-operations/",
                    "wordCount": 700,
                },
                "clusters": [
                    {
                        "name": "Workflow",
                        "posts": [
                            {
                                "title": "SEO Content Workflow",
                                "keyword": "seo content workflow",
                                "url": "/seo-content-workflow/",
                                "wordCount": 700,
                            },
                            {
                                "title": "Editorial Checkpoints",
                                "keyword": "editorial checkpoints",
                                "url": "/editorial-checkpoints/",
                                "wordCount": 700,
                            },
                        ],
                    }
                ],
                "links": [
                    {
                        "from": "cluster-0-post-0",
                        "to": "pillar",
                        "type": "mandatory",
                        "anchor": "content operations guide",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _complete_run(run_dir: Path) -> None:
    manifest = load_manifest(run_dir)
    Path(manifest.article).write_text("complete", encoding="utf-8")
    for name, stage in manifest.stages.items():
        if name == "images":
            stage.status = "skipped"
        else:
            stage.status = "complete"
            stage.attempts = 1
            stage.artifacts = [manifest.article] if name == "core_article" else []
    manifest.status = "complete"
    save_manifest(manifest)


def _fake_finalize(run_dir: Path, **_: object):
    if not (run_dir / f"{run_dir.name}.md").is_file():
        raise CoreArticleError("article is missing", blocked=False, attempts=0)
    _complete_run(run_dir)
    return load_manifest(run_dir)


def test_prepare_creates_every_canonical_node_and_resumes_idempotently(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path / "cluster-plan.json")

    first = cluster.prepare_cluster(plan, tmp_path / "output")

    assert [item["id"] for item in first["articles"]] == [
        "pillar",
        "cluster-0-post-0",
        "cluster-0-post-1",
    ]
    assert [item["role"] for item in first["articles"]] == [
        "pillar",
        "spoke",
        "spoke",
    ]
    request_mtimes = {
        item["id"]: (Path(item["run_dir"]) / "request.json").stat().st_mtime_ns
        for item in first["articles"]
    }
    for item in first["articles"]:
        run_dir = Path(item["run_dir"])
        request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        assert request["image_mode"] == "deferred"
        assert Path(item["article"]).parent == run_dir
        assert not Path(item["article"]).exists()

    second = cluster.prepare_cluster(plan, tmp_path / "output")

    assert [item["run_dir"] for item in second["articles"]] == [
        item["run_dir"] for item in first["articles"]
    ]
    assert request_mtimes == {
        item["id"]: (Path(item["run_dir"]) / "request.json").stat().st_mtime_ns
        for item in second["articles"]
    }
    assert second["image_decision"] == "not_asked"


def test_finalize_continues_other_articles_and_claims_one_batch_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(_plan(tmp_path / "plan.json"), tmp_path / "out")
    articles = manifest["articles"]
    Path(articles[0]["article"]).write_text("draft", encoding="utf-8")
    Path(articles[2]["article"]).write_text("draft", encoding="utf-8")
    calls: list[str] = []

    def finalize(run_dir: Path, **kwargs: object):
        calls.append(run_dir.name)
        return _fake_finalize(run_dir, **kwargs)

    monkeypatch.setattr(cluster, "finalize_run", finalize)

    first, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is False
    assert [item["status"] for item in first["articles"]] == [
        "non_image_complete",
        "awaiting_article",
        "non_image_complete",
    ]
    assert first["image_decision"] == "not_asked"

    Path(articles[1]["article"]).write_text("draft", encoding="utf-8")
    second, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is True
    assert second["image_decision"] == "asked"
    assert all(
        item["status"] == "non_image_complete" for item in second["articles"]
    )
    before = list(calls)

    third, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is False
    assert third["image_decision"] == "asked"
    assert calls == before


def test_blocked_article_does_not_hold_other_articles_or_batch_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(_plan(tmp_path / "plan.json"), tmp_path / "out")
    for item in manifest["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    blocked = Path(manifest["articles"][1]["run_dir"])

    def finalize(run_dir: Path, **kwargs: object):
        if run_dir == blocked:
            run_manifest = load_manifest(run_dir)
            core = run_manifest.stages.setdefault(
                "core_article", StageResult("core_article")
            )
            core.status = "blocked"
            core.attempts = 3
            core.error = "incomplete article"
            run_manifest.status = "blocked"
            save_manifest(run_manifest)
            raise CoreArticleError("incomplete article", blocked=True, attempts=3)
        return _fake_finalize(run_dir, **kwargs)

    monkeypatch.setattr(cluster, "finalize_run", finalize)

    result, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is True
    assert [item["status"] for item in result["articles"]] == [
        "non_image_complete",
        "blocked",
        "non_image_complete",
    ]
    assert result["status"] == "complete_with_warnings"


def test_explicit_images_are_planned_only_after_the_entire_queue_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(
        _plan(tmp_path / "plan.json"), tmp_path / "out", image_mode="full"
    )
    articles = manifest["articles"]
    Path(articles[0]["article"]).write_text("draft", encoding="utf-8")
    planned: list[tuple[str, str]] = []

    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)

    def plan_images(run_dir: Path, scope: str):
        planned.append((run_dir.name, scope))
        return {"scope": scope, "items": []}

    monkeypatch.setattr(cluster, "create_image_plan", plan_images)

    first, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is False
    assert planned == []
    assert first["image_decision"] == "full"

    for item in articles[1:]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    second, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert prompt is False
    assert planned == [
        ("content-operations", "full"),
        ("seo-content-workflow", "full"),
        ("editorial-checkpoints", "full"),
    ]
    assert all(item["image_status"] == "planned" for item in second["articles"])

    cluster.finalize_cluster(Path(manifest["output_dir"]))
    assert len(planned) == 3


def test_image_planning_failure_is_bounded_to_two_attempts_per_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(
        _plan(tmp_path / "plan.json"), tmp_path / "out", image_mode="hero"
    )
    for item in manifest["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)
    calls: list[str] = []

    def fail_plan(run_dir: Path, scope: str):
        calls.append(f"{run_dir.name}:{scope}")
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(cluster, "create_image_plan", fail_plan)

    cluster.finalize_cluster(Path(manifest["output_dir"]))
    cluster.finalize_cluster(Path(manifest["output_dir"]))
    result, _ = cluster.finalize_cluster(Path(manifest["output_dir"]))

    assert len(calls) == 6
    assert all(item["image_attempts"] == 2 for item in result["articles"])
    assert all(item["image_status"] == "degraded" for item in result["articles"])


def test_batch_converges_after_all_successful_child_image_runs_are_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(
        _plan(tmp_path / "plan.json"), tmp_path / "out", image_mode="hero"
    )
    for item in manifest["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)

    def plan_images(run_dir: Path, scope: str):
        run = load_manifest(run_dir)
        run.image_status = "planned"
        run.stages["images"].status = "pending"
        save_manifest(run)
        return {"scope": scope, "items": []}

    monkeypatch.setattr(cluster, "create_image_plan", plan_images)
    planned, _ = cluster.finalize_cluster(Path(manifest["output_dir"]))
    assert planned["status"] == "images_planned"

    for index, item in enumerate(planned["articles"]):
        run = load_manifest(Path(item["run_dir"]))
        run.image_status = "degraded" if index == 1 else "complete"
        run.stages["images"].status = run.image_status
        save_manifest(run)

    finished = cluster.cluster_status(Path(manifest["output_dir"]))
    assert finished["status"] == "complete_with_warnings"


def test_one_corrupt_child_manifest_is_bounded_and_other_pages_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(_plan(tmp_path / "plan.json"), tmp_path / "out")
    for item in manifest["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    broken_path = Path(manifest["articles"][1]["run_dir"]) / "run-manifest.json"
    broken = json.loads(broken_path.read_text(encoding="utf-8"))
    broken["output_dir"] = str(tmp_path / "outside")
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)

    first, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))
    assert prompt is False
    assert [item["status"] for item in first["articles"]] == [
        "non_image_complete",
        "ready_to_finalize",
        "non_image_complete",
    ]

    second, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))
    assert prompt is True
    assert [item["status"] for item in second["articles"]] == [
        "non_image_complete",
        "failed",
        "non_image_complete",
    ]


def test_invalid_late_duplicate_leaves_no_batch_artifacts_and_can_be_corrected(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path / "plan.json")
    value = json.loads(plan.read_text(encoding="utf-8"))
    value["clusters"][0]["posts"][1]["keyword"] = "content operations"
    plan.write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "out"

    with pytest.raises(ValueError, match="duplicated"):
        cluster.prepare_cluster(plan, output)
    assert not output.exists()

    value["clusters"][0]["posts"][1]["keyword"] = "editorial checkpoints"
    plan.write_text(json.dumps(value), encoding="utf-8")
    corrected = cluster.prepare_cluster(plan, output)
    assert len(corrected["articles"]) == 3


def test_decline_images_is_persisted_for_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = cluster.prepare_cluster(_plan(tmp_path / "plan.json"), tmp_path / "out")
    for item in manifest["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)
    finalized, prompt = cluster.finalize_cluster(Path(manifest["output_dir"]))
    assert prompt is True
    declined: list[str] = []

    def decline(run_dir: Path):
        declined.append(run_dir.name)
        return load_manifest(run_dir)

    monkeypatch.setattr(cluster, "decline_images", decline)
    result = cluster.decline_cluster_images(Path(finalized["output_dir"]))

    assert result["image_decision"] == "declined"
    assert result["status"] == "complete"
    assert declined == [
        "content-operations",
        "seo-content-workflow",
        "editorial-checkpoints",
    ]


def test_manifest_path_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = cluster.prepare_cluster(_plan(tmp_path / "plan.json"), tmp_path / "out")
    path = Path(manifest["output_dir"]) / "cluster-run-manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["articles"][0]["run_dir"] = str(tmp_path / "outside")
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="article run directory"):
        cluster.load_cluster_manifest(path)


def test_prepare_rejects_a_symlinked_output_ancestor_before_creating_files(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(ValueError, match="symlink ancestor"):
        cluster.prepare_cluster(
            _plan(tmp_path / "plan.json"), linked / "escaped-output"
        )

    assert not (real / "escaped-output").exists()


def test_cluster_cli_prepare_status_and_decline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path / "plan.json")
    assert (
        cli_main(
            [
                "cluster",
                "prepare",
                str(plan),
                "--output-root",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    prepared = json.loads(capsys.readouterr().out)
    batch = Path(prepared["output_dir"])
    assert len(prepared["articles"]) == 3

    assert cli_main(["cluster", "status", "--run", str(batch)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "awaiting_articles"

    for item in prepared["articles"]:
        Path(item["article"]).write_text("draft", encoding="utf-8")
    monkeypatch.setattr(cluster, "finalize_run", _fake_finalize)
    assert cli_main(["cluster", "finalize", "--run", str(batch)]) == 0
    finalized = json.loads(capsys.readouterr().out)
    assert finalized["image_prompt_required"] is True

    monkeypatch.setattr(cluster, "decline_images", lambda run: load_manifest(run))
    assert cli_main(["cluster", "decline-images", "--run", str(batch)]) == 0
    declined = json.loads(capsys.readouterr().out)
    assert declined["image_decision"] == "declined"
