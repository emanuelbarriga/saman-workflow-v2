# Exploration — perfil-por-usuario

> Change: `perfil-por-usuario` · Phase: explore · Repository: saman-workflow-v2 (public) · Date: 2026-09-03
> Research only — no code modified. All paths evidence is `file:line` on the current working tree (HEAD `97a8599`).

## Executive Summary

The V2 profile model is wrong for the studio and must be corrected end-to-end (engine → store chain → Path Manager):

1. **New profile model (user-decided, binding):** a profile is a **username** carrying **independent roots for the three spaces (`TO_VFX` / `COMP` / `FROM_VFX`) per platform** — the V1 model where each space can live on a different disk (evidence: V1 `nodos/Rutas.nk`: ARTIST `TO_VFX=/mnt/wupm/HTLR/TO_VFX/`, `COMP=/mnt/media/2026/HTLR/COMP/`, `FROM_VFX=/mnt/RedDeArtistas/HTLR/FROM_VFX/`). NOT the current "single base per user+hostname with hosts/default" model.
2. **New store location:** `{project_root}/.saman/nuke_profiles.json`; project root derived from the file open in Nuke (`/Volumes/wupm/2026/HTLR/COMP/EP_107/x.nk` → `/Volumes/wupm/2026/HTLR`).
3. **Path Manager gets a profile selector (combo):** lists usernames from the store; selecting one applies its per-platform space roots.

The change is **schema-breaking with regeneration** (the old store at `~/.config/saman/nuke_profiles.json` is dev data of an unreleased V2), the **hostname level disappears** (ladder collapses to a user lookup), the **store chain gets the project root as first link**, and the affected specs are **MODIFIED** (with a small set of ADDED requirements). Findings, decisions and open product questions below.

---

## A. Core engine impact (`SamanTools/core/rutas_engine.py`)

### A1. What depends on the hostname level today

Current envelope D1: `{"perfiles": {usuario: {"hosts": {host: roots}, "default": roots}}}` (`rutas_engine.py:9`).

Hostname-dependent machinery:

| Function | Lines | Role |
|---|---|---|
| `_mezclar_perfil_usuario` | `rutas_engine.py:151-176` | merge kernel: per-host `hosts[...]` + replace `default` |
| `_merge_perfil` | `rutas_engine.py:179-188` | writes `hosts[hostname]` **and** `default` (fallback for other machines) |
| `guardar_perfiles` | `rutas_engine.py:191-208` | read-merge-write per user through `_mezclar_perfil_usuario` |
| `_emparejar_perfil` | `rutas_engine.py:254-287` | precedence ladder: exact user+host → user-only `default` → hostname-only foreign → `None` |
| `ruta_para_plataforma` | `rutas_engine.py:290-299` | per-OS root lookup on a *roots* dict |
| `crear_perfil_default` | `rutas_engine.py:227-248` | per-OS roots for one base (slot-matching) |
| `asegurar_perfil` | `rutas_engine.py:302-322` | onboarding under lock; re-resolve race → `_merge_perfil` |
| `resolver_perfil` | `rutas_engine.py:325-337` | ladder match, else onboarding |
| `_base_prefijada` | `rutas_engine.py:400-418` | first profile root prefixing the plate path |
| `get_context` / `variables_entorno` | `rutas_engine.py:436-497` | base+so derivation from profile roots / env contract built on `reconstruir_rutas(base, proyecto)` |
| `_lock_perfiles` | `rutas_engine.py:615-632` | **schema-independent** (locks `path + ".lock"`, never the target — immune to shape changes) |

The hostname level is also mirrored in the helper: `_emparejar_con_fuente` (`ui/path_manager.py:49-79`) replicates the ladder with source tracking (`exact`/`default`/`foreign-host`), and `estado_panel` / `detectar_desconocido` / `preparar_cambio_base` consume it (`ui/path_manager.py:103-147, 153-190`).

### A1. Decision — profile shape and hostname

