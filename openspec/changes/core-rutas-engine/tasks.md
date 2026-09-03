# Tasks: Core Rutas Engine — V2 Foundation

Engine: blank V2 repo; every group lands as its own commit(s) with the suite GREEN
(`python3 -m pytest` from root, no Nuke installed). TDD per group: RED test → GREEN
code → verify. Decisions D1–D7 come from design.md; D8 (test matrix) and D9
(implementation order: extractions → guard → engine) are covered by group ordering
and per-module test tasks below. No `SamanTools/rutas.py` shim in this change —
recorded only for the future load-layer change (proposal traceability).

**Neutralization contract (only allowed real-token usage besides the exempt guard
test):** `wupm→estudio`, `wupmCloud→estudioCloud`, `L:/2026→L:/VFX/2026`,
`/mnt/wupm→/mnt/estudio`, `HTLR/PCF→CINE`. No real studio paths/tokens anywhere
outside this contract.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2,300 – 2,800 (authored) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR2 → PR3 → PR4 → PR5 → PR6 → PR7 (stacked-to-main) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| G1 | Scaffold + purity guard (commit one) | PR 1 | `python3 -m pytest tests/test_no_import_nuke_en_core.py` | `python3 -m pytest` full suite, empty `core/`, no Nuke | Revert PR1 commit; no source depends on it yet |
| G2 | Extract `core/entorno.py` + pure test subset | PR 2 | `python3 -m pytest tests/test_entorno.py` | `python3 -m pytest` on machine without Nuke | Revert removes `core/entorno.py` + its test |
| G3 | Extract `core/nombres.py` + ported tests | PR 3 | `python3 -m pytest tests/test_nombres.py` | `python3 -m pytest` full suite | Revert removes `core/nombres.py` + its test |
| G4 | Extract `core/limpiar.py` + inline fixture | PR 4 | `python3 -m pytest tests/test_limpiar.py` | `python3 -m pytest` full suite | Revert removes `core/limpiar.py` + its test |
| G5 | Engine store + lock (D1/D6) | PR 5 | `python3 -m pytest tests/test_rutas_engine.py -k "perfiles or lock or guardar or round_trip"` | `python3 -m pytest tests/test_rutas_engine.py -k concurrente` (real multiprocess fcntl) | Revert removes store/lock functions + their tests |
| G6 | Engine resolution + onboarding (D2/D3) | PR 6 | `python3 -m pytest tests/test_rutas_engine.py -k "resolver or emparejar or onboarding or precedencia"` | `python3 -m pytest` full suite | Revert removes resolution/onboarding + tests; store still functional |
| G7 | Engine mapping/relativization/context/env (D4/D5) | PR 7 | `python3 -m pytest tests/test_rutas_engine.py -k "relativizar or absolutizar or contexto or entorno or plataforma"` | `python3 -m pytest` full suite | Revert removes pure mapping functions + tests; profiles still persist |
| G8 | Final verification (success criteria) | PR 7 (last commit) | `python3 -m pytest` + `python3 -m py_compile` on all touched .py | `grep -rniE` audit command (below) | N/A — verification only, no code |

Note: G2 (≈460), G4 (≈410), G5 (≈440), G7 (≈460) each marginally exceed the
400-line budget; module+test pairing is mandated by config.yaml (extraction ships
both together), so slices stay per-module/per-concern.

## Group G1 — Foundation + Purity Guard (Phase 1: infrastructure; commit one)

- [x] 1.1 Create `SamanTools/__init__.py` with `__version__ = "2.0.0"` (SemVer source of truth).
- [x] 1.2 Create `SamanTools/core/__init__.py` (package marker, empty docstring ES).
- [x] 1.3 Create minimal `tests/conftest.py` (root path bootstrap only; NO nuke stub — spec core-purity-guard).
- [x] 1.4 RED: write `tests/test_no_import_nuke_en_core.py` — single tokenizer `detectar_violaciones(texto) -> list[str]` (D7: one compiled pattern; static anchored `^\s*(import|from)\s+`; dynamic unanchored `__import__|import_module`; one `_MODULOS_PROHIBIDOS` set nuke/nukescripts/PySide2/PySide6) + `auditar_tokens(raiz)` hygiene (case-insensitive tokens `wupm|LucidLink|HTLR|PCF` over `SamanTools/`+`tests/`, skip `__pycache__`; guard file self-exempt). Scenarios: `import nuke` fails; `from PySide6.QtWidgets import` fails; `importlib.import_module("nuke")` fails; `__import__('nuke')` fails; `import_module("os")` passes; comment `# import nuke` passes; banned token flagged; neutralized source passes.
- [x] 1.5 GREEN: implement the matcher + scan real `SamanTools/core/**/*.py`; iterate to green.
- [x] 1.6 Verify `python3 -m pytest` green from root (empty core) and `python3 -m py_compile` on touched .py; commit conventionally.

