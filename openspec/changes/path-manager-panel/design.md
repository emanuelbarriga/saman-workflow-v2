# Design: Path Manager Panel (Ctrl+Alt+R)

## Technical Approach

Pure/thin split (injector precedent): helper `SamanTools/ui/path_manager.py` (identity + store injected; no nuke/PySide/`os.environ`) feeds a thin `QDialog` (`path_manager_panel.py`) that renders and applies env via `injector.cachear_env` + `aplicar_entorno`. `ui/menu.py` gains one item with a lazy callback importing the panel at click time (regex guard stays green). No `core/` edits; writes consume public `guardar_perfiles`/`asegurar_perfil`.

## Architecture Decisions

| # | Decision | Options | Resolution |
|---|----------|--------------------|------------|
| D1 | Deferred PySide in menu.py | (a) Nuke string command; (b) `importlib`; (c) top-level try/except; (d) **function-local panel import** | **(d)**. Regex `^\s*(?:import\s+PySide|from\s+PySide)` (`re.M`) also matches indented imports and `from PySide6 import …` — any literal is fatal. Only (d) has none, loads PySide at click, and is invokable by `_MenuFake` (strings are never evaluated). (c) violates the guard; (b) adds indirection for no gain. |
| D2 | Unknown-user detection without write | `resolver_perfil` write-on-miss (D2/D3) → unusable; call private `_emparejar_perfil` vs. replicate D2 ladder over public `leer_perfiles` | **Replicate with source tracking.** Core is frozen, `_emparejar_perfil` private; D2 precedence (exact → user default → first hostname → `None`) is pinned by core tests. Helper `_emparejar_con_fuente()` mirrors it and reports the matched entry kind (exact/default/foreign-host), which change-base needs. Parity vs `resolver_perfil` pinned in tests (known store, no write). |
| D3 | Helper API | God-function vs. focused pure functions | Focused, all returning DATA: `estado_panel()` (read slice), `preparar_cambio_base()`, `preparar_onboarding()` (write slices, lock-safe via engine). Env deltas via `armar_estado_env(perfil, so, ruta_plato, base=…)`. |
| D4 | Widget | Compute in widget vs. render-only | Thin `PathManagerDialog(QDialog)`, V1 dual import (PySide2→PySide6, `QtAlignment` compat). Renders helper data; submit → helper → `cachear_env`/`aplicar_entorno`. `abrir_dialogo()` guards `nuke.GUI`, never raises upward. |
| D5 | Menu + shortcut | Item placement; collision policy | Item **flat on SamanTools menu** (V1 tool precedent), idempotent `findItem` guard. Constants `_ATAJO_PATH_MANAGER="Ctrl+Alt+R"`, `_ATAJO_FALLBACK_PATH_MANAGER="Ctrl+Alt+O"` (config.yaml's original key). Collision via injectable `_atajo_ocupado()` + pure `seleccionar_atajo`; real impl = try/except re-register (Nuke exposes no ownership query). Modal over Nuke's active window. |
| D6 | Testability | — | Helper Qt-free pytest; widget pytest-qt 4.5.0 + PySide6 6.10.2 (verified), `skipif` → 0%; menu reuses `test_menu.py` fakes (`addCommand` gains optional shortcut). |
| D7 | Change-base write shape | host only vs. host+default | Update the matched entry only: exact/foreign-host → `hosts[hostname]`; user-default → `default` + `hosts[hostname]`, via one `guardar_perfiles` lock; other platforms/users untouched. |
| D8 | Order | single PR vs slices | P1 helper+tests → P2 widget+tests → P3 menu integration, green each commit. |

## Data Flow

    menu.instalar() ──▶ click "Path Manager" ──▶ _abrir_path_manager()
    └─ import path_manager_panel (PySide recién aquí) ─▶ abrir_dialogo()
         ├─ identidad + store + so ─▶ estado_panel() ─▶ emparejar sin escribir
         ├─ PathManagerDialog(estado) ──exec() modal──▶ submit
         │    ├─ preparar_onboarding|cambio_base ─▶ engine (lock) ─▶ store
         │    └─ cachear_env(env) + aplicar_entorno(env) ─▶ os.environ
         └─ nuke.message(resumen) / degrade silencioso sin GUI

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `SamanTools/ui/path_manager.py` | Create | Pure helper: read + prepare slices. |
| `SamanTools/ui/path_manager_panel.py` | Create | Thin `PathManagerDialog` + `abrir_dialogo()`. |
| `SamanTools/ui/menu.py` | Modify | Item, shortcut constants, lazy callback. |
| `tests/test_path_manager.py` | Create | Helper matrix (Qt-free). |
| `tests/test_path_manager_panel.py` | Create | Widget, pytest-qt + nuke fake; `skipif` → 0%. |
| `tests/test_menu.py` | Modify | `_MenuFake` shortcut capture + new scenarios. |

## Contracts

```python
# path_manager.py — docstrings ES, ids EN. Pure (no nuke/PySide/os.environ).
def estado_panel(ruta_store, usuario, hostname, so) -> dict:
    # {"conocido": bool, "perfil": dict|None, "base_actual": str|None,
    #  "unidad": {"conectado","ruta","detalle"}}  # entorno.estado_unidad(base_actual)

def preparar_cambio_base(usuario, hostname, ruta_store, so, nueva_base, ruta_plato="") -> dict:
    # guardar_perfiles (merge, lock) -> {"perfil", "env", "unidad"}

def preparar_onboarding(usuario, hostname, ruta_store, base, so, ruta_plato="") -> dict:
    # asegurar_perfil (lock, slot-matching) -> {"perfil", "env", "unidad"}
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit (helper) | markers for all pairing sources; no write on detection (store bytes unchanged); change-base preserves other platforms+users; onboarding slotting; env delta; env snapshot unchanged | `tests/test_path_manager.py`, tmp stores, pytest puro |
| Widget | renders helper data; submit → engine write + `cachear_env`/`aplicar_entorno`; cancel leaves env unchanged; `abrir_dialogo` no-GUI silent | `tests/test_path_manager_panel.py`, pytest-qt + `_NukeFake`, real helper+injector; `pytest.importorskip("PySide6")` |
| Menu | one item, shortcut constant, no duplicate; exec w/o invocation imports no PySide (sys.modules); regex guard; collision → fallback; click → panel imported | extend `test_menu.py`; `_MenuFake` captures `shortcut`; fake panel module |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary introduced. The only subprocess (`estado_unidad` probe) is pre-existing core, untouched.

## Migration / Rollout

No migration: revert removes the item; helpers are additive; suite green per slice.

## Open Questions

- [ ] Nuke warns, not raises, when `addCommand` claims an in-use shortcut — verify in a Nuke session (non-blocking).