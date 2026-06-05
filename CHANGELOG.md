# Changelog

## v1.0.1 (2026-06-05)

- Move history data storage to `%APPDATA%/GateKeeper` for per-user isolation
- Add startup error handling and file logging via `logging` module
- Fix type hints and event handler type assertions for `ruff`/`pyright` compliance
- Add CI lint workflow (`.github/workflows/lint.yml`) and `requirements-dev.txt`
- Update AGENTS.md to reflect actual directory structure and state machine

## v1.0.0 (2026-05-14)

- Initial release — single-window focus timer with three-state model (VOID / SILENT / OVERTIME)
- Intent-first engagement, pause/resume, extend budget with cap
- History tracking with filter, pagination, and delete
- Overtime growth animation, fade transitions, screen-edge clamped dragging
- Nuitka-based standalone build via `build.bat`
