# ADR-0001 — Python Engine Strategy

- **Status:** Accepted (2026-07-05); **corrected 2026-07-05** after live verification.
- **Deciders:** Product owner (BK Designs) + Lead Architect
- **Supersedes:** the `CLAUDE.md` note that "IronPython (pyRevit's default)" is the assumed engine
  — corrected version below actually *confirms* CLAUDE.md was right and the original
  version of this ADR was wrong.

## Correction (2026-07-05)

The original version of this ADR assumed **IronPython 3.4** ships as this pyRevit
installation's engine. That was wrong. Phase 0 smoke testing (`execute_revit_code`
against the live Revit 2026 session) confirmed the actual engine:

```
sys.version        = 2.7.12 (2.7.12.1000) [.NETStandard,Version=v2.0 on .NET 8.0.23]
platform.python_implementation() = IronPython
pyrevit HOST_APP.version = 2026, engine_ver = 2712
```

This is **classic IronPython 2.7**, not IronPython 3.4. `CLAUDE.md`'s original note
("IronPython is Python 2-compatible... avoid f-strings") was correct all along. The
mistake was assuming a newer pyRevit engine option without checking what was actually
installed/configured on this machine. The bug this caused was concrete: a stray
non-ASCII em-dash in `bkbim/__init__.py`'s docstring raised a `SyntaxError` under the
live engine (PEP 263 - Python 2 requires a declared encoding for non-ASCII source
bytes; Python 3 does not). Fixed by adding `# -*- coding: utf-8 -*-` headers and
avoiding non-ASCII characters in `.py` source going forward.

## Context

BK BIM Tools is a long-horizon (5–10 year) commercial suite. The product vision
requires, at once: WPF/.NET interop for a premium UI, access to the pip ecosystem for
AI/network/data features, and a clean eventual migration to C#. Options given the
*actual* installed engine:

- **IronPython 2.7** (confirmed installed, engine 2712) — EOL upstream, Python 2
  syntax only (no type hints, no f-strings, explicit encoding declarations needed for
  non-ASCII source) — but full, native .NET/WPF interop and the only engine pyRevit
  pushbutton scripts run under by default in this environment.
- **CPython 3** (`#! python3` shebang, or a fully separate process like the existing
  `revit-mcp-python.extension` MCP server) — full pip ecosystem, modern syntax, but
  clunkier .NET/WPF interop and some harder Revit API patterns.
- IronPython 3.x is **not** confirmed available as a pyRevit engine option on this
  installation; do not assume it without re-verifying (`sys.version_info` /
  `platform.python_implementation()` inside `execute_revit_code`).

## Decision

Adopt a **hybrid, two-engine strategy with a hard architectural firewall**:

1. **IronPython 2.7 is the primary engine** for all Revit-facing and UI code
   (adapters, commands, WPF viewmodels/views) — because it is what this pyRevit
   installation actually runs. Code must be Python-2.7-compatible: no PEP 484
   annotation syntax, no f-strings, `class Foo(object):` explicit new-style classes,
   `# -*- coding: utf-8 -*-` on every file, ASCII-only source content preferred.
2. **CPython 3 is used only for leaf modules** that require pip packages the Revit
   API cannot provide — the AI/MCP client (`revit-mcp-python.extension`'s `tools/`
   and `main.py`, already CPython 3), heavy data export, reporting.
3. **The `domain` and `core` layers stay pure Python 2.7-compatible** — no `import
   clr`, no `Autodesk.Revit` — so they run under the live IronPython 2.7 engine *and*
   under CPython (verified: `bkbim.core` unit tests run and pass under
   `C:\Python314\python.exe`, since well-written Python 2.7-compatible code is also
   valid Python 3). This is what makes the eventual C# port mechanical.

## Consequences

- **Positive:** matches the real, verified environment; deterministic and testable
  core (proven by 24 passing unit tests under plain CPython plus a live in-Revit
  smoke test); straight path to C#.
- **Cost:** no type hints or f-strings anywhere in `bkbim` until/unless a newer engine
  is confirmed available; every `.py` file needs an explicit encoding declaration if
  it might ever contain non-ASCII bytes (prefer: don't - keep source ASCII).
- **Guardrail (enforce in CI later):** *no `Autodesk.Revit` import is permitted below
  the `bkbim.revit` adapter layer.* This single rule protects portability and testability.
- **Process guardrail:** re-verify engine assumptions (`sys.version_info`,
  `platform.python_implementation()`) against the live environment before writing an
  ADR that depends on them - don't assume from general pyRevit knowledge.
