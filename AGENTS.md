# GateKeeper AGENTS.md

## Shell Syntax

Since the environment is Windows (PowerShell), always use `;` as the delimiter, not `&&`.

## Framework & Architecture

- **Language:** Python 3.8+ (enforce type hints via `from __future__ import annotations`)
- **GUI:** Tkinter (stdlib) — single-window, three-state model
- **Lint:** `ruff check .` (format with `ruff format .`)
- **Build:** `.\build.bat` (Nuitka → standalone `dist/main.dist/main.exe`)
- **Run:** `python main.pyw`

## Directory Structure

```
gate_keeper/
├── main.pyw                 # Single-file app (~850 lines)
├── build.bat                # Nuitka build script
├── gate_keeper_history.json # Auto-generated history data
├── README.md
├── AGENTS.md
├── LICENSE                  # Apache 2.0
└── dist/                    # Build output (gitignored)
```

## State Machine & Data Flow

```
VOID ──(ENGAGE)──> SILENT ──(time up)──> OVERTIME
  ^                   │                      │
  └──(Esc/abort)──────┘    (RELEASE)─────────┘
```

- **Session** (dataclass) — holds intent, time tracking, pause state, progress, extend budget
- **HistoryStore** — loads/saves `gate_keeper_history.json` (JSON array of `HistoryEntry`)
- **Theme** — design tokens (dark bg, emerald accent, Segoe UI)

## Key Files

| File | Purpose |
|------|---------|
| `main.pyw` | All source: `GateKeeper(tk.Tk)` with `_build_void()`, `_build_silent()`, `_build_overtime()` |
| `build.bat` | `python -m nuitka --standalone --windows-console-mode=disable --output-dir=dist --enable-plugin=tk-inter main.pyw` |

## Versioning (current: v1.0.0)

When bumping versions:
1. Identify all version occurrences (README, CHANGELOG, AGENTS.md)
2. Update `CHANGELOG.md`
3. Commit changes
4. Create a Git tag