## Group G2 — Extract `entorno` (Phase 2: core implementation; PR 2)

- [x] 2.1 RED/port: `tests/test_entorno.py` from V1 pure subset lines 37–267 (28 functions / 30 cases ported); drop `import nuke`; neutralize fixtures to `estudio`/`L:/VFX/2026`/`CINE` (no real paths); DO NOT port lines 279–533 (nuke-stub helpers + integration, declared deferred — spec core-purity-guard). RED evidence: `pytest tests/test_entorno.py` → `ImportError: cannot import name 'entorno'` (module absent).
- [x] 2.2 GREEN: copy V1 `SamanTools/entorno.py` → `SamanTools/core/entorno.py` with logic intact; neutralize ONLY per contract in code/docstrings/comments (keep legacy `PREFIJOS=("TO_VFX","comp","FROM_VFX")` casing — `comp_SERVER_*`). Diff vs V1: only docstring + 5 path/token lines differ. GREEN evidence: `pytest tests/test_entorno.py` → 30 passed.
- [x] 2.3 Verify coverage of core-entorno scenarios with the ported names unchanged; full suite `python3 -m pytest` → 48 passed (18 guard + 30 entorno); `py_compile` OK on both touched .py; token audit `grep -rniE 'wupm|LucidLink|HTLR|PCF'` on both new files → 0 matches. Commit: `feat(core): extract entorno module (G2)`.

## Group G3 — Extract `nombres` (Phase 2; PR 3)

- [x] 3.1 RED/port: `tests/test_nombres.py` from V1 (167l), neutralized to fictitious paths (`/Volumes/estudio/2026`, `L:/VFX/2026`, `CINE`); covers canonical parse, folder-chapter authoritative, malformed version to end, lowercase version uppercased, `comp_SAMAN`/`comp_OTRA` metadata, PNG version-less, bare basename, Windows backslashes, invalid never raises.
- [x] 3.2 GREEN: copy V1 `SamanTools/nombres.py` → `SamanTools/core/nombres.py`; neutralize; keep relative import `from .entorno import` (valid — D4 graph, entorno landed in G2).
- [x] 3.3 Verify suite green + `py_compile`; scenario `comp_OTRA` preserved untouched.

## Group G4 — Extract `limpiar` (Phase 2; PR 4)

- [x] 4.1 RED/port: `tests/test_limpiar.py` from V1; REPLACE `Review.gizmo` fixture with synthetic inline `.nk`-style sample exercising all three volatile knobs + legit knobs (fictitious only, no studio gizmo — spec core-limpiar).
- [x] 4.2 GREEN: copy V1 `SamanTools/limpiar.py` → `SamanTools/core/limpiar.py` (stdlib os/re only); verify no real tokens in docstrings.
- [x] 4.3 Verify scenarios: 3 knobs stripped, legit untouched, idempotent, BOM+CRLF preserved, latin-1 `0xE9` survives, unchanged→0 no temp, missing→`FileNotFoundError`, mixed-tree summary, ext filter; suite green; `py_compile`.

## Group G5 — Engine: profile store + lock (Phase 2; PR 5)

