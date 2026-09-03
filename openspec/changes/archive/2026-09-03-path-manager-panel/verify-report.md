```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d199eb8a95c73b2346f3240faa76a932f77254d1ff05b5ca4a609f8af00033b9
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 13/13
scenarios: 17/17
test_command: python3 -m pytest
test_exit_code: 0
test_output_hash: sha256:d199eb8a95c73b2346f3240faa76a932f77254d1ff05b5ca4a609f8af00033b9
build_command: python3 -m py_compile SamanTools/ui/path_manager.py SamanTools/ui/path_manager_panel.py SamanTools/ui/menu.py tests/test_path_manager.py tests/test_path_manager_panel.py tests/test_menu.py
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: path-manager-panel
**Version**: N/A (specs read from `openspec/changes/path-manager-panel/specs/{panel-path-manager-helper,panel-path-manager-widget,panel-path-manager-menu}/spec.md`)
**Mode**: Strict TDD (config `testing.strict_tdd: true`, pytest 9.0.2, runner available)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 13 |
| Tasks complete | 13 |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed
```text
python3 -m py_compile SamanTools/ui/path_manager.py SamanTools/ui/path_manager_panel.py SamanTools/ui/menu.py tests/test_path_manager.py tests/test_path_manager_panel.py tests/test_menu.py → exit 0 (output empty, sha256 e3b0c442…)
```

**Tests**: ✅ 292 passed / 0 failed / 0 skipped (`python3 -m pytest`, exit 0, output sha256 d199eb8a…; PySide6 6.10.2 + pytest-qt 4.5.0 active)

**Coverage** (changed files, informational; config `coverage_threshold: 0`): `SamanTools/ui/path_manager.py` 96% (✅ Excellent, miss L72/75/96 — None/empty defensive branches), `SamanTools/ui/path_manager_panel.py` 70% (⚠️ below 80% strict-TDD threshold — see Issues; uncovered = PySide2 dual-import branch L25, empty-base/ValueError submit guards L135-158, `_identidad_ambiental` L168-182, `abrir_dialogo` full-open path L200-212), `SamanTools/ui/menu.py` 0% by design (ADR-7, imports `nuke` at module level — coverage cannot attach).

### Spec Compliance Matrix

**panel-path-manager-helper (5 requirements / 7 scenarios — 7/7 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Pure, deterministic data layer | same inputs, same outputs, no env access | `tests/test_path_manager.py > test_estado_panel_mismos_inputs_mismos_outputs` (+ `test_helper_puro_sin_imports_prohibidos`, `test_helper_import_no_inyecta_nuke_ni_pyside`) | ✅ COMPLIANT |
| Active profile read with onboarding marker | known user resolves | `test_path_manager.py > test_estado_panel_par_conocido_devuelve_roots` | ✅ COMPLIANT |
| Active profile read with onboarding marker | unknown user returns marker without write | `test_estado_panel_desconocido_marcador_sin_escribir` (store bytes unchanged) + `test_detectar_desconocido_miss_verdadero_sin_escribir` | ✅ COMPLIANT |
| Unit status for the current-OS base | connected unit | `test_estado_panel_unidad_conectada` (probes `estado_unidad` called with `base_actual`) | ✅ COMPLIANT |
| Unit status for the current-OS base | disconnected unit | `test_estado_panel_unidad_desconectada` + `test_estado_panel_desconocido_consulta_primera_candidata` | ✅ COMPLIANT |
| Change-base prepares merged roots and env delta | macOS base change persists, others intact | `test_cambio_base_mac_2027_conserva_resto_y_otros_usuarios` (+ `test_cambio_base_fuente_default_actualiza_default_y_host`, `test_cambio_base_host_ajeno_actualiza_solo_ese_host`) | ✅ COMPLIANT |
| Onboarding preparation | onboarding persists with user base | `test_onboarding_persiste_par_con_roots_ficticias` (+ `test_onboarding_slotting_linux`) | ✅ COMPLIANT |

**panel-path-manager-widget (5 requirements / 5 scenarios — 5/5 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Thin dialog bound to the helper | profile and status rendered from helper data | `tests/test_path_manager_panel.py > test_dialogo_conocido_muestra_raiz_y_estado` (env snapshot unchanged) | ✅ COMPLIANT |
| Onboarding flow | new user submits base and env propagates | `test_onboarding_submit_asegura_una_vez_y_aplica_env` (spy: `asegurar_perfil` 1 call; `cachear_env`/`aplicar_entorno` received delta; `os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"`) | ✅ COMPLIANT |
| Change-base flow | change base re-applies env | `test_cambio_base_reaplica_env_2027` (env re-applied 2027; no direct widget env assignment) | ✅ COMPLIANT |
| Env purity outside aplicar_entorno | snapshot unchanged on cancel | `test_dialogo_abrir_y_cancelar_no_muta_env` + `test_panel_env_solo_via_injector` (no literal `os.environ` in module source) | ✅ COMPLIANT |
| Modal entry point | no GUI degrades silently | `test_abrir_dialogo_sin_gui_no_levanta` + `test_abrir_dialogo_sin_pyside_no_levanta` (blocked PySide reimport; no raise, no window) | ✅ COMPLIANT |

