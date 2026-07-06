# Jacktorr — Agent Working Constraints & Preferences

> Reference for any AI agent working in `plugin.video.jacktorr`.

## Environment

- **Live TorrServer**: `http://192.168.50.26:5665` (MatriX.141.7)
- **Kodi addon**: `reuselanguageinvoker=true` in `addon.xml` → `api` singleton and
  `service` module are cached across invocations. DaemonMonitor.fix requires
  Kodi restart to take effect.
- **Test suite**: `pytest tests/ -q` — 55 tests passing at last check.

## Workflow

- **Use subagents per phase** — each improvement phase delegated, not inline.
- **Use CodeGraph and Engram MCP tools proactively** — search memory first,
  use `codegraph_explore` before broad filesystem/Grep exploration.
- **Surgical edits only** — minimal diffs; no gratuitous refactors.
- **No AI attribution** in commits; no "Co-Authored-By" lines.
- **Comments in English** — neutral/professional, no regional slang.
- **Conventional commits** — `fix:`, `feat:`, `refactor:`, `docs:`, etc.
- **No push to origin** unless explicitly requested.