Proposed shape (matches V1 and the user's wording "TO_VFX / COMP / FROM_VFX por plataforma"):

```json
{"perfiles": {
  "emanuel": {
    "TO_VFX":   {"macOS": "/mnt/wupm/HTLR/TO_VFX",   "Windows": "L:/2026/HTLR/TO_VFX",   "Linux": "/mnt/wupm/HTLR/TO_VFX"},
    "COMP":     {"macOS": "/mnt/media/2026/HTLR/COMP", "Windows": "L:/2026/HTLR/COMP",     "Linux": "/mnt/media/2026/HTLR/COMP"},
    "FROM_VFX": {"macOS": "/mnt/RedDeArtistas/HTLR/FROM_VFX", "Windows": "L:/2026/HTLR/FROM_VFX", "Linux": "/mnt/RedDeArtistas/HTLR/FROM_VFX"}}}}
```

- Resolver becomes `perfiles.get(user)` → dict or miss. The ladder (`_emparejar_perfil`) and the whole `hosts`+`default` merge machinery die.
- **PRODUCT DECISION (flag): keep `hostname` in public signatures (ignored, compat) or remove it?** Removing is cleaner (V2 is new; profile scope is the user, not the machine) but touches every engine/helper/panel call site and ~20 test fixtures (`tests/test_rutas_engine.py:88-499`, `tests/test_path_manager.py:86-231`, `tests/test_path_manager_panel.py:132-233`). Keeping it as an ignored parameter halves churn but leaves a dead parameter that misleads. **Recommendation: remove.** The "hostname-only foreign" ladder (shared workstation, unknown user) also disappears — a user absent from the store is simply unknown (onboarding), no third-party host fallback.
- `ruta_para_plataforma(perfil, so)` needs a space dimension (e.g. `ruta_para_espacio(perfil, espacio, so)`), and `crear_perfil_default` must build the 3-space × 3-OS shape (default: one base per OS injected into all three spaces — the V1 macOS/Windows default; ARTIST default may differ per space, as V1 shows).

### A2. Breaking vs additive (schema migration)

- **Evidence:** the old-schema store EXISTS: `~/.config/saman/nuke_profiles.json` holds `{"perfiles": {"emanuel": {"hosts": {"iMac-de-Emanuel.local": {...}}, "default": {...}}}}` (dev machine, unreleased V2). `leer_perfiles` (`rutas_engine.py:102-115`) validates only the `perfiles` envelope key — it does not validate per-user shape, so a legacy user dict would load and then be misread by a new resolver (user dict without space keys).
- **Decision (mostly technical): BREAKING schema + regeneration.** Migration to the old shape cannot be lossless anyway: old roots are per-year bases (`/Volumes/wupm/2026`), while new roots are per-space roots (`/Volumes/wupm/2026/HTLR/TO_VFX`); the project segment cannot be fabricated. V2 has no real user data, so: the engine **detects the legacy shape** (user dict has `hosts`/`default` and no space keys) and treats it as unknown → onboarding writes the new shape on first resolve. The old home store is regenerated (or optionally ignored).
- **PRODUCT DECISION (flag):** on legacy-shape detection, regenerate **silently** (V2 is pre-release, friction-free) vs **warn** (surfaces the reset). Recommend silent for this change; the store path is moving per-project anyway, so home only matters as fallback.

### A3. `reconstruir_rutas` — obsolete?

- Today `variables_entorno` (`rutas_engine.py:473-497`) derives `PYTHON_TO_VFX/COMP/FROM_VFX` from ONE base via `reconstruir_rutas(base, proyecto)` (`core/entorno.py:169-188`).
- **Decision (technical): NOT obsolete — demoted to fallback.** Primary env source becomes the profile's own space roots for the current SO (`PYTHON_TO_VFX = perfil["TO_VFX"][so]`, etc.). `reconstruir_rutas` keeps two jobs: (1) fallback when a profile omits one space root (derive it from another space's root base + proyecto if derivable); (2) the V1 legacy knob contract — spec `core-entorno` "Knob route reconstruction" MUST stay untouched because the V1 shim (`SamanTools/rutas.py:_env_desde_knobs`, `rutas.py:249-274`) and saved comps depend on the `comp_SERVER_*` (lowercase) knob names.
- Note: `get_context`/`_base_prefijada` (`rutas_engine.py:400-470`) derive `base`/`so` from the profile's roots — with independent per-space roots there may be **no common parent** (V1 ARTIST proves it). Flag for design: what `PROJECT_ROOT` means when the three spaces don't share a parent (recommendation: `PROJECT_ROOT` = the space root of the space the open file lives in, truncated at the project segment when possible).