**panel-path-manager-menu (3 requirements / 5 scenarios — 5/5 compliant)**
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Path Manager item registration | item present, not duplicated | `tests/test_menu.py > test_instalar_registra_item_path_manager_sin_duplicar` + `test_instalar_no_abre_dialogo_ni_importa_pyside` (no dialog at install) | ✅ COMPLIANT |
| Deferred, indirect PySide access | exec without invocation does not import PySide | `test_instalar_no_abre_dialogo_ni_importa_pyside` (sys.modules PySide probe across 2 bootstrap execs) | ✅ COMPLIANT |
| Deferred, indirect PySide access | source guard keeps passing | `test_sin_pyside_ni_creacion_de_paneles` (regex `^\s*(?:import\s+PySide|from\s+PySide)` re.M, no match) | ✅ COMPLIANT |
| Deferred, indirect PySide access | PySide loads only on invocation | `test_click_path_manager_importa_panel_y_abre_dialogo` (real lazy callback imports panel at click, fake panel `abrir_dialogo` invoked) | ✅ COMPLIANT |
| Shortcut collision handling | collision degrades, menu still builds | `test_colision_atajo_usa_fallback_ctrl_alt_o` (+ `test_seleccionar_atajo_mantiene_principal_si_libre`, `test_seleccionar_atajo_degrade_al_fallback_si_ocupado`) | ✅ COMPLIANT |

