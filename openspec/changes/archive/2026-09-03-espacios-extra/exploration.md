# Exploration — espacios-extra

> Change: `espacios-extra` · Phase: explore · Repository: saman-workflow-v2 (public) · Date: 2026-09-03
> Research only — no code modified. All paths evidence is `file:line` on the current working tree (HEAD `68a742a`).
> Decision already made with the user (binding, not re-litigated): Option A — **arbitrary EXTRA spaces** on top of the three canonical ones, **flat schema** `{login: {ESPACIO: {SO: root}}}`, canonical = key in `("TO_VFX","COMP","FROM_VFX")`, extra = any other key at the same level. Zero migration.

## Executive Summary

The V2 pipeline hard-codes the three canonical spaces in exactly four modules (`rutas_engine`, `injector`, `path_manager`, `path_manager_panel`), each with its own `_ESPACIOS` tuple. Nearly every touch point is **key-agnostic already**: persistence (`guardar_perfiles` → `_mezclar_perfil_usuario`), lookup (`ruta_para_espacio`), env application (`aplicar_entorno`), and profile re-key (`renombrar_perfil_store`) all treat space keys generically, so extra spaces survive storage, selection, rename and injection with **zero core surgery**. The real work is concentrated in four places: (1) `variables_entorno` iterates only `_ESPACIOS` and must generalize to all profile keys; (2) **space REMOVAL cannot be done today** — the read-merge-write kernel never deletes keys, so a lock-guarded remove operation is a mandatory new engine primitive; (3) the helper's write/read surface (`preparar_cambio_base`, `raices_para_so`) validates "canonical or path-like" and must accept profile-known extra names; (4) the widget needs the extra section (dynamic rows + per-row OS selector + add/remove) while the canonical section stays fixed. Structural cut (`raiz_proyecto_desde_ruta`) and prefix detection (`_espacio_prefijado`) stay canonical-only by decision — plates under extra roots lose structural `PROJECT_ROOT` derivation, which is intended and must be documented in the spec. Scope boundary: engine+helper+widget+their tests; shim, `menu.py`, `core/entorno` markers and `get_context` semantics are explicitly out.

---

## 1. Current 3x3 flow mapped end-to-end (who touches `_ESPACIOS` / canonical logic)

### `SamanTools/core/rutas_engine.py` — engine

| Function | Lines | Interaction with spaces |
|---|---|---|
| `_ESPACIOS = ("TO_VFX","COMP","FROM_VFX")` | `rutas_engine.py:72` | module-level canonical tuple |
| `detectar_forma_perfil` | `rutas_engine.py:161-174` | shape check iterates `_ESPACIOS` (`:171`); ANY profile with ≥1 canonical dict space → `"nuevo"`; hosts/default, empty, non-dict → `"legacy"` |
| `_mezclar_perfil_usuario` | `rutas_engine.py:180-209` | merge kernel **iterates `perfil.items()` — fully key-agnostic** (`:200`); extra dict keys merge like canonical ones; non-dict value → `ValueError` (`:202`); legacy existing entry → wholesale replace (`:196-199`) |
| `guardar_perfiles` | `rutas_engine.py:212-231` | read-merge-write under lock; **never removes keys** — only adds/updates slots |
| `crear_perfil_default` | `rutas_engine.py:261-282` | builds ONLY the 3 canonical × 3 OS fictitious profile (`:271`, `:280`) — extras never onboarded |
| `ruta_para_espacio` | `rutas_engine.py:285-296` | `perfil.get(espacio, {}).get(so)` — **already works for extra names unchanged** |
| `resolver_perfil` / `asegurar_perfil` | `rutas_engine.py:302-335` | user-level lookup + onboarding; legacy replacement keeps only the incoming 3x3 — an extras-only profile would be **replaced wholesale** (edge case, §3) |
| `renombrar_perfil_store` | `rutas_engine.py:338-356` | re-keys the whole user dict (`store.pop`/`store[new]=perfil`) — **extras travel with the user for free** |
| `_espacio_prefijado` | `rutas_engine.py:416-439` | iterates `_ESPACIOS` only (`:428`) → extra roots never prefix-detect the plate (canonical-only, by decision) |
| `get_context` | `rutas_engine.py:451-490` | `espacio`/`so` from `_espacio_prefijado`; `project_root` = structural cut via `raiz_proyecto_desde_ruta` |
| `variables_entorno` | `rutas_engine.py:493-540` | iterates `_ESPACIOS` (`:530`) with `claves_knob` fallback map (`:524-528`); env key `PYTHON_<ESPACIO>`; missing root → sibling `reconstruir_rutas` (canonical only); unresolved → omitted, never `""` |