---

## B. Store chain (`SamanTools/ui/injector.py` + `core/entorno.py`)

### B4. Where the project root comes from

- The plate path is read in the ui layer from `nuke.root().name()`: `menu.py:126-129` (`ruta_plato = str(getattr(root, "name", lambda: "")() or "")`).
- Available `core.entorno` functions: `rutas_base(so, extra)` (`entorno.py:61-89`), `primera_ruta_disponible(so, extra)` (`entorno.py:161-166`), `proyecto_desde_ruta(ruta, base=None, so=None)` (`entorno.py:191-225`), `reconstruir_rutas` (`entorno.py:169-188`), `estado_unidad` (`entorno.py:135-158`).
- **Critical evidence:** the real share `/Volumes/wupm/2026` is NOT in `rutas_base("macOS")` (only fictitious `/Volumes/estudio/2026`, `/Volumes/estudioCloud/2026`). So base-detection via `proyecto_desde_ruta` **misses** the user's own example (`/Volumes/wupm/2026/HTLR/...nk` → `None`).
- **Decision (technical, recommended): structural cut is the primary rule.** The convention "the project root is the segment immediately before `TO_VFX|COMP|FROM_VFX`" is already established in V1: `_reescribir_proyecto_en_rutas` regex `/\/[^/]+\/(TO_VFX|COMP|FROM_VFX)(\/|$)/` (`SamanTools/rutas.py:58-81`, inherited from the V1 gizmo). Cutting the plate path at the first `TO_VFX/`|`COMP/`|`FROM_VFX/` marker (case-insensitive, backslash-normalized) yields `/Volumes/wupm/2026/HTLR` from `/Volumes/wupm/2026/HTLR/COMP/EP_107/x.nk`, and `L:/2026/HTLR` from `L:/2026/HTLR/TO_VFX/...` — base-agnostic, exactly the user's example. **Secondary rule:** `proyecto_desde_ruta` + base → `root = base + "/" + proyecto` when a known base prefixes the path. Fallback: `None` (→ home store).
- **DESIGN DECISION (flag): where the new pure function lives** — `core.entorno` (`raiz_proyecto_desde_ruta(ruta, so=None)`, alongside `proyecto_desde_ruta`) vs `core.rutas_engine`. Recommend `core.entorno` (path-shape logic, stdlib-only, testable without nuke); it becomes an ADDED requirement in the `core-entorno` spec.
- Store probe on a possibly-dead mount: `os.path.isfile("{root}/.saman/nuke_profiles.json")` can hang on a dead SMB share — shall reuse the timeout+cache guarded check pattern (`entorno.estado_unidad`, `entorno.py:92-158`) or a cheap bounded stat; flag for design (risk R2).

### B5. New chain order and fallback

- New order (user-decided): **project root store → `NUKE_PROFILES_PATH` env → `SamanTools.config_local` → `~/.config/saman/nuke_profiles.json`**. Current chain (`injector.obtener_ruta_store`, `injector.py:127-143`; config_local contract `injector.py:92-124`) already covers the last three links.
- **Consequence (documented, not a bug):** a project store ALWAYS wins, so `NUKE_PROFILES_PATH`/`config_local` become *fallbacks for projects without `.saman/`* (e.g. untitled scripts, files on Desktop, headless where the root is unknown) — they can no longer override a project that has its own store. This inverts the current "env var is the top override" intent (spec `load-injector` "Profile store resolution", `load-injector/spec.md:83-93`). If the studio later needs a global override it must be a new concept.
- **PRODUCT DECISION (flag):** keep the home fallback at all, or drop it now that the chain starts at the project? Keeping it preserves the "no `.saman` → onboard to home" flow and the `config_local`/env escape hatches; dropping it removes the stale old-schema home store. Recommend **keep** (chain falls back cleanly; the A2 legacy-shape detection handles the stale file).

### B6. `.saman/` auto-creation