**Compliance summary**: 17/17 scenarios compliant, 13/13 requirements satisfied (no UNTESTED, no FAILING, no PARTIAL).

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Helper pure: no nuke/PySide/`os.environ` | ✅ Implemented | `path_manager.py`: no imports beyond core/injector; no `import os`; `os.environ` mentioned only in docstring prose; source guard `detectar_violaciones` green |
| `detectar_desconocido` read-only, never `resolver_perfil` | ✅ Implemented | `path_manager.py:134-147` reads via `leer_perfiles` + `_emparejar_con_fuente`; parity test pins vs `resolver_perfil` with store bytes unchanged |
| Change-base READ-MERGE-WRITE shape (D7) | ✅ Implemented | exact/foreign → `hosts[hostname]` only; user-default → `default` + `hosts[hostname]`; one `guardar_perfiles` call; other platforms/users untouched (3 shape tests) |
| Determinism + `estado_unidad` on current-OS base | ✅ Implemented | `estado_panel` identical outputs on repeat; unit queried on `base_actual`/first candidate; timeout+cache via core `entorno` untouched |
| Onboarding via `asegurar_perfil`, lock-safe | ✅ Implemented | `preparar_onboarding` delegates to engine public API; slotting tests (macOS/Linux); no `os.environ` touch |
| Widget thin, env ONLY via injector | ✅ Implemented | `path_manager_panel.py` contains zero literal `os.environ`; env applied exclusively in `_aplicar_resultado` via `cachear_env`+`aplicar_entorno` |
| Widget no compute/no direct write | ✅ Implemented | renders `estado` data; submits delegate to helper; `PathManagerDialog` only reads helper output |
| Headless degrade | ✅ Implemented | `abrir_dialogo` guards `nuke.GUI`/PySide/estado exceptions; never raises; modal `exec()` |
| Menu item, constants, lazy import | ✅ Implemented | `_NOMBRE_ITEM_PATH_MANAGER`, `_ATAJO_PATH_MANAGER="Ctrl+Alt+R"`, `_ATAJO_FALLBACK_PATH_MANAGER="Ctrl+Alt+O"`; flat findItem-guarded registration; `_abrir_path_manager` imports panel only at click |
| Collision handling (D5) | ✅ Implemented | pure `seleccionar_atajo(principal, fallback, ocupado)` + injectable `_atajo_ocupado` (optimistic, try/except, never raises) |
| Guard tokens | ✅ Implemented | `rg -i wupm|LucidLink|HTLR|PCF` on SamanTools/ui + tests (excl. `__pycache__`) → only self-exempt `test_no_import_nuke_en_core.py` (must name tokens by design); `test_guard_arbol_real_sin_tokens` green |
| No drift: core untouched | ✅ Implemented | `git diff f7451a4~1..HEAD --name-only` → no `SamanTools/core/` paths; helper public surface = exactly the 3 documented contracts + read-only detection |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1 deferred PySide in menu.py | ✅ Yes | function-local `from SamanTools.ui import path_manager_panel` only inside `_abrir_path_manager`; regex guard green (no literal at any indent, re.M) |
| D2 detection without write, source tracking | ✅ Yes | `_emparejar_con_fuente` mirrors D2 ladder over public `leer_perfiles`; parity pinned vs `resolver_perfil` (store unchanged); never calls `resolver_perfil` |
| D3 helper API | ✅ Yes | focused pure functions `estado_panel`/`preparar_cambio_base`/`preparar_onboarding` (+ `detectar_desconocido`), env delta via `injector.armar_estado_env` with `base=` |
| D4 thin dialog | ✅ Yes | PySide2→PySide6 dual import with `QtAlignment` compat; renders helper data only; submit → helper → `cachear_env`/`aplicar_entorno`; `abrir_dialogo` guards `nuke.GUI`, modal `exec()`, never raises |
| D5 menu + shortcut collision | ✅ Yes | flat item, idempotent findItem, constants `Ctrl+Alt+R`/`Ctrl+Alt+O`; `seleccionar_atajo` + injectable `_atajo_ocupado`; open question (Nuke warns vs raises) remains non-blocking |
| D6 testability | ✅ Yes | helper Qt-free; widget `importorskip("PySide6")` + `QT_QPA_PLATFORM=offscreen`; menu reuses `_MenuFake` with `shortcut` capture |
| D7 change-base write shape | ✅ Yes | matched-entry-only writes verified on all three match kinds (exact/foreign/default) |
| D8 order, green per commit | ✅ Yes | git log f7451a4 (P1) → e3eb8af (P2) → 4adf76d (P3); suite green at each (baseline 258 → 286 → 292) |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | apply-progress (`sdd/path-manager-panel/apply-progress`, obs #2312) with TDD Cycle Evidence table; final revision documents P3 rows, cumulative 13/13 |
| All tasks have tests | ✅ | 13/13 tasks map to tests/test_path_manager.py (P1), tests/test_path_manager_panel.py (P2), tests/test_menu.py (P3) — all exist |
| RED confirmed (tests exist) | ✅ | 3/3 test files verified; tasks.md records failing RED runs ("Verify: fails", P3: 6 failed → 12 passed baseline) |
| GREEN confirmed (tests pass) | ✅ | 292/292 pass on full-suite execution; focused files 21/21, 7/7, 18/18 |
| Triangulation adequate | ✅ | `detectar_desconocido` 5 cases, change-base 3 shapes + error, onboarding 2 slots, `seleccionar_atajo` 2 pure cases, negative+positive pairs throughout |
| Safety Net for modified files | ✅ | P3 apply-progress reports 12/12 on pre-existing test_menu.py; helper/panel files new (N/A applies) |

**TDD Compliance**: 6/6 checks passed
Note: TDD Cycle Evidence rows for P1/P2 were overwritten by topic-key upserts (revisions); final revision documents P3 and asserts cumulative GREEN — cross-referenced against real test files and execution (same pattern as load-contract H1–H4).

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 27 | 2 | pytest 9.0.2 (helper Qt-free; menu with fakes) |
| Integration (widget) | 7 | 1 | pytest-qt 4.5.0 + PySide6 6.10.2 |
| E2E | 0 | 0 | not installed |
| **Total (this change)** | **34** | **3** | |

### Changed File Coverage
| File | Line % | Uncovered Lines | Rating |
|------|--------|-----------------|--------|
| `SamanTools/ui/path_manager.py` | 96% | L72, L75, L96 (empty/None defensive branches) | ✅ Excellent |
| `SamanTools/ui/path_manager_panel.py` | 70% | L25 (PySide2 branch), L135-158 (submit guards), L168-182 (`_identidad_ambiental`), L200-212 (`abrir_dialogo` open path) | ⚠️ Low (see Issues) |
| `SamanTools/ui/menu.py` | 0% by design | — (ADR-7: imports nuke at module level) | ➖ By design |

**Average changed file coverage**: ~83% (measured files only); config `coverage_threshold: 0` — informational.

### Assertion Quality
| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| — | — | — | None found: no tautologies, no ghost loops, no type-only-only, no empty-without-companion, no smoke-only; spies wrap real engine/injector functions and assertions verify real store bytes, `os.environ` values and call counts | — |

**Assertion quality**: ✅ All assertions verify real behavior.

### Quality Metrics
**Linter**: ➖ Not available (config `linter: null`)
**Type Checker**: ➖ Not available (config `type_checker: null`)

### Issues Found
**CRITICAL**: None
**WARNING**:
1. `panel-path-manager-widget` / coverage — `SamanTools/ui/path_manager_panel.py` at 70% < 80% strict-TDD threshold (evidence: coverage run, 125 stmts / 37 miss). Uncovered lines are the PySide2 dual-import branch (by design, D4), defensive submit guards (empty base, `ValueError` from helper), `_identidad_ambiental` fallbacks and the full `abrir_dialogo` open path (which uses live `injector.obtener_ruta_store`/`entorno.detectar_so`). D6 explicitly allows 0% for the widget if Qt is absent; with Qt present, error-path coverage is missing. Informational per strict-TDD module; not blocking.

**SUGGESTION**:
1. `panel-path-manager-helper` / drift — module docstring inventory lists `estado_panel`, `detectar_desconocido`, `_emparejar_con_fuente`, `preparar_cambio_base`, `preparar_onboarding` but not the private `_primera_candidata` and `_normalizar_base` (path_manager.py:82-97). No functional drift (all underscore-private, pure, covered indirectly), but the header's function list is incomplete.
2. `panel-path-manager-menu` / labeling — the registered item is "Path Manager..." (with ellipsis, V1 tool-line convention, pinned by tests) while the spec literal says "Path Manager". Cosmetic; behavior and shortcut comply.
3. Design open question (D5) remains open: whether Nuke warns instead of raising on in-use shortcuts — only verifiable in a Nuke session; `_atajo_ocupado` is optimistic by design.

### Verdict
**PASS WITH WARNINGS** — 13/13 tasks complete; full suite 292/292 green; py_compile passes; 17/17 spec scenarios compliant with passing covering tests; guard tokens clean in sources; core untouched; helper/panel/widget/menu fidelity verified against all 3 specs and D1–D8. One non-blocking coverage warning (widget error paths, informational) and two cosmetic suggestions. Residual risks tracked below are non-blocking.