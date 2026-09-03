# Proposal: perfil-por-usuario

## Intent

V2's profile model (user+hostname, one base per OS, `hosts`/`default` ladder) is wrong for the studio: a profile is a **username** with **independent per-platform roots for the three spaces** (`TO_VFX`/`COMP`/`FROM_VFX` — V1 ARTIST model). Schema is rewritten breaking-but-regenerative (V2 pre-release), store moves to `{project_root}/.saman/nuke_profiles.json`, Path Manager gets a selector applying the chosen user's roots at once.

## Scope

### In Scope
- Engine: schema `{user: {space: {os: root}}}`, hostname ladder removed, merge/onboarding rewritten, `get_context`/`variables_entorno` from space roots, `os.makedirs` on first write.
- Entorno: `raiz_proyecto_desde_ruta(ruta, so=None)` — structural cut at first `TO_VFX|COMP|FROM_VFX` marker; `proyecto_desde_ruta`+base secondary. `reconstruir_rutas` = fallback only; V1 knob contract untouched.
- Injector: store chain project-first (`.saman/` → `NUKE_PROFILES_PATH` → `config_local` → home); env source = space roots.
- Helper: `listar_perfiles(ruta_store)`, `preparar_seleccion_perfil(...)`.
- Widget: profile combo (refresh on open), apply-on-select via `cachear_env`+`aplicar_entorno`+refresh Reads.
- Legacy shape (`hosts`/`default`) → regenerate store + warning.
- Tests: fixtures legacy → new schema. Docs: store-chain. Extraction: V1 `rutas.py` marker + `Rutas.nk`; rest new V2.

### Out of Scope
Export Manager, vfxflow/render, mass relativization (deferred), real-data migration (none), menu spec.

## Capabilities

### New Capabilities
None — entorno candidate is an ADDED requirement of existing `core-entorno`, not a new capability.

### Modified Capabilities
- `core-rutas-engine`: store schema, user-only resolution (ladder removed), per-space×per-platform mapping, onboarding, context/`PROJECT_ROOT` semantics, lazy `.saman/`.
- `load-injector`: store chain (project first), env from space roots.
- `panel-path-manager-helper`: user-only writes + ADDED listing/selection.
- `panel-path-manager-widget`: combo + apply-on-select + Reads refresh.
- `core-entorno` (candidate ADDED): `raiz_proyecto_desde_ruta`.

## Approach

1. Rewrite schema; ladder → `perfiles.get(user)`; legacy = unknown → re-onboard + warn.
2. Env: `PYTHON_TO_VFX/COMP/FROM_VFX` = space root for current OS; `PROJECT_ROOT` = that root truncated to project.
3. Store chain project-first; `.saman/` lazy on first write under lock.
4. Combo lists users; select applies env + refreshes Reads.

## Affected Areas

| Area | Impact | Change |
|------|--------|--------|
| `core/rutas_engine.py` | Modified | schema, ladder, merge, onboarding, env, `makedirs` |
| `core/entorno.py` | Modified | ADDED `raiz_proyecto_desde_ruta` |
| `ui/injector.py` | Modified | store chain, env source |
| `ui/path_manager.py` | Modified | listing, selection, writes |
| `ui/path_manager_panel.py` | Modified | combo, apply, Reads refresh |
| `docs/ARQUITECTURA-V2.md` | Modified | chain order |
| `tests/test_*.py` ×3 | Modified | fixtures new schema |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| R1 Test churn (~20 fixtures) | High | migration in same task; budgeted |
| R2 Dead-mount hang on `.saman/` probe | Med | reuse `estado_unidad` cache pattern |
| R3 Env staleness on failed select | Low | idempotent apply, `ValueError` guard |
| R4 Silent behavior change (project store wins, foreign-host gone) | Med | release note + warn |
| R5 Public-repo hygiene | Low | fictitious fixtures |
| R6 `PROJECT_ROOT` ambiguity | Med | cut primary + fallback chain |

## Rollback Plan

`git revert` restores code/specs. Regenerated stores are dev data: re-seed from V1; reset warned.

## Dependencies

None external (stdlib core; PySide6 widget; pytest). Decisions D1–D6 bound from exploration.

## Success Criteria

- [ ] Suite green after fixture migration
- [ ] Selector lists usernames from the store
- [ ] Selecting applies env + refreshes Reads at once
- [ ] Legacy store regenerates with warning
- [ ] `PROJECT_ROOT` = project root via structural cut