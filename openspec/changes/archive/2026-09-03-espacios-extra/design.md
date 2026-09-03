# Design: Extra Spaces (espacios-extra)

## Technical Approach

Flat generalization (Option A, binding): reuse the key-agnostic merge kernel and the existing `injector.aplicar_entorno` dump; the only new engine primitive is a lock-guarded removal op. Extras are profile keys at the same level as canonical spaces, stored under their UPPERCASE sanitized name; env key = `"PYTHON_" + _clave_env_para_espacio(nombre)`. Three modules change: `rutas_engine` (all-key env iteration, sanitizer, `eliminar_espacio_store`), `path_manager` (validation + widened accept-list + add/remove helpers), `path_manager_panel` (separate extras subtree).

## Architecture Decisions

| # | Decision | Options considered | Chosen | Rationale |
|---|----------|-------------------|--------|-----------|
| D1 | Canonical removal guard | allow any key / silent no-op / **reject** | `eliminar_espacio_store` raises `ValueError` for `espacio in _ESPACIOS` (inside the lock, before pop) | The canonical trio is the fixed 3x3 shape invariant (`detectar_forma_perfil:171`, `crear_perfil_default:271`, widget canonical section). Silent removal corrupts the shape and is bypassable if only the helper guards; the widget removes extras only. |
| D2 | OS-selector default for new rows | always macOS / last-used / **dialog current `so`** | New rows default the per-row OS combo to `self.so` (production value = `entorno.detectar_so()` at `abrir_dialogo:664`) | First root a user types lands in the slot they are looking at; deterministic in tests (injected `so`), no hidden state. |
| D3 | Sorting stability | insertion order / **lexicographic `sorted()`** | Extras iterate via `sorted(k for k in perfil if k not in _ESPACIOS)`; canonical first in `_ESPACIOS` order. Same in `raices_para_so` | Insertion order depends on edit history (non-deterministic across stores); codepoint sort is total and stable → identical inputs yield identical env dicts and `{espacio: raiz}` dicts (engine/helper purity contract). |
| D4 | Unsanitizable store key in env assembly | raise / **omit** | `variables_entorno` wraps `_clave_env_para_espacio` per extra in try/except `ValueError` → `continue` (omit) | Env assembly must stay total: `armar_estado_env` is on the load path and must not break on a hand-edited store. Mirrors AD7 "irresoluble → omitida, nunca `""`". |
| D5 | `_copia_con_slot` key set | keep canonical-only / **iterate all `perfil` keys** | Loop over `perfil.items()` instead of `_ESPACIOS` (`path_manager.py:148-154`) | Canonical-only rebuild silently drops extras from `res["perfil"]` and the env delta, breaking the spec scenario "env delta carries PYTHON_3D". Extras keep their other-OS roots. |
| D6 | Extras subtree lifecycle | fold into `guardar()` / **self-contained rows** | Extras live in `self.grupo_extras` (added after `grupo_avanzado`, visible only when advanced checkbox is checked, wired in `_alternar_avanzado`); `guardar()` persists ONLY `campos_avanzados` (unchanged); rows persist via their own `OK`/`[-]` | Keeps the two must-green widget assertions (`campos_avanzados` order at `test_path_manager_panel.py:537-540`; checkbox toggle at `:501-522`) untouched; separate subtree is the R5 containment. |
| D7 | `eliminar_espacio_extra` signature | spec-minimal `(usuario, ruta_store, espacio)` / **add `so`** | `eliminar_espacio_extra(usuario, ruta_store, espacio, so)` | The mandated `{"perfil","env","unidad"}` return needs `so` for `armar_estado_env` and `_raiz_para_so`; the widget always has `self.so`. Documented deviation from the spec's minimal signature. |
| D8 | Existing-row name editing | editable name per row / **fixed label** | Rows render the extra name as a non-editable `QLabel`; only the add-row template has an editable, validated name field | Per-space rename is explicitly out of scope (exploration §1); editing would imply a rename feature. |