### `SamanTools/core/entorno.py` — environment helpers

| Function | Lines | Interaction |
|---|---|---|
| `PREFIJOS = ("TO_VFX","comp","FROM_VFX")` | `entorno.py:36` | V1 knob-name prefixes; `reconstruir_rutas` emits `{pre}_SERVER_{suf}` (`:182-188`) — **V1 contract, untouched** |
| `raiz_proyecto_desde_ruta` | `entorno.py:191-214` | structural cut at first marker segment, default `marcadores=("TO_VFX","COMP","FROM_VFX")` (`:191`) — canonical-only by decision; extra segments (e.g. a folder named `3D`) must NOT cut |

### `SamanTools/ui/injector.py` — load layer

| Function | Lines | Interaction |
|---|---|---|
| `_ESPACIOS_INYECTOR` | `injector.py:78` | canonical tuple for the `PROJECT_ROOT` fallback |
| `_raiz_fallback_so` | `injector.py:84-105` | current-SO root fallback for `PROJECT_ROOT` iterates canonical only (`:101`) — extras never become `PROJECT_ROOT` candidates |
| `armar_estado_env` | `injector.py:108-134` | `get_context` → forces explicit `so` (`:133`) → `variables_entorno(contexto, perfil)` — **extras flow through automatically once the engine iterates all keys** |
| `aplicar_entorno` | `injector.py:251-266` | dumps ANY dict key into `os.environ` + `__main__` — **no new injection snippet needed (confirmed)** |
| `obtener_ruta_store` | `injector.py:214-245` | store chain, space-agnostic |
| `_aplicar_precedencia` | `injector.py:300-325` | only forces `PROJECT_ROOT`; `PYTHON_*` pass through untouched |

### `SamanTools/ui/path_manager.py` — pure helper

| Function | Lines | Interaction |
|---|---|---|
| `_ESPACIOS` | `path_manager.py:90` | canonical tuple |
| `_raiz_para_so` | `path_manager.py:97-109` | first non-None root for `so`, canonical order only |
| `raices_para_so` | `path_manager.py:173-193` | returns `{espacio: raiz}` **canonical only** (dict comprehension `:190-193`) — widget advanced-mode renderer |
| `estado_panel` | `path_manager.py:196-233` | `base_actual` = `_raiz_para_so` (canonical); returns the FULL `perfil` dict (`:228-229`) — extras already inside |
| `preparar_seleccion_perfil` | `path_manager.py:236-259` | selection env via `armar_estado_env` — extras ride along once the engine produces them |
| `preparar_cambio_base` | `path_manager.py:280-333` | validation: `espacio in _ESPACIOS` (`:312`) → per-space slot; `_es_ruta_aparente` (`:316`) → transient TODOS mode; else `ValueError` (`:322-325`) — **an extra name like `3D` currently hits the ValueError branch** |
| `guardar_base_unificada` | `path_manager.py:336-368` | simple mode, canonical trio only |
| `cargar_seleccion`/`guardar_seleccion` | `path_manager.py:416-477` | per-store selection, space-agnostic |

### `SamanTools/ui/path_manager_panel.py` — widget (thin)

| Function | Lines | Interaction |
|---|---|---|
| `_ESPACIOS` / `_AVANZADOS` | `path_manager_panel.py:80`, `:84-88` | canonical order COMP→FROM_VFX→TO_VFX (mockup) |
| `_construir_modo_normal` | `path_manager_panel.py:180-278` | simple container (`:193-220`), advanced checkbox (`:222-227`), advanced group rendered from `_AVANZADOS` (`:229-263`), buttons (`:265-275`) |
| `_refrescar_campos_activo` | `path_manager_panel.py:401-423` | base = first canonical root (`:415-419`); per-field from `raices_para_so` (`:421-423`) |
| `guardar` | `path_manager_panel.py:577-622` | simple → `guardar_base_unificada`; advanced → per-space `preparar_cambio_base` (`:602-609`) |
| `abrir_dialogo` | `path_manager_panel.py:641-680` | modal entry; refreshes `listar_perfiles` per open |

### `SamanTools/ui/menu.py` + `SamanTools/rutas.py` (shim)

- `menu.py:_abrir_path_manager` (`menu.py:211-237`) — entry point; **unchanged** by this change.
- `rutas.py:_reescribir_proyecto_en_rutas` (`rutas.py:58-81`) — regex matches canonical markers only; `_env_desde_knobs` reads only `*_SERVER_*` knob names (V1 contract). Extras have no knob representation → shim **untouched** (documented, out of scope).

---

