# Tasks: Path Manager Panel (Ctrl+Alt+R)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 280–380 (3 new modules + 2 new test files + menu delta) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR; green commit per slice (P1→P2→P3, D8) |
| Delivery strategy | auto-chain |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Pure helper + Qt-free tests | PR 1 (commit 1) | `pytest tests/test_path_manager.py` | tmp store JSON, real engine/injector, no Qt | delete module + test |
| 2 | Widget + pytest-qt tests | PR 1 (commit 2) | `pytest tests/test_path_manager_panel.py` | pytest-qt 4.5.0 + PySide6 6.10.2, `_NukeFake`; skip → 0% | delete module + test |
| 3 | Menu integration | PR 1 (commit 3) | `pytest tests/test_menu.py` | `_MenuFake` + fake panel, sys.modules probe | revert menu delta |

## Design Notes

- D6: pytest-qt 4.5.0 + PySide6 6.10.2 verified; widget `importorskip("PySide6")` → 0% OK if Qt absent; helper 100% Qt-free.
- D2: detection via `_emparejar_con_fuente()` over `leer_perfiles`, NEVER `resolver_perfil`; parity pinned in tests.
- D7: change-base matched entry only (exact/foreign → `hosts[hostname]`; user-default → `default` + `hosts[hostname]`); one `guardar_perfiles` lock.
- D1: no PySide at any indent (regex re.M, test_menu.py:387) → deferred import in callback. D5: collision → fallback key.
- Threat matrix N/A by design: no routing/shell/subprocess boundary; no extra RED rows.
- Style: docstrings ES, identifiers EN; py_compile every touched `.py`.

## Phase 1: P1 — Pure helper + tests

- [x] 1.1 RED — `tests/test_path_manager.py`: `estado_panel()` determinism + no `os.environ` (REQ-1); known → 3 fictitious roots, unknown → onboarding marker without write (REQ-2). Verify: `pytest tests/test_path_manager.py -k estado` fails.
- [x] 1.2 GREEN — `SamanTools/ui/path_manager.py` (D3): pure `estado_panel(ruta_store, usuario, hostname, so)` with `_emparejar_con_fuente`; `entorno.estado_unidad` on current-OS base (REQ-3). Verify: 1.1 green + `py_compile`.
- [x] 1.3 RED — change-base (REQ-4, D7): macOS → 2027 persisted, Windows/Linux + `"pedro"/"ws2"` untouched; env delta `PROJECT_ROOT` 2027. Verify: fails.
- [x] 1.4 GREEN — `preparar_cambio_base()`: READ-MERGE-WRITE `guardar_perfiles` (one lock, D7) + `armar_estado_env(perfil, so, ruta_plato, base=…)` (D3); `os.environ` untouched. Verify: 1.3 green + `py_compile`.
- [x] 1.5 RED — onboarding (REQ-5): store gains `("nuevo","pc9")` with macOS base + fictitious other roots; env delta present. Verify: fails.
- [x] 1.6 GREEN — `preparar_onboarding()` via `asegurar_perfil` (lock-safe) → `{"perfil","env","unidad"}`. Verify: 1.5 green; full helper suite green.

## Phase 2: P2 — Thin widget + tests

- [x] 2.1 RED — `tests/test_path_manager_panel.py`: labels render macOS root + connected status; `os.environ` unchanged on open/cancel (REQ-1/REQ-4); `importorskip("PySide6")` (D6). Verify: fails or skips.
- [x] 2.2 GREEN — `SamanTools/ui/path_manager_panel.py` (D4): dual import PySide2→PySide6 + `QtAlignment` compat; dialog renders helper data only; env ONLY via `injector.cachear_env` + `aplicar_entorno`. Verify: 2.1 green + `py_compile`.
- [x] 2.3 RED — onboarding submit → `asegurar_perfil` once + env applied (REQ-2); change-base re-applies 2027, no direct widget assignment (REQ-3); `abrir_dialogo()` headless silent (REQ-5). Verify: fails.
- [x] 2.4 GREEN — submit handlers + `abrir_dialogo()` guarding `nuke.GUI`/PySide, never raises, modal `exec()` (D4). Verify: 2.3 green; panel suite green; `py_compile`.

## Phase 3: P3 — Menu integration

- [x] 3.1 RED — extend `tests/test_menu.py`: `_MenuFake.addCommand` captures `shortcut` (D6); one idempotent item, `Ctrl+Alt+R`, no dialog at install (REQ-1); no PySide in sys.modules after exec, regex clean (REQ-2); collision → fallback `Ctrl+Alt+O` via `_atajo_ocupado()` + `seleccionar_atajo` (REQ-3, D5). Verify: fails.
- [x] 3.2 GREEN — `SamanTools/ui/menu.py`: flat item; `_ATAJO_PATH_MANAGER="Ctrl+Alt+R"` / `_ATAJO_FALLBACK_PATH_MANAGER="Ctrl+Alt+O"`; lazy callback importing panel ONLY at click (D1); try/except fallback (D5). Verify: 3.1 + `test_sin_pyside_ni_creacion_de_paneles`/`test_importa_nuke_a_nivel_de_modulo` green; `py_compile`.
- [x] 3.3 VERIFY — invoke command → panel imported + dialog opens (fake panel); full `pytest` green; `py_compile` all touched. Verify: suite + build gate.