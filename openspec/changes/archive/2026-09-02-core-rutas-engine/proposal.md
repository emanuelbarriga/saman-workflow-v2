# Proposal: Core Rutas Engine — V2 Foundation

## Intent

Build the V2 heart first: `SamanTools/core/rutas_engine.py`, a pure-stdlib path engine (JSON profiles, tri-platform mapping, `[getenv PROJECT_ROOT]` relativization, context API, onboarding), plus the pure modules sustaining it, extracted from V1. Legislates the UI/core boundary via a guard test from commit one. Starts here, not at bootstrap: it is the single dependency of future panels; no UI exists to load yet.

## Scope

### In Scope

- `SamanTools/__init__.py` — `__version__ = "2.0.0"` (SemVer source of truth; V1 is 1.12.0).
- Extraction by copy:

| New module | Source (V1) |
|---|---|
| `SamanTools/core/entorno.py` | `SamanTools/entorno.py` (223l) |
| `SamanTools/core/nombres.py` | `SamanTools/nombres.py` (164l); `from .entorno import` stays valid |
| `SamanTools/core/limpiar.py` | `SamanTools/limpiar.py` (135l) |

- `SamanTools/core/rutas_engine.py` (new): JSON profile store (`nuke_profiles.json`, injectable path); resolve profile by user/hostname; per-platform base root; absolute↔`[getenv PROJECT_ROOT]` relativization (string-level); `get_context()` → project/shot/version/output dir; unknown-user onboarding.
- Guard `tests/test_no_import_nuke_en_core.py` (regex on import lines only over `core/`); minimal `tests/conftest.py` (no nuke stub); ported + new tests; green pytest; `py_compile` per touched file.

### Out of Scope

UI/panels. `bootstrap/` + load contract. `vfxflow/`, `render/`. V1 `rutas.py` shim (no saved comps in V2). Nuke-stub integration tests; `nodos/` gizmos.

## Traceability: future `SamanTools/rutas.py` shim (NOT implemented here)

V1 saved comps embed Rutas nodes whose `knobChanged` expression runs `from SamanTools import rutas` (V1 `Rutas.nk:12`). V2 does NOT install over V1 yet, so no shim is needed in this change. BUT the moment V2's load layer replaces the V1 checkout on artist machines, that import MUST resolve: plan a re-export shim (`SamanTools/rutas.py` delegating to `core.rutas_engine`) in the same change that introduces the V2 load contract. Recorded here so the future migration does not regress saved comps. Same applies to the `Rutas.gizmo`/`Rutas.nk` mirror invariant: any future node migration regenerates the `.gizmo` from the `.nk` block in the same commit.

## Open Decision (copy-intact vs public repo)

V1 `entorno.py` hardcodes REAL roots in code: `rutas_base()` → `["/Volumes/wupm/2026", ...]`, `L:/2026`, `/mnt/wupm/2026` (entorno.py:67-77), plus real tokens (wupm, LucidLink, HTLR, PCF) in docstrings/fixtures. Public-repo policy outranks byte-copy. **Default**: neutralize to fictitious paths (`/Volumes/estudio/2026`, `L:/2026`, `/mnt/estudio/2026`); logic untouched. Confirm at spec.

## Capabilities (all New — `openspec/specs/` empty)

- `core-entorno`: SO/unit-state/base-root detection. `core-nombres`: plate parsing. `core-limpiar`: volatile-knob sanitizer. `core-rutas-engine`: profiles, mapping, relativization, context, onboarding. `core-purity-guard`: import-guard enforcement.

## Approach

Copy, don't rewrite — one documented neutralization (above). Port only pure tests: `test_entorno` splits (~23 pure ported; ~19 nuke-stub integration tests at test_entorno.py:304-533 deferred); `test_limpiar` gizmo regression uses an inline sample. Engine TDD with injected user/hostname/base.

## Affected Areas

| Area | Impact |
|------|--------|
| `SamanTools/__init__.py`, `SamanTools/core/{entorno,nombres,limpiar,rutas_engine}.py` | New |
| `tests/test_{entorno,nombres,limpiar,rutas_engine}.py`, `tests/conftest.py`, `tests/test_no_import_nuke_en_core.py` | New |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Real path/token leak into public repo | High | Neutralization mandated; grep gate `wupm\|LucidLink\|HTLR` |
| Extracted modules diverge from V1 | Med | Copy + ported tests together; no silent renames |
| Ambient getpass/socket → machine-dependent tests | Med | Injectable user/hostname/base in API |
| Ported subset silently drops coverage | Med | Declared pure-vs-stub split; diff review |

## Rollback Plan

Per-commit revert; engine lands after extracted modules. No UI/installer depends on it yet — safe to delete pre-UI.

## Dependencies

V1 frozen at current HEAD (read-only). Python 3.14 + pytest 9 (detected).

## Success Criteria

- [ ] `python3 -m pytest` green from root.
- [ ] `py_compile` clean on every touched .py.
- [ ] Guard fails on `import nuke`/PySide in `core/`.
- [ ] Grep audit: no real studio path/token in `SamanTools/` or `tests/`.