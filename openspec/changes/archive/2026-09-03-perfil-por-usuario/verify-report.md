```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:06698a8d0929fb03045d6054dd683169139d5c745d4e40bbd19092d7ccbdb463
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 24/24
scenarios: 42/42
test_command: QT_QPA_PLATFORM=offscreen python3 -m pytest -q
test_exit_code: 0
test_output_hash: sha256:26bc2781196e37c19ca8aeba0f62fb07800ae0a7d3d5ff01d87b2423dab3c59b
build_command: python3 -m py_compile SamanTools/core/rutas_engine.py SamanTools/core/entorno.py SamanTools/ui/injector.py SamanTools/ui/path_manager.py SamanTools/ui/path_manager_panel.py SamanTools/ui/menu.py SamanTools/rutas.py
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: perfil-por-usuario
**Version**: deltas S1-S5 (local change, 5 spec files)
**Mode**: Standard + Strict TDD (config `testing.strict_tdd: true`, runner `python3 -m pytest`)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 23 |
| Tasks complete | 23 (S1 ×8, S2 ×6, S3 ×3, S4 ×3, S5 ×3) |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed — `python3 -m py_compile` sobre los 7 .py de runtime del cambio — exit 0 (salida vacía)
**Tests**: ✅ 350 passed (0 failed, 0 skipped) en 3.03 s — `QT_QPA_PLATFORM=offscreen python3 -m pytest -q`
**Coverage (changed files)**: core/rutas_engine.py 90%, core/entorno.py 90%, ui/injector.py 88%, ui/path_manager.py 96%, ui/path_manager_panel.py 83%, ui/menu.py 76% — media 87%; threshold config 0

### Spec Compliance Matrix — core-rutas-engine (9 reqs, 12 scen)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Injectable, deterministic API (hostname OUT) | same inputs, same outputs | `test_resolver_perfil_determinismo_mismos_inputs_mismos_outputs` / `test_contexto_determinismo_inputs_identicos` | ✅ COMPLIANT |
| JSON profile store | missing file starts empty | `test_leer_perfiles_archivo_inexistente_devuelve_vacio` | ✅ COMPLIANT |
| JSON profile store | malformed JSON fails loudly | `test_leer_perfiles_json_malformado_lanza_valueerror` (+raiz no objeto) | ✅ COMPLIANT |
| JSON profile store | atomic round-trip | `test_guardar_perfiles_round_trip_sin_temporales` | ✅ COMPLIANT |
| JSON profile store | concurrent onboarding no lost profiles | `test_guardar_concurrente_multiproceso_no_pierde_perfiles` / `test_onboarding_concurrente_mismo_usuario_no_duplica` (multiproceso real con lock read-merge-write) | ✅ COMPLIANT |
| JSON profile store | legacy entry regenerates with warning flag | `test_guardar_perfiles_reemplaza_forma_legacy` / `test_asegurar_perfil_legacy_regenera_flagged` / `test_estado_panel_legacy_flag_true_sin_escribir` (flag solo-lectura) | ✅ COMPLIANT |
| Profile resolution by user (RENAMED, ladder out) | — | `resolver_perfil(user, path)` sin hostname; ladder muerto grep-clean (`_emparejar_perfil`/`_merge_perfil`/`ruta_para_plataforma` ausentes); `test_firmas_publicas_sin_hostname` | ✅ COMPLIANT |
| Profile resolution by user | known user resolves | `test_resolver_perfil_usuario_conocido_devuelve_3x3` | ✅ COMPLIANT |
| Profile resolution by user | absent user triggers onboarding | `test_resolver_perfil_desconocido_onboarding_persiste_y_segundo_resolve` | ✅ COMPLIANT |
| Per-space tri-platform mapping (RENAMED) | — | `ruta_para_espacio(perfil, espacio, so)`; `ruta_para_plataforma` eliminada | ✅ COMPLIANT |
| Per-space tri-platform mapping | independent space roots map per platform | `test_ruta_para_espacio_cada_combinacion` (param 3×3) + `test_ruta_para_espacio_combinacion_ausente_devuelve_none` | ✅ COMPLIANT |
| Context API | context from a space root | `test_contexto_desde_raiz_de_espacio_comp` (proyecto/plano/version/token carpeta_salida) + `test_contexto_windows_plato_deriva_espacio_y_so` + `test_contexto_carpeta_salida_siempre_token_comp` | ✅ COMPLIANT |
| Environment variables exposure | env contract: cut PROJECT_ROOT + space roots + purity | `test_env_contracto_corte_project_root_y_raices_del_perfil` + `test_env_no_muta_os_environ` + `test_env_espacio_faltante_usa_sibling_y_el_presente_usa_perfil` + `test_env_clave_irresoluble_se_omite_nunca_vacia` (nunca `""`; AD7) | ✅ COMPLIANT |
| Unknown-user onboarding | onboarding persists the profile | `test_resolver_perfil_desconocido_onboarding_persiste_y_segundo_resolve` + `test_asegurar_perfil_*` (slotting linux/windows, carrera ganada) | ✅ COMPLIANT |

### Spec Compliance Matrix — core-entorno (1 req, 4 scen)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Project root from structural cut | cut at COMP | `test_raiz_proyecto_corte_en_comp` | ✅ COMPLIANT |
| Project root from structural cut | cut at FROM_VFX | `test_raiz_proyecto_corte_en_from_vfx_otra_base` | ✅ COMPLIANT |
| Project root from structural cut | no marker returns None | `test_raiz_proyecto_sin_marcador_devuelve_none` | ✅ COMPLIANT |
| Project root from structural cut | Windows slashes normalize | `test_raiz_proyecto_windows_normaliza_slashes` | ✅ COMPLIANT |

Extras de tarea S1 green: `test_raiz_proyecto_saman_no_es_marcador`, `base_sola`, `case_insensitive`, `segmento_entero`, `vacia`, `trailing`, `marcador_primera_posicion` (7 tests adicionales, todos pasan). Función pura stdlib (sin filesystem).

### Spec Compliance Matrix — load-injector (2 reqs, 6 scen)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Pure environment assembly | comp under space root yields cut env | `test_env_completo_bajo_root` | ✅ COMPLIANT |
| Pure environment assembly | untitled script still gets a root | `test_untitled_gap_2286_inyecta_base` (+ `test_ruta_fuera_de_toda_root_inyecta_base`, `test_sin_corte_sin_base_*`) | ✅ COMPLIANT |
| Pure environment assembly | deterministic across calls | `test_determinista_entre_llamadas` | ✅ COMPLIANT |
| Pure environment assembly | purity — no os.environ mutation | `test_no_muta_os_environ_ni_main` | ✅ COMPLIANT |
| Profile store resolution | project store wins | `test_store_proyecto_gana_siempre` | ✅ COMPLIANT |
| Profile store resolution | env var is the fallback without .saman | `test_store_proyecto_sin_archivo_cae_al_env` + `test_env_var_gana` | ✅ COMPLIANT |

Probe anti-hang (AD6): `test_probe_mount_muerto_cortocircuita_sin_isfile`, `test_probe_reutiliza_cache_estado_unidad` (cache 10 s), `test_probe_no_crea_saman_en_lectura` (nunca crea `.saman/` en read). config_local scoped (AD5): `test_config_local_modulo_gana` / `test_config_local_json_hermano_gana` / `test_config_local_sin_valor_cae_a_home` + `from .. import config_local` (nunca módulo en raíz; gitignored).

### Spec Compliance Matrix — panel-path-manager-helper (7 reqs, 12 scen)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Pure, deterministic data layer | same inputs, same outputs, no env access | `test_estado_panel_mismos_inputs_mismos_outputs` + `test_estado_panel_no_muta_os_environ_desconocido` + `test_firmas_publicas_sin_hostname` + `test_helper_puro_sin_imports_prohibidos` | ✅ COMPLIANT |
| Active profile read with onboarding marker | known user resolves | `test_estado_panel_usuario_conocido_devuelve_3x3` | ✅ COMPLIANT |
| Active profile read with onboarding marker | unknown user returns marker without write | `test_estado_panel_desconocido_marcador_sin_escribir` + `test_detectar_desconocido_*` | ✅ COMPLIANT |
| Active profile read with onboarding marker | legacy flags regeneration without write | `test_estado_panel_legacy_flag_true_sin_escribir` (+ false nuevo/ausente) | ✅ COMPLIANT |
| Unit status for the current-OS base | connected unit | `test_estado_panel_unidad_conectada` | ✅ COMPLIANT |
| Unit status for the current-OS base | disconnected unit | `test_estado_panel_unidad_desconectada` | ✅ COMPLIANT |
| Change-base prepares merged roots and env delta | macOS COMP persists, others intact | `test_cambio_base_por_espacio_cambia_solo_ese_slot` + `test_cambio_base_por_espacio_otro_espacio_y_so_windows` | ✅ COMPLIANT |
| Onboarding preparation | onboarding persists the user profile | `test_onboarding_persiste_perfil_3x3` + `test_onboarding_slotting_linux` | ✅ COMPLIANT |
| Profile listing | sorted users from the store | `test_listar_perfiles_orden_estable` | ✅ COMPLIANT |
| Profile listing | missing store is empty | `test_listar_perfiles_store_ausente_vacio` (+ corrupto) | ✅ COMPLIANT |
| Profile selection | selection returns env data without writing | `test_seleccion_devuelve_perfil_env_unidad_sin_escribir` (store bytes sin cambios) + `test_seleccion_env_so_windows` | ✅ COMPLIANT |
| Profile selection | missing user raises without writing | `test_seleccion_usuario_inexistente_raise_sin_escribir` + `test_seleccion_legacy_raise_no_es_seleccion` | ✅ COMPLIANT |

### Spec Compliance Matrix — panel-path-manager-widget (5 reqs, 8 scen)
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Thin dialog bound to the helper | profile and status rendered from helper data | `test_dialogo_conocido_muestra_raiz_estado_y_combo` + `test_panel_env_solo_via_injector` (sin escritura directa os.environ; grep del panel limpio) | ✅ COMPLIANT |
| Onboarding flow | new user submits base and env propagates | `test_onboarding_submit_asegura_una_vez_y_aplica_env` | ✅ COMPLIANT |
| Change-base flow | change base re-applies env | `test_cambio_base_por_espacio_persiste_y_aplica_env` | ✅ COMPLIANT |
| Modal entry point | no GUI degrades silently | `test_abrir_dialogo_sin_gui_no_levanta` + `test_abrir_dialogo_sin_pyside_no_levanta` | ✅ COMPLIANT |
| Modal entry point | open refreshes the profile list | `test_abrir_dialogo_refresca_lista_perfiles_al_abrir` | ✅ COMPLIANT |
| Profile selector combo | selecting a profile applies env and refreshes Reads | `test_seleccion_aplica_env_y_refresca_reads` (cachear_env+aplicar_entorno+_refrescar_reads) | ✅ COMPLIANT |
| Profile selector combo | stale selection surfaced without partial env | `test_seleccion_stale_valueerror_no_aplica_env_parcial` | ✅ COMPLIANT |
| Profile selector combo | legacy store warns before onboarding | `test_legacy_avisa_regeneracion_y_sigue_onboarding` | ✅ COMPLIANT |

**Compliance summary**: 42/42 escenarios con test que pasa en runtime (0 UNTESTED, 0 FAILING, 0 PARTIAL).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Esquema user-only 3×3 sin hostname | ✅ Implementado | `leer/guardar_perfiles` envelope `{"perfiles": {...}}`; `_espacios`/`_plataformas` 3×3; grep hostname en core solo en docstrings |
| Legacy detectado → regen con flag | ✅ Implementado | `detectar_forma_perfil` ("nuevo"|"legacy"); resolución trata legacy como desconocida; escritura reemplaza; flag read-only en `estado_panel["legacy"]` |
| Resolver por usuario | ✅ Implementado | `perfiles.get(user)` directo; nunca raise/None (onboarding silencioso bajo lock) |
| ruta_para_espacio | ✅ Implementado | `None` sin lanzar para combinación ausente |
| get_context (project_root corte + espacio + so) | ✅ Implementado | `raiz_proyecto_desde_ruta` + `_espacio_prefijado` + `_proyecto_desde_nombre` fallback; `carpeta_salida` SIEMPRE token |
| variables_entorno(contexto, perfil=None) | ✅ Implementado | PROJECT_ROOT por corte (nunca base); PYTHON_* space roots; sibling `reconstruir_rutas`; clave irresoluble OMITIDA (nunca "") ; puro |
| raiz_proyecto_desde_ruta | ✅ Implementado | pura stdlib, corte estructural, Windows, None sin marcador |
| Cadena store proyecto-primero | ✅ Implementado | `{raiz}/.saman/` → env → config_local scoped → home; probe anti-hang estado_unidad+isfile; `.saman/` lazy solo write |
| Helper (listar/seleccion/cambio/estado) | ✅ Implementado | per-space, ValueError sin onboarding, flag legacy sin escribir |
| Widget combo + apply-on-select | ✅ Implementado | combobox + cachear_env/aplicar_entorno + _refrescar_reads; aviso legacy; degrada headless; call-site per-space |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1 Schema+legacy | ✅ Yes | envelope 3×3, `detectar_forma_perfil`, replace-on-write, flag read-only |
| D2 hostname removed | ✅ Yes | fuera de TODAS las firmas públicas del cambio (resolver/helper/widget/menu call-site); `resolver_perfil(usuario, hostname, ...)` → `(usuario, ...)` |
| D3 Engine API | ✅ Yes | firmas = contrato design.md; `variables_entorno(contexto, perfil=None)` |
| D4 raiz_proyecto_desde_ruta | ✅ Yes | en core.entorno, pura, `.saman` NO marcador |
| D5 Store chain | ✅ Yes | proyecto-primero, GANA proyecto, fallback env/config/home |
| D6 R2 probe | ✅ Yes | `_probe_store` = estado_unidad + isfile, cache 10 s, nunca crea en read |
| D7 R6 env | ✅ Yes | PROJECT_ROOT corte; fallback hermano; omitir irresoluble, nunca "" |
| D8 Shim | ✅ Yes | `SamanTools/rutas.py` FUERA del diff (14 archivos del cambio, shim no está); importa solo entorno/nombres/injector; `test_shim_sobrevive_sin_hostname` pasa |
| D9 Testability | ✅ Yes | fixtures 3×3 `_perfil_por_defecto()`; ladder tests eliminados |
| D10 Slices | ✅ Yes | commits S1→S5 stacked (8913c11→c062a25); suite verde por slice |

### TDD Compliance (Strict TDD)
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | apply-progress en Engram #2320 (sdd/perfil-por-usuario/apply-progress), tabla TDD Cycle Evidence por slice |
| All tasks have tests | ✅ | 23/23: cada tarea RED referencia un test file que EXISTE y pasa |
| RED confirmed (tests exist) | ✅ | test_rutas_engine / test_entorno / test_injector / test_menu / test_path_manager / test_path_manager_panel / test_shim / test_h5_docs verificados en disco |
| GREEN confirmed (tests pass) | ✅ | 350/350 pasan en ejecución real (coincide con claim del apply-progress: 349 baseline + 1 marker D8) |
| Triangulation adequate | ✅ | múltiples casos por comportamiento (p.ej. ruta_para_espacio param 9 combos; raiz_proyecto 12 tests; seleccion con Windows/legacy/ausente) |
| Safety Net for modified files | ✅ | apply-progress reporta 349/349 previos por slice; suite completa re-verificada |

Rayado por slice (suite counts reportados vs observados): S1 314 → S2 328 → S3 (helper) → S4 349 → S5 350 ✅ consistente con los commits y con la suite actual.

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | ~346 | 8 (core×3, ui×3, shim, docs-guard) | pytest 9.0.2 / Python 3.14 |
| Widget (UI fakes) | ~12 | 1 (`test_path_manager_panel.py`, pytest-qt + fakes, headless) | pytest-qt 4.5.0 |
| E2E | 0 | 0 | not installed (N/A por diseño) |

### Changed File Coverage
| File | Line % | Uncovered Lines | Rating |
|------|--------|-----------------|--------|
| `SamanTools/core/rutas_engine.py` | 90% | 124, 152-155, 202, 205-206, 223, 390, 392, 405, 454, 542-543, 560-567, 570-575, 578-579 | ✅ Excellent |
| `SamanTools/core/entorno.py` | 90% | 44-48, 80, 99, 117-120, 211, 242 | ✅ Excellent |
| `SamanTools/ui/path_manager.py` | 96% | 71, 76, 93 | ✅ Excellent |
| `SamanTools/ui/injector.py` | 88% | 96, 98-100, 150-151, 153, 161, 172, 188, 238, 263, 269, 300 | ✅ Excellent |
| `SamanTools/ui/path_manager_panel.py` | 83% | 38, 192, 219, 222-223, 228, 236-237, 244-245, 250-252, 264-265, 270-272, 282-289, 309, 311, 313, 317-318 | ⚠️ Acceptable |
| `SamanTools/ui/menu.py` | 76% | 61-62, 93-107, 129-130, 136-137, 155, 162-163, 187-188, 201-202, 208, 251-252 | ⚠️ Low |

**Average changed file coverage**: 87% (threshold config: 0 — no bloquea)
Nota menu.py: capa nuke-bound (import a nivel módulo + `instalar()` con efecto, aceptado por diseño ADR-7/0% documentado; las ramas headless se testean con fake_nuke).

### Assertion Quality (Step 5f)
Auditoría de los 8 test files del cambio: sin tautologías, sin ghost loops, sin assertions tipo-only solas, sin smoke-only. Las assertions verifican valores concretos (raíces ficticias, dicts de env, bytes del store SIN cambio tras lecturas/selección, `carpeta_salida` token) y efectos reales (multiproceso = no lost update; `os.environ` snapshot intacto; `.saman/` no creado en read). Mocks: `monkeypatch` de `entorno.estado_unidad`/`_verificar_ruta` con fakes — ratio mocks/assertions bajo, capa correcta.

**Assertion quality**: ✅ All assertions verify real behavior

### Quality Metrics
**Linter**: ➖ Not available (config linter: false) · **Type Checker**: ➖ Not available · **Formatter**: ➖ Not available

### Issues Found
**CRITICAL**: None
**WARNING**:
1. `SamanTools/ui/menu.py` — coverage 76% (< 80%). Evidencia: `pytest --cov` (líneas 93-107 `_identidad_ambiental` real, 129-137, 155, 162-163, 187-188, 201-202, 208, 251-252). Recomendación: aceptado por diseño (ADR-7: capa ui nuke-bound con import a nivel módulo; threshold config 0). No bloquea archive.
**SUGGESTION**:
1. `SamanTools/ui/menu.py:94-107` — `_identidad_ambiental()` aún recolecta `hostname` (socket.gethostname) y lo devuelve como segundo valor; el call-site `_resolver_contexto_carga` lo descarta (`usuario, _hostname`). Es código pre-existente del cambio load-contract (H4), NO está en el diff de este cambio, y ninguna firma de perfil lo usa (todas libres de hostname, verificado por `test_firmas_publicas_sin_hostname`). Recomendación opcional: limpiar la tupla en un cambio futuro para honrar AD2 por completo.

### Verdict
**PASS WITH WARNINGS** (`verified_with_warnings`): 23/23 tareas, 42/42 escenarios COMPLIANT con evidencia runtime (350 passed), 0 CRITICAL, 0 blockers, 10/10 ADs seguidos, shim D8 intacto, guard-audit limpio. Los warnings son informativos (coverage menu.py + residuo hostname pre-existente) y no bloquean archive.