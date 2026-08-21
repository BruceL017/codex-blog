# Contributing to Codex Blog

Thank you for helping improve the article-first content pipeline. By
contributing, you agree to the Code of Conduct and to license your contribution
under MIT unless an existing file clearly carries another compatible license.

## Development setup

```bash
git clone https://github.com/BruceL017/codex-blog.git
cd codex-blog
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r plugins/codex-blog/requirements-dev.txt
python -m pip install -e plugins/codex-blog
python scripts/validate_repo.py
python -m pytest -q tests plugins/codex-blog/tests
```

On Windows, activate with `.venv\Scripts\Activate.ps1`.

## Change rules

- Keep the article-first, image-deferred, one-retry behavior intact.
- Do not make optional SEO Skills, MCPs, APIs, rendering libraries, or image
  providers prerequisites for core writing.
- Add compatibility through normalized files and adapters, not imports from
  another Skill repository.
- Keep provider secrets in the environment and use synthetic values in tests.
- Update fixtures and contract tests when an input schema intentionally changes.
- Preserve every attribution listed in `NOTICE` and `THIRD_PARTY.md`.
- Never copy the restricted upstream `brain/` subtree.

Pull requests should explain the user-visible outcome, tests run, compatibility
impact, and any new network or credential surface.