- [x] 5.1 RED: extend `tests/test_rutas_engine.py` (store+lock slice): missing file → `{}`; malformed → `ValueError`; atomic round-trip no temp leftovers; concurrent `guardar_perfiles` (`ana`/`ws1` + `pedro`/`ws2`) both persist via multiprocessing with start barrier on POSIX; lock exhausted → `TimeoutError`; `_lock_clase(plataforma)` factory covers fcntl/msvcrt/no-op branches.
- [x] 5.2 GREEN: `core/rutas_engine.py` — `leer_perfiles` (returns inner `perfiles` dict, D1), `guardar_perfiles` (wraps envelope, preserves unknown top-level keys, per-user merge — never blind replace, D1/D3), `crear_perfil_default(base)` (fictitious roots; base-shape slotting `/Volumes/`→macOS, `^[A-Za-z]:`→Windows, `/mnt/`→Linux, else all three), `_lock_perfiles(path)` context manager (sibling `path + ".lock"`, NEVER the os.replace target, D6).
- [x] 5.3 Iterate to green; `py_compile`. (No real paths — store roots fictitious.)

## Group G6 — Engine: resolution + onboarding (Phase 2; PR 6)

- [x] 6.1 RED: precedence tests (exact pair → user-only → hostname-only insertion order → `None` marker; every match same-shaped roots dict, D2); onboarding persists and second resolve returns it; determinism (`ana`/`ws1` twice → identical, spec core-rutas-engine).
- [x] 6.2 GREEN: `_emparejar_perfil(user, hostname, perfiles)` (clean D2 order), `resolver_perfil(user, hostname, path)` (miss → `asegurar_perfil(...)`: lock → fresh re-read → re-resolve → merge → atomic write → return; race-won returns winner, D3), `ruta_para_plataforma(perfil, so)` (`perfil.get(so)` → `None`, no raise), `asegurar_perfil` public-ish inner.
- [x] 6.3 Verify suite green; `py_compile`.

## Group G7 — Engine: mapping, relativization, context, env (Phase 2/3; PR 7)

- [ ] 7.1 RED: `relativizar` macOS → `[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk`; outside base unchanged; **Windows case/separator variants**: `l:\vfx\2026\CINE\TO_VFX\ep.nk` vs base `L:/VFX/2026` relativizes AND keeps output casing `CINE/TO_VFX` (D5 two-track: compare canonical copy, emit from separator-normalized original); precondition: no comparison on raw non-normalized strings; `absolutizar` uses injected base verbatim + forward slashes (drive-case-insensitive match); `get_context` → `{proyecto, plano, version, carpeta_salida, base, so}`, `carpeta_salida` starts `[getenv PROJECT_ROOT]`; `variables_entorno` → `PROJECT_ROOT` + `PYTHON_TO_VFX/PYTHON_COMP/PYTHON_FROM_VFX` from `reconstruir_rutas(base, proyecto)` filtered by `sufijo_so(so)`; `os.environ` unmutated (data-driven injector contract, D4). `get_context` overrides proyecto via `proyecto_desde_ruta(plato, base)` (injected base, deterministic).
- [ ] 7.2 GREEN: `_normalizar_para_comparar` (canonical STRING: `\`→`/`, strip, rstrip `/`, `.lower()` whole string), `relativizar` (prefix guard `clave_base + "/"` against canonical copy → slice separator-normalized original at `len(base_s)`, lstrip `/`), `absolutizar`, `get_context`, `variables_entorno` (never touches `os.environ`).
- [ ] 7.3 Full engine suite green; `py_compile`.

## Group G8 — Final verification (Phase 4: verification; last commit of PR 7)

- [ ] 8.1 Run `python3 -m pytest` from root on a machine without Nuke — full suite green (proposal success criteria 1).
- [ ] 8.2 `python3 -m py_compile` on EVERY touched `.py` under `SamanTools/` and `tests/` (config.yaml apply rule).
- [ ] 8.3 Real-token grep audit (proposal success criteria 4): `grep -rniE 'wupm|LucidLink|HTLR|PCF' SamanTools tests` → matches ONLY in the self-exempt `tests/test_no_import_nuke_en_core.py`; anything else fails the change.
- [ ] 8.4 Confirm no temp files left by engine tests; sibling `.lock` file may persist by design (D6); update commit list.

## Out of Scope (do NOT implement)

- `SamanTools/rutas.py` shim (future load-layer change; proposal traceability only).
- V1 `test_entorno.py` lines 279–533 (nuke-stub integration; deferred — spec core-purity-guard).
- UI/panels, `bootstrap/`, `vfxflow/`, `render/`; any `import nuke`/PySide in `core/`.