## Data Flow

    Widget extras row ──OK──> path_manager.preparar_cambio_base(espacio=extra)   ──> engine.guardar_perfiles (lock, read-merge-write; _copia_con_slot keeps extras)
    Widget add row     ──> path_manager.agregar_espacio_extra (sanitizar → merge) ──> engine.guardar_perfiles
    Widget [-] row     ──> path_manager.eliminar_espacio_extra                  ──> engine.eliminar_espacio_store (lock, read-pop-write)
                                        │
                                        └──> injector.armar_estado_env ──> engine.variables_entorno(contexto, perfil=perfil)   (canonical first + sorted extras)
                                        └──> widget: injector.cachear_env + aplicar_entorno (thin, sole env writer — as today)
    Rendering: widget rows <── path_manager.raices_para_so(usuario, ruta_store, row_so)  (canonical first, extras sorted)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `SamanTools/core/rutas_engine.py` | Modify | Add `_clave_env_para_espacio` (near `_ESPACIOS`); generalize `variables_entorno` loop (`:530-539`); add `eliminar_espacio_store` (mirror `renombrar_perfil_store` `:338-356`, `_lock_perfiles`); canonical guard per D1. `_ESPACIOS`, `detectar_forma_perfil`, `crear_perfil_default`, `_espacio_prefijado`, `get_context`: untouched. |
| `SamanTools/ui/path_manager.py` | Modify | Add `sanitizar_espacio_extra(nombre, perfil)`; extend `raices_para_so` (`:190-193` → canonical + sorted extras); `_copia_con_slot` iterates all keys (D5); `preparar_cambio_base` accept-list: `espacio in _ESPACIOS` → `espacio in perfil` → `_es_ruta_aparente` → `ValueError` (`:312-325`); add `agregar_espacio_extra` + `eliminar_espacio_extra`. R3: docstring documents extra-only legacy replace; `estado_panel.legacy` already flags it read-only. |
| `SamanTools/ui/path_manager_panel.py` | Modify | `self.grupo_extras` subtree after `grupo_avanzado` (`:263`): rows `[name label][path][Buscar...][OK][-]` + per-row OS combo (default `self.so`); `[ + Agregar espacio extra ]`; detected-OS info label (shows `self.so`); semaphores via `entorno.estado_unidad` per selected OS (empty root → "Ruta base vacia" disconnected); add/OK/`[-]` wired to helpers; env only via `cachear_env`+`aplicar_entorno`. Canonical section `:229-263` byte-identical. |
| `tests/test_rutas_engine.py` | Modify | New tests below; existing env/sibling tests (`:677-734`) must stay green. |
| `tests/test_path_manager.py` | Modify | New helper tests; the two tests at `:459`/:477 stay green unmodified (guard re-run). |
| `tests/test_path_manager_panel.py` | Modify | Extras-subtree tests; `:537-540` assertion untouched (guard). |
| `tests/test_injector.py` | Modify | 1–2 env-through-injector tests with extras. |
| `openspec/changes/espacios-extra/design.md` | Create | This document. |

## Interfaces / Contracts

```python
# engine (core)
def _clave_env_para_espacio(nombre) -> str:
    # UPPER → [^A-Z0-9]+ → "_"; collapse via regex; strip("_");
    # reject empty-after-strip, "/{}" (R8), "HOSTS"/"DEFAULT" (R2) → ValueError
def eliminar_espacio_store(path, user, espacio) -> dict:
    # _lock_perfiles: re-read store; user absent → ValueError; espacio in _ESPACIOS → ValueError (D1);
    # pop only target key if present; _escribir_perfiles; return internal dict.

# helper (ui, pure)
def sanitizar_espacio_extra(nombre, perfil) -> str:
    # s = rutas_engine._clave_env_para_espacio(nombre)   # single source of truth (underscore-private, same package)
    # s in _ESPACIOS → ValueError; s == "PROJECT_ROOT" → ValueError;
    # s in {k for k in perfil if k not in _ESPACIOS} → ValueError (intra-extra dup); return s
def agregar_espacio_extra(usuario, ruta_store, so, nombre, nueva_ruta) -> {"perfil","env","unidad"}
def eliminar_espacio_extra(usuario, ruta_store, espacio, so) -> {"perfil","env","unidad"}
# raices_para_so / preparar_cambio_base: signatures unchanged.
```