## 2. Where extra keys touch — per pipeline stage

| Stage | Today | With extras |
|---|---|---|
| **Validation** | `preparar_cambio_base` (`path_manager.py:312-325`): canonical or path-like, else `ValueError`; `_mezclar_perfil_usuario` (`rutas_engine.py:202`) raises on non-dict space value | New pure validation at UI entry: sanitize name (upper, alphanumeric, space→underscore), reject empty, canonical dupes (case-insensitive), reserved names, duplicates among extras. Store the **sanitized** name as the profile key |
| **Normalization/repair** | `_normalizar_ruta` (`path_manager.py:118-127`); `detectar_forma_perfil` canonical presence | `_normalizar_ruta` applies to extra roots identically. `detectar_forma_perfil` **stays canonical-only** — extras never make a profile "nuevo" by themselves (edge case §3) |
| **Store read/merge** | `_mezclar_perfil_usuario` (`rutas_engine.py:180-209`) key-agnostic | Merges extra slots automatically; **removal is impossible** (`guardar_perfiles` never deletes) → new lock-guarded `eliminar_espacio_store(path, user, espacio)` engine primitive required |
| **Envelope** | `leer_perfiles`/`_escribir_perfiles` preserve unknown top-level keys | No change; extra keys at the *user* level are plain JSON |
| **Env dict** | `variables_entorno` iterates `_ESPACIOS` + `claves_knob` sibling fallback (`rutas_engine.py:524-538`) | Iterate ALL profile keys: canonical keep the sibling fallback; **extra without fallback → omitted if root missing** (fixed requirement). Key = `PYTHON_` + sanitized name; canonical-first, extras sorted, for deterministic output. `claves_knob` map stays canonical-only |
| **PROJECT_ROOT derivation** | `raiz_proyecto_desde_ruta` canonical markers; `_raiz_fallback_so` canonical | Unchanged (canonical-only, fixed requirement). Plate under an extra root → no structural cut → injector falls to base/current-SO-root fallback; env still gains `PYTHON_<EXTRA>` via the explicit-`so` override in `armar_estado_env` (`injector.py:133`) |
| **UI rendering** | canonical section from `_AVANZADOS` (`path_manager_panel.py:84-88`) | Canonical section fixed on top (unchanged); NEW extra section below: dynamic rows `[name][path][Buscar...][OK][-]`, per-row OS selector (`macOS|Windows|Linux`), `[ + Agregar espacio extra ]`, OS-detected label (`entorno.detectar_so()`) |
| **Selection** | `preparar_seleccion_perfil` → `armar_estado_env` | Extras ride along once `variables_entorno` iterates all keys; no helper signature change needed |
| **Rename** | `renombrar_perfil` re-keys the user (profile name dialog) | **Extras travel automatically** (`renombrar_perfil_store` pops/re-keys the whole dict). Per-space rename is NOT in the wireframe — out of scope |
| **Unit status** | `estado_panel` on `base_actual` (canonical first root); per-field semaphore via `estado_unidad` | Per-extra-row semaphore uses the same `entorno.estado_unidad` (timeout+cache) on the row's root for the row's selected OS; empty/missing root → existing "Ruta base vacia" disconnected state (`entorno.py:142-147`) |
| **OS selector** | SO fixed at dialog level (`so` param) | Per-row selector overrides which OS slot the OK button writes/reads; detected OS shown as info label |

---

## 3. Edge cases

