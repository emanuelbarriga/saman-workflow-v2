# Proposal: Extra Spaces (espacios-extra)

## Intent

Artists need per-user EXTRA spaces (3D, PREVIEW, MATTEPAINT) beyond canonical TO_VFX/COMP/FROM_VFX. Gap: `variables_entorno` iterates only `_ESPACIOS` (`rutas_engine.py:530`); `preparar_cambio_base` rejects unknown keys (`path_manager.py:312`); deletion is impossible (merge kernel adds/updates only). New V2 code on extracted modules (saman-nuke-tools). Zero migration: FLAT `{login:{ESPACIO:{SO:root}}}`.

## Scope

### In Scope (first slice: engine + helper + widget + tests)
- **Engine**: `variables_entorno` iterates all keys — canonical first (fallback unchanged), extras sorted; missing extra root → key omitted, never `""`. Sanitizer `_clave_env_para_espacio`: UPPER, `A-Z0-9`, space→`_`, collapse, strip, empty→reject. Lock-guarded `eliminar_espacio_store` (mirrors `renombrar_perfil_store`).
- **Helper**: `sanitizar_espacio_extra`; `raices_para_so` + extras; `preparar_cambio_base` accepts profile-known keys before TODOS branch (two tests preserved); add/remove helpers.
- **Widget**: canonical section intact; separate subtree — rows `[name][path][Buscar][OK][-]`, per-row OS selector, `[ + Agregar espacio extra ]`; `campos_avanzados` order assertion stays green.
- **Tests**: env, sanitizer, removal race, omission; helper add/remove; panel wiring; `_ESPACIOS` agreement test (4 modules; `PREFIJOS` V1-cased, excluded).

### Out of Scope / Non-Goals
- `entorno` markers, `raiz_proyecto_desde_ruta`, `_espacio_prefijado`, `get_context`: canonical-only.
- Extras never become PROJECT_ROOT cut markers (R6); plate under extra root falls to base/current-SO root.
- `injector.py` (no snippet), `menu.py`, shim `rutas.py`, V1 knobs, per-space rename, legacy-shape changes.

## Capabilities

**New Capabilities:** None — no new main spec files.

**Modified Capabilities:**
- `core-rutas-engine`: all-key env, `eliminar_espacio_store`, sanitizer.
- `panel-path-manager-helper`: extra validation + add/remove; widened accept-list.
- `panel-path-manager-widget`: extra subtree.
- `load-injector`, `panel-path-manager-menu`, `core-entorno`: no delta.

## Approach

Flat generalization (Option A, binding): reuse key-agnostic merge kernel; env via existing `aplicar_entorno`; only new primitive is lock-guarded removal; UI = fixed canonical + separate extras subtree.

## Risks (R1–R8)

- R1 → lock-guarded `eliminar_espacio_store`, race-tested.
- R2 → pinned: canonical dupes (case-insensitive), literal `PROJECT_ROOT`, intra-extra dupes, `hosts`/`default`.
- R3 → extras-only legacy replace documented; UI prevents by construction.
- R4 → profile-known check before TODOS branch; both tests stay green.
- R5 → separate widget subtree; canonical assertions untouched.
- R6 → non-goal: extras env-only, never cut markers.
- R7 → `_ESPACIOS` agreement test across 4 modules.
- R8 → sanitizer blocks path-like/JSON-reserved names; fictitious fixtures only.

## Business Rules / Edge Cases

- Env key `PYTHON_` + sanitized name (stored key): `3D`→`PYTHON_3D`, `MATTE PAINT`→`PYTHON_MATTE_PAINT`.
- Missing extra root → omitted key, disconnected row; row OS selector switches.
- Canonical presence stays the shape criterion; deterministic output: canonical first, extras sorted.
- `/` impossible in names → no name/path ambiguity reaches `preparar_cambio_base`.
- Spec confirmations: reject `hosts`/`default` (recommended); R3 warning for hand-edited stores.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `SamanTools/core/rutas_engine.py` | Modified | env, sanitizer, remove |
| `SamanTools/ui/path_manager.py` | Modified | validation, accept-list, add/remove |
| `SamanTools/ui/path_manager_panel.py` | Modified | extra subtree |
| `tests/test_rutas_engine.py`, `test_path_manager*.py` | Modified | coverage + agreement test |

## Rollback Plan

Additive: revert the commit restores prior behavior; stores with extra keys remain valid JSON — no migration.

## Dependencies

Key-agnostic kernel + lock already shipped; none external.

## Success Criteria

- [ ] `PYTHON_<EXTRA>` sorted after canonical; missing root omits key; engine never mutates `os.environ`.
- [ ] `eliminar_espacio_store` removes only target key, race-safe.
- [ ] Add/remove/OS-select persist; canonical suite (incl. `campos_avanzados` order) green.
- [ ] Agreement test passes; sanitizer rejects all pinned cases.