- **Decision (technical, decided): create `.saman/` lazily on FIRST WRITE, never on read.** Reading a missing store already returns `{}` without error (`leer_perfiles`, `rutas_engine.py:93-94`); auto-creating on read would sprinkle empty `.saman/` folders into every opened location (e.g. Desktop). `_escribir_atomico` (`rutas_engine.py:121-145`) currently `mkstemp`s in `dirname(path)` and would fail if the folder is absent — write paths (`guardar_perfiles`, `asegurar_perfil` → `_escribir_perfiles`, `rutas_engine.py:211-221`) need `os.makedirs(dirname, exist_ok=True)` under the lock.
- The user's "debería crearse para cada proyecto" is satisfied: onboarding/change-base/selección writes are exactly the moments a project gets its store.
- Hygiene: `.saman/` lives in production project folders (outside this repo), but the change docs MUST state "never commit `nuke_profiles.json` with real paths" (public-repo rule, `openspec/config.yaml` proposal rules).

---

## C. Path Manager selector

### C7. Helper functions missing (`ui/path_manager.py`)

- **List profiles:** none exists. Add pure `listar_perfiles(ruta_store)` → `sorted(leer_perfiles(ruta_store).keys())` (usernames), `[]` on missing/corrupt store (tolerant, no raise — mirrors `detectar_desconocido`, `path_manager.py:134-147`).
- **Select/apply:** add pure `preparar_seleccion_perfil(usuario, ruta_store, so, ruta_plato="")` returning `{"perfil", "env", "unidad"}` — the same data contract as `preparar_cambio_base` (`path_manager.py:153-190`): read store → `perfiles.get(usuario)` → env via `injector.armar_estado_env` (`injector.py:66-86`) → `entorno.estado_unidad` on the current-SO root. Missing user → `ValueError` (the combo lists only existing users; only a stale-store race can hit it). NO onboarding on selection (selection is not creation).
- Existing functions simplify: `_emparejar_con_fuente` (`path_manager.py:49-79`) collapses to a user lookup (source types `exact`/`default`/`foreign-host` disappear); `preparar_cambio_base` writes become `perfiles[user][espacio][so] = base` (single shape); `preparar_onboarding` (`path_manager.py:196-215`) keeps its lock-safe contract but with the new shape. The "active profile" concept changes identity: active = **selected user**, not ambient user+hostname (`_identidad_ambiental`, `path_manager_panel.py:162-182`, only pre-selects).

### C8. Widget changes (`ui/path_manager_panel.py`)

- Add a `QComboBox` in `_construir_ui` (`path_manager_panel.py:70-107`).
- **Refresh (user-decided, minimal): re-read the store on dialog open.** `abrir_dialogo` (`path_manager_panel.py:185-211`) already re-reads state per open via `estado_panel`; populate the combo from the new `listar_perfiles` there. No timer, no project-change hook.
- **Micro-decision (flag): apply env immediately on combo change vs a confirm button.** The user's model says "seleccionar un perfil aplica sus rutas" → **recommend immediate apply** on selection (via `_aplicar_resultado`, `path_manager_panel.py:114-129`); tradeoff: an accidental switch changes `PROJECT_ROOT` mid-session (mitigation: keep "Cambiar base"/"Onboarding" for fine edits; the label shows the active user). Empty store → combo empty + onboarding form (existing flow).
- Default selection: ambient username if present in the store, else current active profile (first listed).

### C9. Interaction with the injector

- **Yes, identical to today:** selection env travels `preparar_seleccion_perfil` (pure) → widget calls `injector.cachear_env(env)` + `injector.aplicar_entorno(env)` (`path_manager_panel.py:114-129`). The module-level `_env_cache`/`_env_inyectado` (`injector.py:49-50`) makes `addOnScriptSave` re-assert the selected profile's env (`menu.py:160-168`) with no disk/lock. No injector logic change beyond `obtener_ruta_store` (B4-B6). Decided.

---

## D. MAIN specs to modify

