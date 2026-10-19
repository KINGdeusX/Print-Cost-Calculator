# Changelog

## 0.3.0 — 2026-10-19

### Added
- Projects: save, reopen, rename and delete quotes from a project list (stored in `Documents\Print Cost Calculator`).
- Invoices: numbered PDF invoices (`INV-0001`...) created from a project, recorded with the project.
- Company name and logo in preferences, shown on invoices.
- Windows installer (`PrintCostCalculator-<version>-setup.exe`) with Start menu entry, optional desktop shortcut and a smoke-tested uninstall that keeps your data.

### Changed
- The start screen is now the project list; the printer selector moved into projects.

## 0.2.0 — 2026-10-17

### Added
- New `pcc` package with a pure-Python core (pricing, `.3mf` parsing, storage, Excel export).
- Multi-plate jobs with per-plate copies and labor, plus a live price summary.
- `.3mf` drag & drop import with automatic filament and printer matching.
- Failure allowance, packaging per job, hidden per-plate fee (never exported) and configurable rounding step.
- Printer and filament profile editors, multiple currencies, light/dark/system theme.
- Excel report export with "append to last report" and a locked-file retry.
- `pcc` command-line tool (`quote`, `parse`, `printers`, `filaments`, `serve`).
- HTTP API (FastAPI, OpenAPI 3.1 at `/openapi.json`) and a `Dockerfile`.
- PyInstaller packaging: Windows zip, Linux AppImage and tarball.
- GitHub Actions CI (Linux and Windows, Python 3.11 and 3.13) and tagged release builds.

### Changed
- Settings and catalog now live in a per-user config directory (override with `PCC_CONFIG_DIR`); a v0.1 `pricing_config.json` is migrated when valid.
- The GUI was rebuilt on PySide6 with a compact, scrollable layout.

### Removed
- `Cronus.py` single-window app.
- `pandas` dependency.
- Committed build artifacts.
