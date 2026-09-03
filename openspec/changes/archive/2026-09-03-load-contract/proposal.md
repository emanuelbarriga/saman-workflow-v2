# Proposal: load-contract

## Intent

Pure core; no Nuke visibility. Legacy comps call `rutas.actualizar(nuke.thisNode())`; TCL `[getenv PROJECT_ROOT]` must resolve. Deliver: V2 bootstrap, shim, injector.

## Scope

### In Scope

- `bootstrap/menu.py` (V1 copy): 11 V1 rules kept; marker `core/rutas_engine.py`; target `ui/menu.py`; distinct uninstall marker; coexistence documented.
- `SamanTools/rutas.py` shim: lazy `import nuke` in bodies; re-export pure constants (`SUFIJOS`, `KNOBS_RUTAS_BASE`, `KNOBS_VERSION_ACTUAL`, `_KNOBS_A_MIGRAR`); thin facades (`actualizar`, `es_nodo_rutas`, `aplicar_proyecto`, `refrescar_fuentes`); compat-only stubs; no `core/` edits.
- `ui/injector.py`: PURE `armar_estado_env(perfil, so, ruta_plato, base=None)` (base/so explicit, fixes gap #2286); THIN `aplicar_entorno(env)` + `registrar_callbacks()` (load: perfil→SO→`nuke.root().name()`→apply; save: idempotent re-assert).
- Store: `NUKE_PROFILES_PATH` → project-shared (studio setup; no real paths) → `~/.config/saman/nuke_profiles.json` → onboarding. `config_local.py` (gitignored) override.
- Precedence: injector primary (addOnScriptLoad first); knobChanged idempotent, same env contract.
- `ui/menu.py` minimal: callbacks + maintenance menu; no panels.
- Tests: `armar_estado_env` incl. base/so gap; shim import+delegation, node fake in test file only.

Extraction: `saman-nuke-tools` read-only.

### Out of Scope

Panels; `vfxflow/`; `render/`; single installer; `nodos/`; `cargar_scripts`; `core/` changes; migration execution.

## Capabilities

New (each → `openspec/specs/<name>/spec.md`): `load-bootstrap-contract`, `load-shim`, `load-injector`, `load-ui-menu`. Modified: None.

## Approach

V1 bootstrap copy, adapted probes + distinct marker; shim = delegation layer (lazy import); injector pure/thin split; store env/config-driven; V2 replaces V1 with consent.

## Affected Areas

| Area | Impact | What |
|------|--------|------|
| `bootstrap/menu.py` | New | V1 copy, adapted probes |
| `SamanTools/rutas.py` | New | Shim: constants, facades, stubs |
| `SamanTools/ui/{injector,menu}.py` | New | Env/callbacks + maintenance menu |
| `tests/` | New | injector + shim tests |
| `config_local.py` / `docs/` | New/Mod | Studio override; coexistence note |

## Risks

| Severity | Risk | Mitigation |
|----------|------|------------|
| HIGH | Auto-sync war; V1 uninstaller hits V2 bootstrap | Distinct marker; V2 replaces V1 with consent |
| HIGH | Double env source (injector vs knobs) | Injector-first; idempotent same contract |
| MED | `base=None` → `PROJECT_ROOT` unset | Explicit assembly; tested |
| MED | Top-level nuke import breaks pytest | Lazy import; test-local fake |
| LOW-MED | Scripts rescan orphaned | `PYTHON_*` to `__main__`; rescan deferred |
| LOW | Compat-only stubs keep dead surface | Documented compat-only |

## Rollback Plan

All files new/additive: `git revert` → core-only V2. Bootstrap removed via distinct marker; V1 `~/.nuke/menu.py` untouched.

## Dependencies

- `core-rutas-engine` (archived); `saman-nuke-tools` read-only.
- No PySide/nuke in tested paths.

## Success Criteria

- [ ] `python3 -m pytest` green (core + new tests).
- [ ] Shim imports headless (no stub); `actualizar()` tested with local fake.
- [ ] `armar_estado_env` covers `base=None`, no #2286 gap.
- [ ] Bootstrap probes marker, execs `ui/menu.py`; 11 V1 rules intact.
- [ ] Precedence documented in design: injector first, knobChanged idempotent.