| Spec | Type | Scope of change |
|---|---|---|
| `core-rutas-engine` | **MODIFIED** | "JSON profile store" (schema A1, legacy detection A2), "Profile resolution by user/hostname" → by user (ladder removed), "Tri-platform mapping" → per-space × per-platform, "Unknown-user onboarding" (new shape, `.saman/` write), "Context API"/"Environment variables exposure" (env from space roots; `PROJECT_ROOT` semantics A3), store-write `os.makedirs` (B6) |
| `load-injector` | **MODIFIED** | "Profile store resolution" (chain: project root first, B4-B5), "Pure environment assembly" (space-root env source) |
| `panel-path-manager-helper` | **MODIFIED + ADDED** | MODIFIED: matching/change-base/onboarding adapt to user-only model; ADDED: profile listing + selection requirements (C7) |
| `panel-path-manager-widget` | **MODIFIED + ADDED** | MODIFIED: existing flows bound to selection; ADDED: combo + refresh-on-open requirement (C8) |
| `panel-path-manager-menu` | **NOT MODIFIED** | registration/shortcut/PySide guards (`panel-path-manager-menu/spec.md`) are untouched — no delta needed (or an explicit "no change" note) |
| `core-entorno` | **ADDED (candidate)** | if `raiz_proyecto_desde_ruta` lands in `core.entorno` (B4). `reconstruir_rutas` requirement untouched |

Not specs but co-affected: `docs/ARQUITECTURA-V2.md:66-68` (store-chain description) must be updated to the new order.

---

## Decision summary (for proposal)

**Decided (technical evidence):**
- D2: breaking schema + regeneration; legacy-shape detection → re-onboard. (Sub-choice: silent vs warn — flagged.)
- D3: keep `reconstruir_rutas` as fallback + V1 contract; env primary source = profile space roots.
- D4: structural cut at `TO_VFX|COMP|FROM_VFX` as primary root derivation; `proyecto_desde_ruta`+base as secondary.
- D6: `.saman/` created lazily on first write, never on read.
- D9: selection applies env through the existing `cachear_env` + `aplicar_entorno` path.
- D8: combo refreshed on dialog open only.

**Flagged for user/product judgment:**
- D1: remove `hostname` from signatures (recommended) vs keep as ignored compat parameter.
- D2: silent regeneration (recommended) vs warn on legacy store.
- B5: keep home fallback link (recommended) vs drop it.
- C8: apply env on combo change (recommended) vs confirm button.
- B4: `PROJECT_ROOT` semantics when space roots share no parent (recommended: space-local root truncated to project segment).

## Risks

- R1 **Test churn:** the hostname ladder is fixture-hardwired in ~20+ tests (`test_rutas_engine.py:88-499`, `test_path_manager.py:86-231`, `test_path_manager_panel.py:132-233`); schema change rewrites them. Budget for it in tasks/design.
- R2 **Dead-mount hang:** probing `{root}/.saman/` on an unmounted share can hang Nuke's load callback; must reuse timed/cached checks (B4).
- R3 **Env staleness:** `_env_cache` keeps the previous profile's env if selection apply fails midway (mitigate: apply is idempotent, widget already guards `ValueError`, `path_manager_panel.py:141-158`).
- R4 **Silent behavior change:** project store now always wins over `NUKE_PROFILES_PATH` (B5) and hostname-foreign fallback disappears (A1) — both intentional but user-visible; needs a release note in the change.
- R5 **Public-repo hygiene:** any `.saman/` sample/template added for documentation must stay fictitious (config.yaml proposal rule).
- R6 **`PROJECT_ROOT` ambiguity:** with independent per-space roots there is no single base per profile; wrong truncation would mis-set `PROJECT_ROOT` for `[getenv PROJECT_ROOT]` TCL paths (A3/B4) — the fallback chain for missing space roots must be specified in design.

## Ready for Proposal

Yes. The orchestrator should tell the user: exploration confirms the current D1 schema, the ladder, the store chain and the Path Manager are all coupled to the user+hostname model; the change is breaking-but-regenerative (V2 pre-release), touches 4 MODIFIED specs (+1 ADDED candidate in core-entorno), and needs 5 explicit product decisions before sdd-spec (hostname removal, silent-vs-warn regeneration, home-fallback retention, apply-on-select UX, PROJECT_ROOT semantics).