1. **Name sanitization** — rule (fixed): key = `PYTHON_` + name UPPER, alphanumeric kept, space→underscore. Concrete proposal: uppercase; every char not `A-Z0-9` → `_`; collapse runs; strip leading/trailing `_`; empty after sanitize → reject. `3D` → `PYTHON_3D`, `MATTE PAINT` → `PYTHON_MATTE_PAINT`. Canonical names are already identity-stable (`TO_VFX` keeps its underscore). Store the sanitized name as the profile key.
2. **Duplicate/reserved rejection** — reject: (a) sanitized name equal to a canonical space (case-insensitive, any of `TO_VFX|COMP|FROM_VFX` — otherwise it would collide with the fixed `PYTHON_*` trio); (b) sanitized name equal to another extra already present in the profile (two inputs mapping to one key); (c) the literal name `PROJECT_ROOT` (decision lists it as reserved — the profile-level key stays unambiguous); (d) empty. The exact scope of "reserved" (literal `PROJECT_ROOT` vs any `PYTHON_*` env key) should be pinned in the spec — see Risk R2.
3. **Missing root for the current OS** — extra has no sibling fallback (fixed): `PYTHON_<EXTRA>` is OMITTED (never `""`), the row renders empty and the semaphore shows disconnected; the user switches the row OS selector to the OS that has a root. Canonical spaces keep the `reconstruir_rutas` sibling fallback unchanged (`rutas_engine.py:536-537`).
4. **Extras-only profile (hand-edited/legacy store)** — `detectar_forma_perfil` returns `"legacy"` for a profile with extras but no canonical space; `asegurar_perfil`/`_mezclar_perfil_usuario` then **replaces the entry wholesale**, losing the extras. The UI always keeps the fixed canonical section, so this can't originate from the panel — but the spec MUST state the behavior and recommend: canonical presence remains the shape criterion; document the data-loss risk for hand-edited stores (or, if desired, treat any-dict-key as `"nuevo"` — requires a decision; NOT recommended because legacy `hosts`/`default` are also dicts... actually they hold dict values too, so any-dict-key detection would misclassify legacy — canonical-only is the safe rule).
5. **Legacy store handling** — zero migration (fixed): existing stores with only canonical keys load and behave identically; legacy (`hosts`/`default`) detection and regeneration are untouched; adding an extra is a normal per-space merge write.
6. **Name colliding with legacy keys (`hosts`/`default`)** — a new-shape profile containing a canonical space plus an extra literally named `hosts` is still `"nuevo"` and merges fine; only an extras-only `hosts`/`default` profile is misread as legacy. Recommend rejecting `hosts`/`default` as extra names for hygiene (optional, spec decision).
7. **`preparar_cambio_base` ordering** — must accept any **profile-known** space key (canonical or existing extra) before the transient TODOS path-like branch, preserving both current tests (`test_cambio_base_todos_compat_widget_antes_de_s4`, `test_cambio_base_espacio_no_canonico_ni_ruta_lanza`). An extra whose name contains `/` cannot exist (creation-time sanitization rejects it), so the "name vs path" ambiguity never arises.
8. **Determinism** — env dict and `raices_para_so` must emit canonical keys first (canonical order), extras sorted, so identical inputs yield identical dicts (engine/holder purity contract).
9. **Widget test surface (canonical section intact)** — `test_path_manager_panel.py:537-540` asserts `list(dialogo.campos_avanzados) == ["COMP","FROM_VFX","TO_VFX"]` — the canonical section must remain exactly these three fields; the extra section must be a separate widget subtree.
10. **Removal via merge is impossible** — verified: `_mezclar_perfil_usuario` (`rutas_engine.py:200-209`) and `guardar_perfiles` only add/update slots; passing a profile *without* an extra leaves the extra in the store. A `-` row button therefore requires the new engine primitive (or a full user-dict replace variant — the merge kernel would need a new branch; a dedicated remove is cleaner and lock-safe like `renombrar_perfil_store`).

---

## 4. Approaches

The user decision (Option A, flat schema) fixes the *what*; these are the open implementation strategies:

1. **Flat generalization (recommended)** — generalize `variables_entorno` to iterate all profile keys; add pure name-sanitizer + validation in the helper; add `eliminar_espacio_store` under the existing lock; extend `raices_para_so`/`preparar_cambio_base` around profile-known keys; extra section in the widget.
   - Pros: zero migration, maximal reuse of the key-agnostic kernel, engine purity intact, no new injection snippet.
   - Cons: `detectar_forma_perfil` stays canonical-only (extras-only edge documented); more surface in one change (engine+helper+widget).
   - Effort: Medium.

2. **Helper-side env synthesis** — keep `variables_entorno` canonical-only; the helper post-processes the env dict to append `PYTHON_<EXTRA>` from the profile.
   - Pros: engine untouched.
   - Cons: duplicates the env contract in the UI layer (breaks the single-source-of-truth TCL contract), diverges from the purity layering (`core` owns env semantics); rejected on architectural grounds.

3. **Nested schema `canonical`/`espacios_extra`** — structurally separate canonical from extras.
   - Pros: explicit modeling.
   - Cons: REQUIRES migration of every store (violates the zero-migration fixed requirement); touches `detectar_forma_perfil`, `_mezclar_perfil_usuario`, `crear_perfil_default`, all reads; user already rejected it.

---

## 5. Recommendation and scope boundary (first slice)

**Recommendation: Approach 1 — flat generalization**, kept minimal:

- `core/rutas_engine.py`:
  - Add pure `_clave_env_para_espacio(nombre)` sanitizer (upper, alphanumeric, space→underscore).
  - `variables_entorno`: iterate ALL profile keys — canonical first (canonical order, sibling `reconstruir_rutas` fallback unchanged), then extras sorted (profile root for the context `so`, no fallback, omitted if missing).
  - Add lock-guarded `eliminar_espacio_store(path, user, espacio)` (mirrors `renombrar_perfil_store`: read under lock, remove key, atomic write).
  - `_ESPACIOS`, `detectar_forma_perfil`, `crear_perfil_default`, `_espacio_prefijado`, `get_context`: **unchanged**.
