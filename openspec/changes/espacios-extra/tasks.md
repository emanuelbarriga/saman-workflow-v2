# Tasks: Extra Spaces (espacios-extra)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~990 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 (stacked) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Scope: engine + helper + widget + tests only; injector/menu/shim untouched (no new snippet).

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Engine env core | PR 1 | `pytest tests/test_rutas_engine.py -k "clave_env or env"` | N/A — pure | revert engine |
| 2 | Engine removal + race | PR 2 | `pytest tests/test_rutas_engine.py -k "eliminar"` | Barrier(2) multiprocess | revert op |
| 3 | Helper add/remove | PR 3 | `pytest tests/test_path_manager.py -k "extra or sanitizar or raices"` | N/A — pure | revert helper |
| 4 | Widget extras subtree | PR 4 | `pytest tests/test_path_manager_panel.py -k "extra or grupo"` | qtbot + env spy | revert subtree |
| 5 | Agreement + injector tests | PR 5 | `pytest tests/test_injector.py -k "extras"` | N/A — static imports | tests only |

## Phase 1: Engine env core (PR 1)

- [x] 1.1 RED: sanitizer — `3D`→`3D`, `matte paint`→`MATTE_PAINT`; ValueError: `foo/bar`, `{}`, `---`, empty, `HOSTS`, `DEFAULT` (R2/R8)
- [x] 1.2 RED: env extras — sorted after canonical; missing/unsanitizable key omitted, never `""` (D4); sibling fallback intact; same-inputs→same-dict
- [x] 1.3 GREEN: add `_clave_env_para_espacio` near `_ESPACIOS` (rutas_engine.py:72)
- [x] 1.4 GREEN: rewrite `variables_entorno` loop (:530-539): `list(_ESPACIOS) + sorted(extras)`; `except ValueError: continue`
- [x] 1.5 Guard: env tests (:677-734) green unmodified

## Phase 2: Engine removal (PR 2)

- [x] 2.1 RED: `eliminar_espacio_store` — target key only removed; absent key → no-op `_bytes_store`; unknown user → ValueError; canonical → ValueError (D1)
- [x] 2.2 RED: race — Barrier(2) workers remove `3D`/`PREVIEW`; both persist, canonicals intact, no temp files (skipif win32)
- [x] 2.3 GREEN: implement mirroring `renombrar_perfil_store` (:338-356): lock, re-read, guards, pop, `_escribir_perfiles`

## Phase 3: Helper (PR 3)

- [x] 3.1 RED: `sanitizar_espacio_extra` — valid; ValueError: empty, canonical dup, `hosts`/`default`, `PROJECT_ROOT`, intra-extra dup, path-like/JSON-reserved
- [x] 3.2 RED: `raices_para_so` extras; `preparar_cambio_base` accepts profile-known extra (env `PYTHON_3D`); `_copia_con_slot` keeps extras (D5); unknown → ValueError; add/remove return data, no `os.environ`
- [x] 3.3 GREEN: `sanitizar_espacio_extra(nombre, perfil)` delegating to engine sanitizer
- [x] 3.4 GREEN: `raices_para_so` (:190-193) → canonical + sorted extras
- [x] 3.5 GREEN: `_copia_con_slot` (:148-154) iterates all `perfil` keys (D5)
- [x] 3.6 GREEN: `preparar_cambio_base` (:312-325): `_ESPACIOS` → `in perfil` → `_es_ruta_aparente` → ValueError (R4)
- [x] 3.7 GREEN: `agregar_espacio_extra(usuario, ruta_store, so, nombre, nueva_ruta)` + `eliminar_espacio_extra(usuario, ruta_store, espacio, so)` (D7); R3 legacy docstring
- [x] 3.8 Guard: `:459`/`:477` unmodified

## Phase 4: Widget (PR 4)

- [ ] 4.1 RED: rows render name+root+semaforo; OS switch → disconnected/back; add persists + env via `_spy_aplicar_env` (:203); invalid `hosts` → nuke.message, no write; `[-]` removes + env; `:537-540` + toggle (:501-522) untouched
- [ ] 4.2 GREEN: `self.grupo_extras` after `grupo_avanzado` (:263): rows `[name][path][Buscar][OK][-]`, per-row OS combo (D2), add-row validated name (D8), `[+ Agregar]`, OS label; semaphores via `estado_unidad`
- [ ] 4.3 GREEN: wire `_alternar_avanzado` + OK/add/`[-]` to helpers; env only via `cachear_env`+`aplicar_entorno`; canonical section (:229-263) byte-identical

## Phase 5: Agreement + injector (PR 5)

- [ ] 5.1 RED: 4-module `_ESPACIOS` equality; `entorno.PREFIJOS` excluded (V1 `comp`); PySide guard
- [ ] 5.2 RED: `test_injector.py` — `armar_estado_env` extras sorted, missing omitted (1-2 tests)
- [ ] 5.3 Verify: full `python3 -m pytest` green; zero production delta beyond engine/helper/widget