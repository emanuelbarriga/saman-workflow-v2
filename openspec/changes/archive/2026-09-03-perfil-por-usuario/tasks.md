# Tasks: Perfil por usuario

## Review Workload Forecast

| Slice | Scope | Est. lines |
|---|---|---|
| S1 | engine 3x3 + ladder out + entorno cut + fixture rewrite (~20) | ~650 |
| S2 | injector chain + probe + env + menu call-sites | ~250 |
| S3 | helper listing/selection/cambio/onboarding | ~280 |
| S4 | widget combo + apply + Reads refresh | ~320 |
| S5 | shim proof + ARQUITECTURA docs | ~80 |
| Total | breaking core change | ~1580 |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| S1 engine+entorno | PR 1 | pytest tests/test_rutas_engine.py tests/test_entorno.py | pytest only — core is pure stdlib | revert core/* + test rewrites |
| S2 injector+menu | PR 2 | pytest tests/test_injector.py tests/test_menu.py | pytest + monkeypatch | revert ui/injector.py ui/menu.py |
| S3 helper | PR 3 | pytest tests/test_path_manager.py | pytest — helper never imports nuke/PySide | revert ui/path_manager.py |
| S4 widget | PR 4 | pytest tests/test_path_manager_panel.py | pytest-qt headless + fakes | revert ui/path_manager_panel.py |
| S5 docs/verify | PR 5 | full pytest + py_compile | full suite | revert docs only |

## S1 — Engine + Entorno

- [x] 1.1 RED: rewrite tests/test_rutas_engine.py fixtures to 3x3 `_perfil_por_defecto()`, deleting ~20 ladder fixtures in the SAME slice (R1/AD9); add test_entorno cases for `raiz_proyecto_desde_ruta`: 4 delta scenarios + no-marker, base-sola, `.saman` non-marker, Windows
- [x] 1.2 GREEN core/entorno.py: pure `raiz_proyecto_desde_ruta` (AD4) — slash normalize, first case-insensitive marker segment, trailing sep strip, `None` on no-marker/empty; `.saman` NOT a marker
- [x] 1.3 GREEN core/rutas_engine.py: 3x3 `leer/guardar_perfiles` — envelope validation, atomic temp + `os.replace`, fcntl/msvcrt lock over read-merge-write, <=2s timeout -> retry -> `TimeoutError`, lazy `.saman/` makedirs under lock, never on read
- [x] 1.4 GREEN core/rutas_engine.py: delete ladder (`_emparejar_perfil`, `_merge_perfil`, hosts branch, `ruta_para_plataforma`); add `detectar_forma_perfil` -> "nuevo"|"legacy", `ruta_para_espacio`, `_espacio_prefijado` (AD1/AD2)
- [x] 1.5 GREEN core/rutas_engine.py: `resolver_perfil` user-only (`perfiles.get`, unknown -> onboarding, never raise/None); `asegurar_perfil`/`crear_perfil_default` 3x3; legacy writes regenerate flagged
- [x] 1.6 GREEN core/rutas_engine.py: `get_context` returns `{proyecto, plano, version, carpeta_salida, espacio, so}` — espacio + SO of the space root prefixing the plate; proyecto via structural cut with plate-token fallback; `carpeta_salida="[getenv PROJECT_ROOT]/COMP/"` (AD3)
- [x] 1.7 GREEN core/rutas_engine.py: `variables_entorno(contexto, perfil=None)` — PROJECT_ROOT via cut (NOT base), PYTHON_* = space roots for current SO; missing space -> `reconstruir_rutas` sibling fallback; unresolvable key OMITTED, never `""` (AD7); pure, no os.environ mutation
- [x] 1.8 Gate: py_compile every touched .py; full suite green

## S2 — Injector + Menu

- [x] 2.1 RED tests/test_injector.py + tests/test_menu.py: chain precedence, probe anti-hang, space-root env, purity, untitled fallback, menu root passing
- [x] 2.2 GREEN ui/injector.py: `obtener_ruta_store(raiz_proyecto=None)` — `{raiz}/.saman/` -> `NUKE_PROFILES_PATH` -> `SamanTools.config_local` (scoped module/locally read .json, NEVER bare top-level module, AD5) -> home; project store always wins
- [x] 2.3 GREEN ui/injector.py: `_probe_store` = `estado_unidad(dirname)["conectado"] and os.path.isfile` + 10s cache; never creates `.saman/` on read (AD6)
- [x] 2.4 GREEN ui/injector.py: `armar_estado_env(perfil, so, ruta_plato, base=None)` — cut PROJECT_ROOT -> base -> current-SO space root; PYTHON_* from space roots; pure
- [x] 2.5 GREEN ui/menu.py: `_resolver_contexto_carga` passes raiz_proyecto; `resolver_perfil` sin hostname (AD10 call-sites)
- [x] 2.6 Gate: py_compile; suite green

## S3 — Helper

- [x] 3.1 RED tests/test_path_manager.py: hostname out; listing sorted/empty; selection no-write; `ValueError` no-write; cambio-base preserves other spaces/users; onboarding; regen flag read-only
- [x] 3.2 GREEN ui/path_manager.py: `listar_perfiles` (sorted, `[]` on missing/corrupt), `preparar_seleccion_perfil` (`ValueError`, never onboard/write), `preparar_cambio_base` (READ-MERGE-WRITE via `guardar_perfiles`, spaces independent), `preparar_onboarding` via `asegurar_perfil`, `estado_panel`+`regeneracion`, `estado_unidad` on current-SO space root
- [x] 3.3 Gate: py_compile; suite green

## S4 — Widget

- [x] 4.1 RED tests/test_path_manager_panel.py (pytest-qt + fakes): combo refresh on open; select -> env + Reads refresh; stale `ValueError` no partial env; legacy warning; onboarding once; change-base no direct widget env write; headless degrade
- [x] 4.2 GREEN ui/path_manager_panel.py: combo (default ambient user), apply-on-select -> `cachear_env` + `aplicar_entorno` + `_refrescar_reads()`, `abrir_dialogo(usuario)`, PySide2/PySide6 dual import, hostname out
- [x] 4.3 Gate: py_compile; suite green

## S5 — Docs / Verify

- [x] 5.1 docs/ARQUITECTURA-V2.md: store-chain order (66-68) project-first + R4 release note (project store wins; foreign-host fallback gone; `carpeta_salida` token)
- [x] 5.2 Proof D8: tests/test_shim.py passes unchanged; `SamanTools/rutas.py` untouched
- [x] 5.3 Verify: full pytest + py_compile all touched files; mark tasks done