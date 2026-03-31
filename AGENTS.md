# Repository Guidelines

## Project Structure & Module Organization

`main.py` is the CLI entry point for crawling. Core crawler logic lives in `zsxq_crawler/`: `config.py` loads `.env`, `client.py` talks to the zsxq API, `crawler.py` handles pagination and downloads, and `storage.py` writes JSON and media files. The Flask viewer is in `web/`, with routes in `web/app.py`, templates in `web/templates/`, and static assets in `web/static/`. Tests live in `tests/`, and design notes or plans go under `docs/`.

## Build, Test, and Development Commands

Set up a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the crawler with `python main.py`. Common variants are `python main.py --max-pages 5`, `python main.py --no-images --no-files`, and `python main.py -v` for debug logging. Start the web viewer with `python web/app.py`. Run tests with `python -m pytest tests/ -v`.

## Coding Style & Naming Conventions

Follow existing Python style: 4-space indentation, type hints where the surrounding code already uses them, and small focused modules. Prefer `snake_case` for functions, variables, and filenames; use `PascalCase` for classes like `Config` or `Crawler`. Keep Flask route helpers and crawler internals local to their modules instead of introducing new abstraction layers. No formatter or linter config is checked in, so match the current code style closely.

## Testing Guidelines

This repo uses `pytest`. Add tests only when requested or when changing behavior that already has coverage. Place tests in `tests/test_*.py`, name functions `test_*`, and group related cases with `Test*` classes when it helps readability. Favor behavior-level checks like API responses, filtering, persistence, and date handling over trivial getters.

## Commit & Pull Request Guidelines

Recent history uses short imperative subjects, often with a scope prefix such as `docs: add design spec` or `test: add integration tests`. Follow that pattern. Keep each commit focused. PRs should explain the user-visible change, list verification steps, link the relevant issue or plan, and include screenshots when `web/` UI output changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` and set `ZSXQ_COOKIE` and `ZSXQ_GROUP_ID` locally. Never commit real cookies, `.env`, or crawler output from `output/`.