`variables_entorno` iteration (replaces `:530-539`):

```python
extras = sorted(k for k in perfil if k not in _ESPACIOS) if perfil else []
for espacio in list(_ESPACIOS) + extras:
    root = None
    raices = perfil.get(espacio) if perfil else None
    if isinstance(raices, dict):
        root = raices.get(so)
    if root is None and espacio in _ESPACIOS and reconstruidas is not None:
        root = reconstruidas.get(claves_knob[espacio] + suf)   # sibling fallback: canonical only
    if not root:
        continue
    if espacio in _ESPACIOS:
        clave = "PYTHON_" + espacio
    else:
        try:
            clave = "PYTHON_" + _clave_env_para_espacio(espacio)
        except ValueError:
            continue                                    # D4: omit, never raise, never ""
    env[clave] = str(root).replace("\\", "/").strip().rstrip("/")
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (engine) | Sanitizer valid/rejected (`3D`, `matte paint`, `foo/bar`, `{}`, `---`, empty, `hosts`, `default`) | New pure tests |
| Unit (engine) | Env: extras sorted after canonical trio; missing extra root → key omitted, no `""`; dirty hand-edited key sanitized or omitted; canonical sibling fallback intact | New tests + existing `test_env_*` (`test_rutas_engine.py:677-734`) re-run as guards |
| Unit (engine) | `eliminar_espacio_store`: removes only target key (ana keeps canonicals + PREVIEW, pedro unchanged); absent key → no-op byte-identical; unknown user → `ValueError`; canonical → `ValueError` (D1) | New tests, assert via `_bytes_store`-style snapshot |
| Race (engine) | Concurrent removals of different extras of the same user both persist | Mirror the barrier harness `test_guardar_concurrente_multiproceso_no_pierde_perfiles` (`:387-406`): 2 processes, `Barrier(2)`, workers remove `"3D"`/`"PREVIEW"`; final store has neither, canonicals intact, no temp files; skipif win32 |
| Agreement | 4 module `_ESPACIOS` sets equal; `entorno.PREFIJOS` excluded (V1-cased `comp`) | New test importing `rutas_engine`, `injector`, `path_manager`, `path_manager_panel` (+ panel needs PySide guard) |
| Unit (helper) | `sanitizar_espacio_extra` 7 rejection scenarios + valid; `raices_para_so` canonical-first + sorted extras; add/remove persist + env delta + no `os.environ` touch; `preparar_cambio_base` accepts profile-known extra (spec scenario), preserves extras and their other-OS roots (D5) | New tests; `test_cambio_base_todos_compat_widget_antes_de_s4` + `test_cambio_base_espacio_no_canonico_ni_ruta_lanza` re-run unmodified (R4 guards) |
| Widget | `campos_avanzados` stays `["COMP","FROM_VFX","TO_VFX"]`; extras in separate subtree; rows render name+root+semaforo; per-row OS switch → disconnected state and back; add validates/persists/env (spy `cachear_env`/`aplicar_entorno`, `_spy_aplicar_env:203` pattern); invalid name surfaced via `nuke.message`, no write; `[-]` removes and re-applies env; detected-OS label | New qtbot tests; `:537-540` and toggle tests untouched |
| Via injector | Env through `armar_estado_env` includes extras sorted, omits missing | 1–2 new tests |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary is introduced. (`entorno.estado_unidad` subprocess pre-exists; it is reused, not changed.)

## Migration / Rollout

No migration. Store schema unchanged (flat `{login:{ESPACIO:{SO:root}}}`); existing stores load identically; `eliminar_espacio_store` is a new op never invoked by old code. Determinism: canonical-first + `sorted()` + stable sanitizer keep identical inputs → identical outputs. Rollback: revert the commit; extra keys remain valid JSON and are simply not iterated by the prior `variables_entorno`. No flags or phased rollout.

## Open Questions

- None blocking. Minor: D7 adds `so` to `eliminar_espacio_extra` beyond the spec's minimal signature (documented decision).