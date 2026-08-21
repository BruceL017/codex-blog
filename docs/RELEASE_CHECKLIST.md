# Release checklist

1. Confirm all version surfaces equal the intended SemVer release.
2. Confirm exactly 33 Skills and 6 parseable TOML Agents.
3. Run `python3 scripts/validate_repo.py`.
4. Run `python3 -m pytest -q tests plugins/codex-blog/tests` on Python 3.10+.
5. Test install, repeat install, modified-file preservation, and uninstall on
   Unix and Windows CI.
6. Verify default writing performs no image-provider discovery or call.
7. Verify downstream failures make `complete_with_warnings` after two attempts.
8. Verify Codex SEO brief/cluster and `extract-seo-materials` v1/v2 fixtures.
9. Verify OpenAI-compatible and Gemini-compatible custom base URLs with fake
   endpoints; confirm image API secret values do not enter logs or artifacts.
10. Confirm `brain/` is absent and all MIT, Apache, and CC BY attribution is
    present in source and release artifacts; compare the complete Apache 2.0,
    CC BY 4.0, and semantic-cluster-engine MIT texts in root, plugin source,
    sdist, and wheel.
11. Build the wheel and source distribution, then run
    `python3 scripts/smoke_wheel.py plugins/codex-blog/dist`.
12. Build the repository archives and SHA-256 files.
13. Before any GitHub commit, confirm the author and committer email is
    `253661133+BruceL017@users.noreply.github.com`.
