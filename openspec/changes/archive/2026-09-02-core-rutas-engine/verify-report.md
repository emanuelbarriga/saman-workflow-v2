```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:971d381a48b49b99ea29a25f64b9ccca94b620c7deed2727f65bdb5db8bc6066
verdict: pass
blockers: 0
critical_findings: 0
requirements: 27/27
scenarios: 60/60
test_command: python3 -m pytest
test_exit_code: 0
test_output_hash: sha256:217ebf37c17a33046a49784e0f331d17ae3c2b385b838c2dcfbc47b2d6360f17
build_command: python3 -m py_compile SamanTools/__init__.py SamanTools/core/__init__.py SamanTools/core/entorno.py SamanTools/core/nombres.py SamanTools/core/limpiar.py SamanTools/core/rutas_engine.py tests/conftest.py tests/test_entorno.py tests/test_nombres.py tests/test_limpiar.py tests/test_rutas_engine.py tests/test_no_import_nuke_en_core.py
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: core-rutas-engine
**Version**: N/A (first V2 foundation change)
**Mode**: Standard + Strict TDD (config testing.strict_tdd: true, runner pytest 9.0.2 available)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 28 |
| Tasks complete | 28 |
| Tasks incomplete | 0 |

Note: tasks.md contains 28 `[x]` items (G1 6, G2 3, G3 3, G4 3, G5 3, G6 3, G7 3, G8 4); zero unchecked. The brief's "24/24" undercounts; nothing is pending either way.

### Build & Tests Execution
**Build**: ✅ Passed — `python3 -m py_compile` on all 12 touched .py files, exit 0, no warnings (output hash of empty output = sha256:e3b0c...).
**Tests**: ✅ 139 passed / 0 failed / 0 skipped — `python3 -m pytest` from root, exit 0, 2.69s, machine without Nuke (Darwin, Python 3.14.0, pytest 9.0.2).
**Coverage**: 89% total over SamanTools package (`pytest --cov`) — changed files: rutas_engine.py 88%, entorno.py 89%, nombres.py 96%, limpiar.py 87%, __init__ 100%. Uncovered lines are defensive branches (msvcrt LK_NBLCK pad/seek, fcntl liberar, OSError cleanup fallbacks) and OS-alternative branches (Windows `dir` cmd, unknown-SO) not executable on the macOS dev machine → ⚠️ Acceptable, all ≥80%.

### Spec Compliance Matrix (60/60 scenarios compliant)
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ engine/Injectable deterministic API | same inputs, same outputs | `test_rutas_engine.py > test_resolver_perfil_determinismo_mismos_inputs_mismos_outputs`, `test_contexto_determinismo_inputs_identicos` | ✅ COMPLIANT |
| REQ engine/JSON profile store | missing file starts empty | `> test_leer_perfiles_archivo_inexistente_devuelve_vacio` | ✅ COMPLIANT |
| REQ engine/JSON profile store | malformed JSON fails loudly | `> test_leer_perfiles_json_malformado_lanza_valueerror`, `test_leer_perfiles_raiz_no_objeto_lanza_valueerror` | ✅ COMPLIANT |
| REQ engine/JSON profile store | atomic round-trip | `> test_guardar_perfiles_round_trip_sin_temporales` (store+lock only, no temps) | ✅ COMPLIANT |
| REQ engine/JSON profile store | concurrent onboarding does not lose profiles | `> test_guardar_concurrente_multiproceso_no_pierde_perfiles` (real multiprocess + fcntl barrier) | ✅ COMPLIANT |
| REQ engine/Profile resolution | known pair resolves | `> test_resolver_perfil_par_conocido_devuelve_roots`, `test_emparejar_perfil_par_exacto_gana_sobre_default` | ✅ COMPLIANT |
| REQ engine/Profile resolution | fallback to user only | `> test_resolver_perfil_fallback_user_only`, `test_emparejar_perfil_fallback_user_only` | ✅ COMPLIANT |
| REQ engine/Tri-platform mapping | known profile maps each platform | `> test_ruta_para_plataforma_cada_plataforma` (+ `plataforma_ausente_devuelve_none`: no raise) | ✅ COMPLIANT |
| REQ engine/String-level relativization | absolute to placeholder | `> test_relativizar_macos_absoluto_a_placeholder` | ✅ COMPLIANT |
| REQ engine/String-level relativization | placeholder back to absolute | `> test_absolutizar_placeholder_a_macos_absoluto` | ✅ COMPLIANT |
| REQ engine/String-level relativization | outside base untouched | `> test_relativizar_fuera_de_base_intacto` | ✅ COMPLIANT |
| REQ engine/String-level relativization | Windows casing and separator variants relativize | `> test_relativizar_windows_casing_y_separador_preserva_casing` (`l:\vfx\2026\CINE\TO_VFX\ep.nk` + base `L:/VFX/2026` → `[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk`), `test_relativizar_drive_minuscula_equivale_drive_mayuscula`, `test_relativizar_prefijo_parcial_estudio2026_rechazado` | ✅ COMPLIANT |
| REQ engine/String-level relativization | Windows variant round-trips back | `> test_absolutizar_windows_round_trip_forward_slashes`, `test_absolutizar_base_inyectada_verbatim` | ✅ COMPLIANT |
| REQ engine/Context API | context from injected data | `> test_contexto_perfil_base_y_plato_basename` (proyecto CINE, plano 008_00100, version V01, carpeta_salida starts token), `test_contexto_carpeta_salida_convencion_comp` | ✅ COMPLIANT |
| REQ engine/Environment variables exposure | env contract contains PROJECT_ROOT | `> test_variables_entorno_project_root_y_python_vars`, `test_variables_entorno_no_muta_os_environ` | ✅ COMPLIANT |
| REQ engine/Unknown-user onboarding | onboarding persists the profile | `> test_resolver_perfil_onboarding_crea_persiste_y_segundo_resolve`, `test_onboarding_concurrente_mismo_par_no_duplica`, `test_asegurar_perfil_carrera_ganada_devuelve_existente_sin_reescribir` | ✅ COMPLIANT |
| REQ entorno/OS detection and SO tables | Darwin maps to macOS | `test_entorno.py > test_detectar_so_devuelve_so_valido` | ✅ COMPLIANT |
| REQ entorno/OS detection and SO tables | SO tables for the three platforms | `> test_tabla_so_sufijo_usuario` (parametrized) | ✅ COMPLIANT |
| REQ entorno/Neutralized base roots per SO | macOS order | `> test_rutas_base_macos` (estudio first, estudioCloud present) | ✅ COMPLIANT |
| REQ entorno/Neutralized base roots per SO | Windows scan without duplication | `> test_rutas_base_windows_escanea_letras` (L first, Z/T scanned, L once) | ✅ COMPLIANT |
| REQ entorno/Neutralized base roots per SO | user extra wins | `> test_rutas_base_extra_va_primera` | ✅ COMPLIANT |
| REQ entorno/Unit state with timeout and cache | existing directory connects | `> test_estado_unidad_conectado` | ✅ COMPLIANT |
| REQ entorno/Unit state with timeout and cache | hung mount is disconnected | `> test_estado_unidad_timeout_se_considera_desconectado` (TimeoutExpired → conectado False, detalle contains timeout) | ✅ COMPLIANT |
| REQ entorno/Unit state with timeout and cache | cache avoids rechecks | `> test_estado_unidad_usa_cache` (verifier runs exactly once) | ✅ COMPLIANT |
| REQ entorno/First available root | extra path available | `> test_primera_ruta_disponible_extra` | ✅ COMPLIANT |
| REQ entorno/First available root | nothing responds | `> test_primera_ruta_disponible_ninguna` | ✅ COMPLIANT |
| REQ entorno/Knob route reconstruction | nine keys under neutralized base | `> test_reconstruir_rutas_genera_9_claves`, `test_reconstruir_rutas_claves_exactas_de_los_knobs` (legacy `comp_SERVER_*` casing) | ✅ COMPLIANT |
| REQ entorno/Knob route reconstruction | Windows stays forward-slash | `> test_reconstruir_rutas_windows_forward_slashes` | ✅ COMPLIANT |
| REQ entorno/Project extraction from path | project under macOS base | `> test_proyecto_desde_ruta_cine_mac`, `> test_proyecto_desde_ruta_acepta_backslashes` | ✅ COMPLIANT |
| REQ entorno/Project extraction from path | partial prefix is not a match | `> test_proyecto_desde_ruta_prefijo_parcial_no_confunde` (`estudio2026` → None) | ✅ COMPLIANT |
| REQ nombres/Canonical plate parsing | canonical macOS path | `test_nombres.py > test_plato_canonico` | ✅ COMPLIANT |
| REQ nombres/Canonical plate parsing | folder chapter is authoritative | `> test_capitulo_de_ruta_es_autoritativo` (EP_107 beats filename 999) | ✅ COMPLIANT |
| REQ nombres/Version normalization | malformed version moved to end | `> test_plato_malformado_version_en_el_medio`, `test_plato_malformado_segundo_ejemplo` | ✅ COMPLIANT |
| REQ nombres/Version normalization | lowercase version uppercased | `> test_version_se_normaliza_a_mayuscula` (parametrized) | ✅ COMPLIANT |
| REQ nombres/Company suffix as metadata | comp suffix does not contaminate the plate | `> test_comp_nk_con_sufijo_empresa_no_contamina_plano` | ✅ COMPLIANT |
| REQ nombres/Company suffix as metadata | any owner token after comp is metadata | `> test_comp_nk_con_otro_nombre_empresa` (comp_OTRA untouched) | ✅ COMPLIANT |
| REQ nombres/Version-less references and basenames | PNG reference without version | `> test_png_sin_version` | ✅ COMPLIANT |
| REQ nombres/Version-less references and basenames | bare basename parses | `> test_solo_basename_reconoce_contenido` | ✅ COMPLIANT |
| REQ nombres/Platform-neutral path handling | Windows backslash path | `> test_ruta_windows_backslashes` | ✅ COMPLIANT |
| REQ nombres/Invalid inputs never raise | invalid inputs | `> test_entradas_invalidas_devuelven_none` (parametrized "", None, "foo.txt") | ✅ COMPLIANT |
| REQ limpiar/Volatile knob text removal | the three knobs are stripped | `test_limpiar.py > test_muestra_inline_quita_los_tres_volatiles`, `test_elimina_mov64_prraw`, `test_elimina_render_settings_schema`, `test_elimina_monitor_out`, `test_varias_ocurrencias_varios_nodos` | ✅ COMPLIANT |
| REQ limpiar/Volatile knob text removal | legit knobs untouched | `> test_no_toca_knobs_legitimos`, `test_muestra_inline_conserva_todo_legitimo` | ✅ COMPLIANT |
| REQ limpiar/Volatile knob text removal | idempotent | `> test_idempotente`, `test_idempotente_muestra_inline` | ✅ COMPLIANT |
| REQ limpiar/Safe atomic file sanitization | CRLF and BOM preserved | `> test_preserva_crlf`, `test_preserva_bom` | ✅ COMPLIANT |
| REQ limpiar/Safe atomic file sanitization | non-UTF-8 bytes survive | `> test_preserva_no_utf8` (0xE9 kept via latin-1), `test_no_utf8_sin_basura_no_reescribe` | ✅ COMPLIANT |
| REQ limpiar/Safe atomic file sanitization | unchanged file is untouched | `> test_sanitizar_archivo_sin_cambios` (0, no rewrite) | ✅ COMPLIANT |
| REQ limpiar/Safe atomic file sanitization | missing file raises | `> test_sanitizar_archivo_inexistente` (FileNotFoundError) | ✅ COMPLIANT |
| REQ limpiar/Recursive folder sanitization | mixed tree summary | `> test_sanitizar_carpeta_recursiva` (2 limpiados, 1 sin_cambios, 0 errores) | ✅ COMPLIANT |
| REQ limpiar/Recursive folder sanitization | only listed extensions count | `> test_sanitizar_carpeta_solo_extensiones` (.py untouched, counts 0/0) | ✅ COMPLIANT |
| REQ limpiar/Inline regression sample | synthetic sample regression | `> test_muestra_inline_quita_los_tres_volatiles` + `test_muestra_inline_conserva_todo_legitimo` (inline MUESTRA_NK_INLINE, fictitious, no studio gizmo) | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | guard fails on real import | `test_no_import_nuke_en_core.py > test_detectar_import_nuke_estatico` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | dynamic import of forbidden module fails | `> test_detectar_importlib_import_module_nuke`, `test_detectar_dunder_import_nuke`, `test_detectar_dunder_import_nukescripts`, `test_detectar_import_module_pyside6_comilla_simple` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | dynamic import of stdlib module passes | `> test_detectar_import_module_os_pasa` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | guard fails on real import (duplicate heading in spec) | `> test_detectar_import_nuke_estatico` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | comment mentioning nuke passes | `> test_detectar_comentario_import_nuke_pasa`, `test_detectar_literal_string_import_nuke_pasa`, `test_detectar_import_nuke_extra_no_matchea` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | PySide import detected | `> test_detectar_from_pyside6`, `test_detectar_from_pyside2`, `test_detectar_import_nukescripts` | ✅ COMPLIANT |
| REQ guard/Forbidden import detection | `__import__` of forbidden module detected | `> test_detectar_dunder_import_nuke` | ✅ COMPLIANT |
| REQ guard/Minimal non-Nuke test harness | full suite green without Nuke | `test_no_import_nuke_en_core.py > test_guard_core_real_limpio` + whole suite (139 passed, no nuke module) + `tests/conftest.py` is path-bootstrap only (no stub) | ✅ COMPLIANT |
| REQ guard/Real token and path hygiene | banned token rejected | `> test_auditar_tokens_marca_token_real` (`/Volumes/wupm/2026` flagged), `test_auditar_tokens_es_case_insensitive` | ✅ COMPLIANT |
| REQ guard/Real token and path hygiene | neutralized sources pass | `> test_auditar_tokens_fuentes_neutralizadas_pasan`, `test_auditar_tokens_ignora_pycache`, `test_guard_arbol_real_sin_tokens` (+ independent grep audit: 0 in sources, 5 matches only in self-exempt guard test) | ✅ COMPLIANT |

**Compliance summary**: 60/60 scenarios compliant (spec block count; core-purity-guard lists one duplicated scenario heading, so 59 unique scenario blocks + 1 duplicate, all green).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| D1 JSON schema (envelope + inner dict) | ✅ Implemented | `leer_perfiles` returns inner dict; `guardar_perfiles` wraps envelope, preserves unknown top-level keys (tested with `version` key), per-user merge never blind replace |
| D2 Precedence | ✅ Implemented | exact pair → user-only default → hostname-only insertion order → None marker; every match same-shaped roots dict |
| D3 Onboarding under lock | ✅ Implemented | lock → fresh re-read → re-resolve → merge → atomic write; race-won returns winner without rewrite (tested single-process sim + real multiprocess same-pair) |
| D4 API/graph | ✅ Implemented | All 12 declared functions present; no extra public surface; graph `entorno` standalone, `nombres → entorno`, `limpiar` standalone, `rutas_engine → entorno+{nombres}`; no cycles; core/ never imports ui/; engine has zero ambient calls (grep: getpass/socket/platform only in docstrings) |
| D5 Two-track normalization | ✅ Implemented | `_normalizar_para_comparar` canonical string (`\`→`/`, strip, rstrip `/`, lower whole); prefix guard `clave_base + "/"` on canonical copy; emission slices separator-normalized original at `len(base_s)` preserving casing; absolutizar verbatim injected base |
| D6 Sibling lock | ✅ Implemented | `_lock_perfiles(path)` locks `path + ".lock"` never target (test asserts fd name); fcntl/msvcrt/no-op factory; 3×2.0s attempts → `TimeoutError("No se pudo adquirir lock de perfiles")` |
| D7 Guard matcher | ✅ Implemented | Single `detectar_violaciones` with one compiled pattern (static anchored `^\s*(import|from)\s+` + dynamic unanchored `__import__|import_module`); one `_MODULOS_PROHIBIDOS` set; `auditar_tokens` hygiene with self-exempt guard file |
| D8 Test matrix / D9 order | ✅ Implemented | Multiprocess concurrency harness with start barrier (POSIX); git log G1→G7 sequential commits |
| V1 copy-intact extraction | ✅ Implemented | No public renames: entorno (detectar_so, sufijo_so, usuario_activo, rutas_base, estado_unidad, primera_ruta_disponible, reconstruir_rutas, proyecto_desde_ruta), nombres (parsear_plato), limpiar (sanitizar_*); legacy `PREFIJOS = ("TO_VFX", "comp", "FROM_VFX")` casing preserved (not "fixed") |
| Neutralization contract | ✅ Implemented | `wupm→estudio`, `wupmCloud→estudioCloud`, `L:/2026→L:/VFX/2026`, `/mnt/wupm→/mnt/estudio`, `HTLR/PCF→CINE`; 0 real tokens in sources (grep + automated guard both clean) |
| Determinism | ✅ Implemented | Engine logic injectable; no ambient identity/env reads in engine path (port overridden per D4); determinism tests pass |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1 envelope + inner + metadata preservation | ✅ Yes | `leer_perfiles` inner dict; envelope keys preserved (tested) |
| D2 precedence ladder + None marker | ✅ Yes | `_emparejar_perfil` exact order, insertion-order hostname scan, `None` internal |
| D3 locked onboarding + race re-read/re-resolve | ✅ Yes | `asegurar_perfil`; race-won bypasses write (test asserted no extra `default` added) |
| D4 API list + dependency graph | ✅ Yes | Exact function set; graph matches; `get_context` 6 keys (spec 4 + base + so) |
| D5 canonical-string two-track | ✅ Yes | Comparison vs emission split exactly as designed; partial-prefix guard |
| D6 sibling `.lock` + timeout/retry | ✅ Yes | Sibling file, 3×2.0s, TimeoutError; no-op degraded path documented and unit-tested |
| D7 single matcher + self-exempt hygiene | ✅ Yes | One tokenizer function; guard file self-exempt via identity compare |
| D8/D9 matrix + order | ✅ Yes | Concurrency multiprocess tests; extraction order respected |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | apply-progress (Engram #2282, topic sdd/core-rutas-engine/apply-progress) contains "TDD Cycle Evidence" table; G7 row detailed (RED 20 tests → AttributeError; GREEN 23 passed), G1–G6 summarized across earlier revisions of the same topic |
| All tasks have tests | ✅ | 28/28 tasks map to test files that exist and are committed |
| RED confirmed (tests exist) | ✅ | 7 test files exist (conftest + 6 suites); RED→GREEN cycle documented |
| GREEN confirmed (tests pass) | ✅ | 139/139 pass on fresh execution, exit 0 |
| Triangulation adequate | ✅ | Multiple distinct test cases per behavior; parametrized where apt; no single-case coverage of multi-scenario requirements |
| Safety Net for modified files | ✅ | G7 row reports 119/119 pre-change suite green; files are new in this change |

**TDD Compliance**: 6/6 checks passed (G1–G6 detailed RED/GREEN rows live in prior revisions of the apply-progress topic and were not re-retrieved; test files and passing execution corroborate independently).

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 139 | 6 | pytest 9.0.2 |
| Integration | 0 | 0 | not installed (declared out of scope; nuke-stub block deferred) |
| E2E | 0 | 0 | not installed |
| **Total** | **139** | **6** | |

Note: the two multiprocess concurrency tests are unit-level tests of real fcntl behavior (runtime harness per tasks.md G5/G6).

### Changed File Coverage
| File | Line % | Branch % | Uncovered Lines | Rating |
|------|--------|----------|-----------------|--------|
| `SamanTools/core/rutas_engine.py` | 88% | n/a | L142-145, L159, L167, L200, L280, L283, L298, L395, L397, L409, L413, L456, L484, L520-521, L538-557 | ⚠️ Acceptable (msvcrt branches + defensive guards not runnable on macOS) |
| `SamanTools/core/entorno.py` | 89% | n/a | L44-48, L80, L99, L117-120, L216 | ⚠️ Acceptable (OS-alternative branches + OSError fallback) |
| `SamanTools/core/nombres.py` | 96% | n/a | L80, L112, L136 | ✅ Excellent |
| `SamanTools/core/limpiar.py` | 87% | n/a | L100-103, L129-131 | ⚠️ Acceptable (cleanup/error-collection branches) |
| `SamanTools/__init__.py`, `core/__init__.py` | 100% | n/a | — | ✅ Excellent |

**Average changed file coverage**: 92% (package total 89%). No changed file below 80% → no WARNING per strict module; coverage threshold configured is 0.

### Assertion Quality
**Assertion quality**: ✅ All assertions verify real behavior — no tautologies, no ghost loops (in-test loops iterate fixed module-level constants), no orphan empty-only checks (every `== {}` / empty assert has a companion non-empty test), no smoke-only tests, no mock-heavy files (real subprocess/multiprocess harness plus targeted monkeypatch).

### Quality Metrics
**Linter**: ➖ Not available (config linter: false)
**Type Checker**: ➖ Not available (config type_checker: false)
**Formatter**: ➖ Not available (config formatter: false)

### Issues Found
**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
1. (core-rutas-engine) `get_context` determinism corner: when the plate path matches NO injected profile root (`base=None`), `parsear_plato`'s V1-copy ambient `proyecto_desde_ruta(ruta)` (which calls `detectar_so()`) can contribute a platform-dependent `proyecto` before the `_proyecto_desde_nombre` fallback — only observable when the plate directory coincides with a real local base whose project differs from the filename prefix. Spec scenarios all use basenames or fictitious roots that match the profile, so no scenario fails; residual risk only. Recommendation: bypass the ambient call in the `base is None` path (name-token fallback only) for full cross-machine determinism.
2. (core-purity-guard) Task 8.3 evidence says "6 matches (lines 8/30/153/161/174)"; the independent audit found 5 matching lines, all in the self-exempt guard test, 0 in sources. Evidence drift only; requirement met.
3. (core-entorno) `detectar_so` Windows/Linux branches and the Windows `dir` branch are uncovered on the macOS dev machine; a unit test monkeypatching `platform.system` would close the gap (coverage is informational, not blocking).

### Verdict
PASS — 139/139 tests green, 27/27 requirements and 60/60 spec scenarios compliant with runtime evidence, all design decisions D1–D9 followed, zero real-studio tokens in sources, engine fully injectable and deterministic as exercised; no CRITICAL or WARNING findings.