- `ui/path_manager.py`:
  - Pure validation helpers: `sanitizar_espacio_extra(nombre, perfil)` implementing §2/§3 rejection rules (returns sanitized name, raises `ValueError` with clear messages).
  - Extend `raices_para_so` to include extras (canonical first, extras sorted) — existing canonical-only tests stay green.
  - Extend `preparar_cambio_base` accept-list to `espacio in _ESPACIOS or espacio in perfil` before the path-like TODOS branch.
  - New write helpers: add extra space (validate name → merge `{user: {nombre: {so: root}}}`, reuse `guardar_perfiles`) and remove extra space (delegates to `eliminar_espacio_store`).
- `ui/path_manager_panel.py`: canonical section untouched on top; add the extra section (dynamic rows `[name][path][Buscar...][OK][-]`, per-row OS selector, `[ + Agregar espacio extra ]`, OS-detected info label); wire OK/`-`/add to the helpers; propagate env through the existing `cachear_env` + `aplicar_entorno` path only.
- Tests: engine (extras in env contract, sanitizer, remove op, omission when root missing), helper (validation, add/remove, cambio_base with extra), panel (extra rows render, add/remove wiring, canonical section assertions `test_path_manager_panel.py:537-540` kept).

**Explicitly OUT of scope (first slice):** `core/entorno` markers/`raiz_proyecto_desde_ruta` (canonical-only, fixed), `_espacio_prefijado` participation of extras, `get_context` semantics, `SamanTools/rutas.py` shim, `menu.py` entry, per-space rename, `reconstruir_rutas`/V1 knob contract.

**Envelope note:** no new main spec files; this change MODIFIES `core-rutas-engine` (env exposure + store write surface) and `panel-path-manager-helper`/`panel-path-manager-widget` (extras UI + validation). `load-injector`, `panel-path-manager-menu`, `core-entorno`: no delta.

---

## 6. Risks

- **R1 — Removal gap:** space deletion is impossible through `guardar_perfiles`' merge kernel; the new `eliminar_espacio_store` must be lock-safe and race-tested like `renombrar_perfil_store`.
- **R2 — Reserved-key semantics ambiguity:** the decision lists "PROJECT_ROOT, PYTHON_*" as reserved, but `PYTHON_` + extra name can only collide with the canonical trio when the name IS canonical. Pin the exact rule in spec (recommended: reject canonical dupes case-insensitively + literal `PROJECT_ROOT` + intra-extra dupes after sanitize).
- **R3 — Extras-only profile data loss:** a hand-edited store with extras but no canonical space is classified `"legacy"` and replaced wholesale on next write (extras lost). Must be documented; UI prevents it by construction.
- **R4 — `preparar_cambio_base` ordering change:** accepting profile-known keys before the TODOS branch must not break `test_cambio_base_todos_compat_widget_antes_de_s4` / `test_cambio_base_espacio_no_canonico_ni_ruta_lanza`.
- **R5 — Widget churn:** the panel test surface is ~1050 lines; the extra section must be a separate subtree so existing canonical assertions (`campos_avanzados` key order, simple/advanced flows) stay green.
- **R6 — PROJECT_ROOT ambiguity for extras:** plates under extra roots get no structural cut (canonical-only, fixed); artists may perceive `PROJECT_ROOT` as "wrong" — the spec must document that extras are env-only, never root-derivation markers.
- **R7 — Canonical tuple drift:** `_ESPACIOS` is duplicated in 4 modules (plus `entorno.PREFIJOS`); the change must keep all canonical definitions consistent and, ideally, add one test asserting they agree.
- **R8 — Public-repo hygiene:** extras are arbitrary user input — validation must also guard against absurd names that could look like paths or reserved JSON keys; no real studio paths in fixtures.

## Ready for Proposal

Yes. The orchestrator should tell the user: Option A is fully compatible with the existing key-agnostic core — the only genuinely new engine primitive is a lock-guarded space-removal operation (deletion is impossible through the merge kernel today), plus the env-iteration generalization in `variables_entorno`. The first slice is engine + helper + widget + tests; structural-cut/PROJECT_ROOT semantics and the V1 shim stay canonical-only by design. Two small spec-time decisions remain: the exact reserved-key rejection rule (R2) and whether to also reject `hosts`/`default` as extra names (§3.6).