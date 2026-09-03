```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d04a4703e7fb78f1e7e263348e306da13653223394b5f85c1631a376f42218c3
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 27/27
scenarios: 36/36
test_command: python3 -m pytest
test_exit_code: 0
test_output_hash: sha256:c6d1e7df130a4c6935f5bcbc4f5b6f299fbde1ee3eb7a123d2f726d0ae08fcd8
build_command: python3 -m py_compile SamanTools/ui/injector.py SamanTools/ui/menu.py SamanTools/rutas.py bootstrap/menu.py SamanTools/config_local.py tests/test_injector.py tests/test_shim.py tests/test_bootstrap.py tests/test_menu.py tests/test_h5_docs.py
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: load-contract
**Version**: N/A (specs read from `openspec/changes/load-contract/specs/{load-injector,load-shim,load-bootstrap-contract,load-ui-menu}/spec.md`)
**Mode**: Strict TDD (config `testing.strict_tdd: true`, pytest 9.0.2, runner available)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 19 |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed
```text
python3 -m py_compile SamanTools/ui/injector.py SamanTools/ui/menu.py SamanTools/rutas.py bootstrap/menu.py SamanTools/config_local.py tests/test_injector.py tests/test_shim.py tests/test_bootstrap.py tests/test_menu.py tests/test_h5_docs.py → exit 0 (output empty, sha256 e3b0c442…)
python3 -m compileall -q SamanTools bootstrap tests → exit 0
```

**Tests**: ✅ 244 passed / 0 failed / 0 skipped (`python3 -m pytest`, exit 0, output sha256 c6d1e7df…)

**Coverage** (changed files, informational): `SamanTools/ui/injector.py` 90% (✅ Excellent), `SamanTools/rutas.py` 75% (⚠️ Low, threshold 80% from strict-TDD module — see Issues; by-design nuke-bound legacy knob reads are not unit-covered per load-shim spec). `ui/menu.py` 0% by design (ADR-7, imports nuke at top); `bootstrap/menu.py` not measured (loaded via importlib with fake module name).

### Spec Compliance Matrix

**load-injector (5 requirements / 10 scenarios — 10/10 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Pure environment assembly | comp under root yields full env | `tests/test_injector.py > test_env_completo_bajo_root` | ✅ COMPLIANT |
| Pure environment assembly | untitled script still gets a base | `test_injector.py > test_untitled_gap_2286_inyecta_base` (+ `test_ruta_fuera_de_toda_root_inyecta_base`) | ✅ COMPLIANT |
| Pure environment assembly | deterministic across calls | `test_injector.py > test_determinista_entre_llamadas` | ✅ COMPLIANT |
| Pure environment assembly | purity — no os.environ mutation | `test_injector.py > test_no_muta_os_environ_ni_main` | ✅ COMPLIANT |
| Thin environment application | apply repeats without duplication | `test_injector.py > test_idempotente_repite_sin_duplicar` (+ `test_escribe_os_environ_y_main`) | ✅ COMPLIANT |
| No disk or lock on save | save re-asserts from memory only | `tests/test_menu.py > test_save_rea_afirma_desde_memoria_sin_store` (spy: `obtener_ruta_store` 0 calls) | ✅ COMPLIANT |
| Callback registration | script load resolves TCL env | `test_menu.py > test_flujo_load_perfil_override_y_env_aplicados`, `test_flujo_load_sin_override_usa_perfil` | ✅ COMPLIANT |
| Callback registration | render farm env wins | `test_menu.py > test_flujo_load_env_preexistente_gana_no_op` (spy `resolver_perfil` 0 calls) + `test_injector.py > test_precedencia_env_preexistente_gana` | ✅ COMPLIANT |
| Callback registration | manual script override respected | `test_menu.py > test_flujo_load_perfil_override_y_env_aplicados` + `test_injector.py > test_precedencia_override_gana` | ✅ COMPLIANT |
| Profile store resolution | env var wins | `test_injector.py > test_env_var_gana` (+ module attr / JSON sibling / home fall) | ✅ COMPLIANT |

**load-shim (5 requirements / 8 scenarios — 8/8 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Headless import without a stub | import ok without nuke | `tests/test_shim.py > test_import_headless_sin_stub` (runtime check: `'nuke' not in sys.modules`) | ✅ COMPLIANT |
| Headless import without a stub | signature with Nuke type still imports headless | `test_shim.py > test_anotaciones_nuke_en_string_no_evaluan` (`__annotations__["n"] == "nuke.Node"`) | ✅ COMPLIANT |
| Re-export pure constants | KNOBS_RUTAS_BASE identical to V1 | `test_shim.py > test_knobs_rutas_base_identica_v1` (+ manual diff vs V1 `saman-nuke-tools/SamanTools/rutas.py:385`) | ✅ COMPLIANT |
| Re-export pure constants | SUFIJOS mapping preserved | `test_shim.py > test_sufijos_identico_v1` (+ `test_knobs_version_actual_identico_v1`, `test_knobs_a_migrar_identico_v1`) | ✅ COMPLIANT |
| Thin nuke-bound facades | actualizar with a fake node returns without exception | `test_shim.py > test_actualizar_devuelve_bool_sin_excepcion` (+ env-via-injector, ADR-3 guards) | ✅ COMPLIANT |
| Thin nuke-bound facades | es_nodo_rutas detects by knobs | `test_shim.py > test_es_nodo_rutas_true_por_knobs_independiente_del_nombre` | ✅ COMPLIANT |
| Compat-only stubs | crear_o_reutilizar is a no-op | `test_shim.py > test_stubs_compat_only_noop_sin_nuke` (+ `test_stubs_docstring_marca_compat_only`) | ✅ COMPLIANT |
| Core untouched | core purity guard keeps passing | `tests/test_no_import_nuke_en_core.py > test_guard_core_real_limpio` + git log (only G1–G7 touch `SamanTools/core/`) | ✅ COMPLIANT |

**load-bootstrap-contract (13 requirements / 14 scenarios — 14/14 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Fetch-only startup | checkout up to date | `tests/test_bootstrap.py > test_estado_update_ok_es_fetch_only` (asserts no pull/clone/reset) | ✅ COMPLIANT |
| Consent-based update | update available and deferred | `test_bootstrap.py > test_alerta_automatica_declina_consentimiento_sin_pull` | ✅ COMPLIANT |
| Consent-based update | alert rate-limited | `test_bootstrap.py > test_alerta_automatica_rate_limit_6_horas` | ✅ COMPLIANT |
| Apply only via fast-forward pull | non-fast-forward pull rejected | `test_bootstrap.py > test_aplicar_update_pull_fallido_mensaje_sin_reset` (asserts no reset/clone) | ✅ COMPLIANT |
| Silence without checkout | never installed or uninstalled | `test_bootstrap.py > test_cargar_menu_real_sin_checkout_silencio_total` (0 git calls, 0 dialogs) | ✅ COMPLIANT |
| Atomic clone via temp + rename | failed clone leaves target untouched | `test_bootstrap.py > test_clonar_si_falta_fallo_limpia_tmp_y_deja_target_ausente` (+ `test_clonar_si_falta_tmp_rename_atomico`) | ✅ COMPLIANT |
| Silent reset repair | broken checkout repaired | `test_bootstrap.py > test_reparar_checkout_reset_hard_alinea_con_origin` | ✅ COMPLIANT |
| Content-hash auto-sync | repo bootstrap differs from installed | `test_bootstrap.py > test_auto_actualizar_bootstrap_sincroniza_por_md5` (+ no-copy-when-equal) | ✅ COMPLIANT |
| Maintenance menu only when checkout exists | uninstalled state leaves menu clean | `test_bootstrap.py > test_agregar_boton_menu_sin_checkout_menu_limpio` | ✅ COMPLIANT |
| Update button reinstalls | manual update reinstalls when checkout missing | `test_bootstrap.py > test_actualizar_ahora_sin_checkout_reinstala` | ✅ COMPLIANT |
| Self-contained bootstrap | broken checkout still offers maintenance | `test_bootstrap.py > test_bootstrap_self_contained_no_importa_repo` (stdlib+nuke only) | ✅ COMPLIANT |
| V2 structural probes | full V2 checkout loads the target | `test_bootstrap.py > test_cargar_menu_real_repara_y_ejecuta_ui_menu` + `test_checkout_completo_probea_rutas_engine` + `test_probes_v2_estructura_de_fuente` | ✅ COMPLIANT |
| Distinct V2 uninstall marker | V1 uninstaller ignores V2 bootstrap | `test_bootstrap.py > test_marcador_v2_presente_y_v1_ausente_en_fuente` + `test_desinstalar_ahora_no_borra_bootstrap_v1` | ✅ COMPLIANT |

**load-ui-menu (4 requirements / 4 scenarios — 4/4 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Bootstrap exec target | bootstrap exec path | `tests/test_menu.py > test_bootstrap_exec_registra_callbacks_y_construye_menu` | ✅ COMPLIANT |
| Idempotent callback registration | re-exec does not duplicate | `test_menu.py > test_reejecucion_no_duplica_callbacks` + `test_instalar_repetido_no_duplica_items` | ✅ COMPLIANT |
| Minimal menu without panels | menu built, no panels | `test_menu.py > test_sin_pyside_ni_creacion_de_paneles` (no PySide/nodePaste/addPanel) | ✅ COMPLIANT |
| Import-safe shim access | shim import failure tolerated | `test_menu.py > test_shim_import_fallido_no_rompe_callbacks_ni_menu` | ✅ COMPLIANT |

**Compliance summary**: 36/36 scenarios compliant, 27/27 requirements satisfied (no UNTESTED, no FAILING, no PARTIAL).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| `armar_estado_env` pure (no nuke, no os.environ, no global state) | ✅ Implemented | `SamanTools/ui/injector.py:66`; gap #2286 corrected via `base` param → `ruta_para_plataforma` → context base, then env assembly (`:77-86`) |
| No disk/lock on save | ✅ Implemented | `ui/menu.py:152-160` `_al_guardar_script` re-asserts only `injector._env_cache` via `aplicar_entorno`; no store/lock/engine call on save path |
| Precedence headless→override→profile | ✅ Implemented | `ui/menu.py:136-137` (pre-existing PROJECT_ROOT → no-op, before any profile resolution), `_aplicar_precedencia` (`injector.py:198-223`); load injector-first (profile = source of truth) |
| Store chain env → config_local scoped → home → onboarding | ✅ Implemented | `injector.py:127-143` `obtener_ruta_store`; `resolver_perfil` onboarding (engine D3, fictitious roots) |
| config_local scoped, never repo root | ✅ Implemented | `SamanTools/config_local.py` (gitignored, `.gitignore:22` any-depth); key `NUKE_PROFILES_PATH` (`injector.py:107`); no root-level module |
| Shim headless + string type hints | ✅ Implemented | `SamanTools/rutas.py`: lazy `import nuke` in bodies only; `n: "nuke.Node"` annotations; runtime import OK with `nuke` absent |
| Constants identical to V1 | ✅ Implemented | Manual diff vs V1 `rutas.py`: `SUFIJOS`, `KNOBS_RUTAS_BASE`, `KNOBS_VERSION_ACTUAL`, `_KNOBS_A_MIGRAR` byte-identical |
| Facades delegate + `_env_inyectado` guard | ✅ Implemented | `rutas.py:286` `_aplicar_env_shim` skips env write when injector wrote this session; always via `injector.aplicar_entorno` |
| Stubs compat-only | ✅ Implemented | 5 no-ops returning `None`, docs marked COMPAT-ONLY (`rutas.py:583-605`) |
| Core untouched | ✅ Implemented | git log: only G1–G7 commits touch `SamanTools/core/`; purity guard passes; core only *mentions* os.environ in docstrings |
| Bootstrap 11 V1 rules | ✅ Implemented | Function inventory identical to V1 (17 helpers + `instalar` + boot call); diff shows only probe/marker/doc changes |
| V2 probes + distinct marker | ✅ Implemented | `bootstrap/menu.py:361` probes `core/rutas_engine.py`; `:401` execs `ui/menu.py`; `:413` auto-sync from `bootstrap/menu.py`; `MARCADOR = "SamanTools V2 bootstrap"` (`:49`), no "bootstrap de artista" |
| Menu idempotent + minimal | ✅ Implemented | `ui/menu.py:63-75` idempotent via `injector._callbacks_registrados`; SamanTools > Configuración with one info item; no panels/PySide |
| Token guard | ✅ Implemented | `rg wupm|LucidLink|HTLR|PCF` in SamanTools/bootstrap/docs/tests (excl. `__pycache__`) → only self-exempt `test_no_import_nuke_en_core.py` |
| No undeclared public functions | ✅ Implemented | Shim public surface = exact V1 12-function set; injector/menu publics all declared (extra helpers underscore-private) |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-1 injector.py name | ✅ Yes | `SamanTools/ui/injector.py` |
| ADR-2 save = memory re-assert only | ✅ Yes | `_al_guardar_script`, spy-verified |
| ADR-3 knobChanged ↔ precedence, injector cache wins | ✅ Yes | `_env_inyectado` guard in shim; idempotent, order-independent tests |
| ADR-4 headless = PROJECT_ROOT pre-present | ✅ Yes | Single check first in load callback; documented narrowing of "(or the store path)" |
| ADR-5 override via root `project_directory` knob | ✅ Yes | `_override_proyecto_desde_root` pure, fake-root tested; residual Nuke-version risk (open Q1) |
| ADR-6 store chain | ✅ Yes | env → `SamanTools.config_local` (attr or sibling JSON) → `~/.config/saman/nuke_profiles.json` |
| ADR-7 menu thin/idempotent via injector flag | ✅ Yes (⚠ interface location) | Flag `_callbacks_registrados` lives in injector; function `registrar_callbacks` implemented in `ui/menu.py` (documented in tasks H1 note + both docstrings) |
| ADR-8 shim signature matrix | ✅ Yes | 12 V1 public functions present; delegation to core/injector |
| ADR-9 testability without stub | ✅ Yes | Node/root/menu/nuke fakes local to test files; conftest untouched |
| ADR-10 implementation order, suite green | ✅ Yes | H1→H5 commits, suite green at each commit (git log) |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | apply-progress (`sdd/load-contract/apply-progress`, obs #2305, 5 revisions) with TDD Cycle Evidence table; final cumulative 19/19 |
| All tasks have tests | ✅ | 5/5 slices: test_injector.py (H1), test_shim.py (H2), test_bootstrap.py (H3), test_menu.py (H4), test_h5_docs.py (H5) — all exist |
| RED confirmed (tests exist) | ✅ | 5/5 test files verified in codebase |
| GREEN confirmed (tests pass) | ✅ | 244/244 pass on full-suite execution |
| Triangulation adequate | ✅ | Multi-case per behavior (e.g. 4 scenarios for `armar_estado_env`, 30+ bootstrap cases, negative+positive pairs) |
| Safety Net for modified files | ✅ | H5 apply-progress reports 240/240 safety net; all changed files new (additive), suite green each commit |

**TDD Compliance**: 6/6 checks passed
Note: TDD Cycle Evidence table rows for H1–H4 were overwritten by topic-key upserts (5 revisions); final revision documents H5 rows and asserts cumulative GREEN; cross-referenced against real test files and execution.

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 244 | 11 | pytest 9.0.2 (no integration/E2E tools configured) |
| Integration | 0 | 0 | not installed |
| E2E | 0 | 0 | not installed |
| **Total** | **244** | **11** | |

### Changed File Coverage
| File | Line % | Uncovered Lines (sample) | Rating |
|------|--------|--------------------------|--------|
| `SamanTools/ui/injector.py` | 90% | L102-105, L113, L124, L160, L185, L191, L222 (defensive branches) | ✅ Excellent |
| `SamanTools/rutas.py` | 75% | nuke-bound knob paths (L118-121, 134-142, 154-167, 180-201, 239-241, 266-267, 311-331, 354-365, 377, 463-495, 543-574) | ⚠️ Low (see Issues) |
| `SamanTools/ui/menu.py` | 0% by design | — (ADR-7; imported under fake only) | ➖ By design |
| `bootstrap/menu.py` | not measured | loaded via importlib fake module name | ➖ N/A |

**Average changed file coverage**: ~83% (measured files only); coverage_threshold in config = 0 (informational).

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| — | — | — | None found: no tautologies, no ghost loops, no type-only-only, no empty-without-companion, no smoke-only | — |

**Assertion quality**: ✅ All assertions verify real behavior (value assertions on env dicts, os.environ, callbacks counters, git argv composition, fs effects). Guard/marker tests (source scans) are the repo's established contract pattern (ADR-9) and assert real published contracts.

### Quality Metrics
**Linter**: ➖ Not available (config `linter: null`)
**Type Checker**: ➖ Not available (config `type_checker: null`)

### Issues Found
**CRITICAL**: None
**WARNING**:
1. `load-shim` / coverage — `SamanTools/rutas.py` at 75% < 80% strict-TDD threshold (evidence: coverage run, `SamanTools/rutas.py:274 stmts, 68 miss`). Uncovered lines are nuke-bound legacy knob reads/defensive branches explicitly out of unit coverage by load-shim spec ("Reading legacy knobs stays nuke-bound and is not unit-covered"). Not blocking; report honestly.
2. `load-injector` / design coherence — `registrar_callbacks` implemented in `SamanTools/ui/menu.py:63` while design Interfaces/Contracts lists it under `SamanTools/ui/injector.py` (evidence: `design.md:76-82` vs `menu.py:63-75`). Documented deviation (tasks.md H1 note, injector.py:33-37, ADR-7 flag location). Behavior, idempotency flag (`injector._callbacks_registrados`) and all spec scenarios comply; does not break the spec.

**SUGGESTION**:
1. `SamanTools/__init__.py:3` docstring stale: "la capa de interfaz grafica se anade en cambios posteriores" — ui/menu.py now exists. Update wording.

### Verdict
**PASS WITH WARNINGS** — 19/19 tasks complete; full suite 244/244 green; py_compile/compileall pass; 36/36 spec scenarios compliant with passing covering tests; token guard clean; core intact; integrity chain verified. Two non-blocking warnings (shim coverage, documented module placement) and one stale-docstring nit. Residual risks below are tracked in the design's open questions, not failures.