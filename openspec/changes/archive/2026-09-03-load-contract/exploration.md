# Exploration: load-contract — V2 visibility layer (injector, shim, bootstrap)

> Change: `load-contract` · Repo: `saman-workflow-v2` (V2 of `saman-nuke-tools`, public) · Date: 2026-09-02
> Source of truth read: V1 repo `saman-nuke-tools` (bootstrap, menu, rutas, registro, ARQUITECTURA) + V2 core engine + archived design `2026-09-02-core-rutas-engine`.

## Executive Summary

V2 currently ships only the pure core (`SamanTools/core/*`, stdlib-only, guard-enforced) with no Nuke
visibility. This change adds the three layers that make the engine visible in Nuke: a new artist
bootstrap (`bootstrap/menu.py`), a compatibility shim (`SamanTools/rutas.py`), and a TCL environment
injector (profile → `os.environ["PROJECT_ROOT"]` + `__main__`). Exploration findings:

- **A (bootstrap):** the V1 bootstrap contract is stable and MUST be preserved (fetch-only startup,
  consent-based update, silence without checkout, hash auto-sync, tmp+rename clone, reset --hard repair).
  Only the structural probes change: `_checkout_completo` probes `SamanTools/registro.py` (V1) and
  `_cargar_menu_real` execs `TOOLS_DIR/menu.py`; in V2 propose marker `SamanTools/core/rutas_engine.py`
  and exec target `SamanTools/ui/menu.py` (created by this change). V1/V2 bootstrap coexistence on
  `~/.nuke/menu.py` is a real risk (auto-sync battle + uninstaller false-positive) → document + migrate explicitly.
- **B (shim):** full inventory below. Re-export pure constants/helpers; implement thin nuke facades for
  the V1 comp contract (`actualizar(nuke.thisNode())`); stub node-lifecycle functions that V2 never calls.
  Shim MUST lazy-import `nuke` (V2 conftest has no stub; top-level import would break tests and headless envs).
- **C (store location):** open question from design D-Open (design.md:333). No decision taken here — three
  viable options with tradeoffs (env var / project-shared LucidLink / per-machine `~/.config/saman`).
- **D (testability):** split pure `armar_estado_env(perfil, so, ruta_plato) -> dict` (tested, no nuke) from a
  thin callback wrapper (0% coverage acceptable, V1 precedent ARQUITECTURA.md:103-106). V1 has **no**
  `addOnScriptLoad`/`addOnScriptSave` precedent anywhere (grep across V1 found none) — the callback pattern is new.

---

## Evidence Base (file:line)

| Evidence | Location |
|---|---|
| V1 bootstrap full contract | `saman-nuke-tools/bootstrap/menu.py` (433 lines) |
| V1 root loader | `saman-nuke-tools/menu.py` (46 lines) |
| V1 rutas module to shim | `saman-nuke-tools/SamanTools/rutas.py` (814 lines) |
| V1 menu/registro + `_inyectar_frame_manager` | `saman-nuke-tools/SamanTools/registro.py` (393 lines) |
| Update contract §3, instances of historical errors §4, 0% coverage rule §6, operative rules §8 | `saman-nuke-tools/docs/ARQUITECTURA.md` |
| Installer flows that copy bootstrap to `~/.nuke/menu.py` | `setup_artista.sh:52-63`, `instalar_script_editor.py:53-89` |
| V1 global route config precedent (per-user JSON) | `saman-nuke-tools/SamanTools/rutas_global.py:23-25` (`~/.config/saman/rutas_global.json`) |
| V1 nuke stub (the pattern V2 deliberately does NOT ship) | `saman-nuke-tools/tests/conftest.py` (221 lines) |
| V2 engine public API | `saman-workflow-v2/SamanTools/core/rutas_engine.py` |
| V2 entorno/nombres available for delegation | `saman-workflow-v2/SamanTools/core/entorno.py`, `core/nombres.py` |
| V2 conftest: minimal, **no stub** | `saman-workflow-v2/tests/conftest.py` (`# A propósito NO se define ningún stub de nuke`) |
| V2 planned structure (ui/ layer, vfxflow, bootstrap as load contract) | `saman-workflow-v2/openspec/config.yaml:12-22` |
| Engine spec "later UI/load layer applies env at addOnScriptLoad" | `openspec/specs/core-rutas-engine/spec.md:123` |
| Design open questions: profile store location + `carpeta_salida` | `openspec/changes/archive/2026-09-02-core-rutas-engine/design.md:328-334` |
| V2 gitignore: `config_local.py` ignored, no `nuke_profiles.json` rule | `saman-workflow-v2/.gitignore:21-22` |
| Demo gap: loader must assemble base/so explicitly (`get_context` returns `base=None` without prefix match) | Engram #2286 (2026-09-02) |

---

## A. V2 Bootstrap (new)

### 1. V1 contract — what V2 MUST keep (verified against `bootstrap/menu.py` + ARQUITECTURA §3)

| # | Contract rule | Evidence |
|---|---|---|
| 1 | Startup does **fetch-only**, never modifies the tree | `_estado_update` `fetch origin BRANCH` then compare hashes (`bootstrap/menu.py:84-95`); ARQUITECTURA §3.1 |
| 2 | Update only **with consent** (alert max 1×/6 h, `LOCK_FILE`) | `_alerta_automatica` 192-220; lock 37-38; ARQUITECTURA §3.2/§3.4; error #5 §4.5 |
| 3 | Apply via `git pull --ff-only` only | `_aplicar_update` 123-143 |
| 4 | **Silence without checkout** — never clones at startup, never errors | `_cargar_menu_real` 369-370; error #8 §4.8; ARQUITECTURA §3 state table |
| 5 | Clone via **tmp + rename** (never partial checkout) | `_clonar_si_falta` 301-331; error #4 §4.4 |
| 6 | Incomplete checkout → silent `reset --hard origin/<BRANCH>` repair | `_reparar_checkout` 346-357; ARQUITECTURA §3 |
| 7 | Bootstrap **auto-syncs by content hash** each startup | `_auto_actualizar_bootstrap` 394-420; error #7 §4.7 |
| 8 | Maintenance menu only when checkout exists (uninstall leaves menu clean) | `_agregar_boton_menu` 278-286 |
| 9 | Update button reinstalls when checkout missing | `_actualizar_ahora` 146-172 |
| 10 | Bootstrap is self-contained — never imports repo code (works even if repo broken) | docstring 18-20; ARQUITECTURA §2 table |
| 11 | Uninstall deletes definitively (no backup accumulation) | `_desinstalar_ahora` 223-275; error #6 §4.6 |

### 2. Structural probes that change in V2

- `_checkout_completo` (334-343) probes `TOOLS_DIR/SamanTools/registro.py` → **V1-only**. V2 has no
  `registro.py`; exists today: `SamanTools/{__init__,core/{__init__,entorno,nombres,limpiar,rutas_engine}}.py`.
- `_version_instalada` (98-120) reads `SamanTools/__init__.py` `__version__` → unchanged, `__version__ = "2.0.0"` exists (V2 `__init__.py:5`).
- `_cargar_menu_real` (360-391) execs `TOOLS_DIR/menu.py` → **V1-only**; V2 has no root `menu.py` yet.
- `_auto_actualizar_bootstrap` (403) syncs from `TOOLS_DIR/bootstrap/menu.py` → V2 has no `bootstrap/` yet; this change creates it.

### 3. Proposal: marker + target for a functional V2 bootstrap

- **Marker (`_checkout_completo` probe)**: `SamanTools/core/rutas_engine.py` — the last engine slice (G7) and the
  strongest signal that a checkout is a complete V2 (a partial clone/pull can still drop `__init__.py`/`core/`).
  Weaker alternatives rejected: `SamanTools/__init__.py` (exists since the first scaffold commit) and
  `SamanTools/core/__init__.py` (package marker only).
- **Target (`_cargar_menu_real` exec)**: `SamanTools/ui/menu.py` — V2's equivalent of the V1
  `registro.instalar()` entry: registers the injector callbacks, builds the Nuke menu, imports the shim.
  The repo-level config already reserves `SamanTools/ui/` as "sole PySide/Nuke layer"
  (config.yaml:13-15) and casts `bootstrap/menu.py` as the load contract (config.yaml:17-18), keeping the
  bootstrap maintenance-only (rule 10).
- **Minimal functional floor for this change**: `ui/menu.py` may be thin (callbacks + menu "SamanTools"
  with maintenance items inherited from the bootstrap); the injector itself can live in
  `SamanTools/ui/injector.py` (or `loader.py` — name to confirm in design) and be imported by `ui/menu.py`.

### 4. V1/V2 coexistence risk (separate repos, same `~/.nuke`)

The V1 installer copies its bootstrap to `~/.nuke/menu.py` (setup_artista.sh:63, instalar_script_editor.py:78-80)
and the V1 bootstrap **rewrites that file on every startup** from `~/.nuke/SamanTools/bootstrap/menu.py`
(auto-sync by md5, 394-420). If V2 installs its own bootstrap to the same path:

1. **Auto-sync war** — each boot, whichever bootstrap runs last copies its own version over the other (V1 syncs
   from its checkout, V2 from its own) → menu.py content flaps between versions.
2. **Uninstaller false positive** — V1 `_desinstalar_ahora` deletes `~/.nuke/menu.py` if it contains
   `"SamanTools"` and `"bootstrap de artista"` (256-270); a V2 bootstrap matching that marker would be deleted
   as "V1's own".
3. **Checkout collision** — using the same `TOOLS_DIR` (`~/.nuke/SamanTools`) would clobber the V1 install;
   separate checkouts require a different dir (e.g. `~/.nuke/SamanToolsV2`).

Mitigation for the change: V2 bootstrap keeps a distinct marker string ("SamanTools V2 bootstrap") and the V2
installer must be documented as **replacing** V1 (delete `~/.nuke/SamanTools` + old menu.py with explicit
consent), not coexisting. Coexistence is temporary and out of scope for this change — only documented here.

---

## B. Shim `SamanTools/rutas.py` — inventory & delegation

V1 entry contract to keep alive (rutas.py docstring:4-6): comps' knobChanged executes
`from SamanTools import rutas; rutas.actualizar(nuke.thisNode())`. The shim must import cleanly and keep
that call working while delegating all logic to `SamanTools.core`.

### Constants (re-export as-is; V1 names must not change — knob values and knob names are serialized in .nk files)

| Constant | V1 line | Notes |
|---|---|---|
| `SUFIJOS` | 23 | `{"MacServer":"MAC","Windows":"WINDOWS","Artist":"ARTIST"}` — inverse mapping of `core.entorno.usuario_activo`/`sufijo_so` |
| `KNOBS_RUTAS_BASE` | 385-389 | the 9 server knobs |
| `KNOBS_VERSION_ACTUAL` | 524-534 | 7-knob frozenset, legacy node "current version" detection |
| `_KNOBS_A_MIGRAR` | 536-548 | 11 knobs for legacy node migration |

### Function classification

| V1 function (line) | Class | V2 disposition |
|---|---|---|
| `_texto_estado` (30) | pure | re-export (thin copy; no core equivalent) |
| `_aplicar_config` (208) | semi-pure: writes `__main__.PYTHON_*` (234-236) + rescans `proyecto.cargar_scripts_proyecto` (240) | **replaced** by injector: `variables_entorno(contexto)` returns the same dict as data (rutas_engine.py:473-497); the `__main__` write and `os.environ` write move to the loader. **Flag:** the `{PYTHON_COMP}/Scripts` rescan (proyecto.py:90) has no V2 equivalent yet — out of scope (future vfxflow change) |
| `_reescribir_proyecto_en_rutas` (245) | PURE (regex on dict) | re-export thin copy in shim; candidate to promote into `core.nombres` later |
| `_capturar_reads_dinamicos` (181) | nuke-bound (`nuke.allNodes("Read")`, `toScript`) | facade copy — V1-critical ordering (capture BEFORE env write, see `actualizar` 372-378) |
| `_re_evaluar_y_recargar` (193) | nuke-bound (node reload) | facade copy |
| `_sincronizar_entorno` (37) / `_sincronizar_plano` (66) / `_recomendar_usuario` (104) / `_aplicar_visibilidad` (135) | nuke-bound (knobs) | thin facades over `core.entorno.{detectar_so,usuario_activo,primera_ruta_disponible,estado_unidad}` + `core.nombres.parsear_plato` |
| `_aplicar_proyecto_inner` (270) | nuke-bound legacy adapter | facade: assemble `cfg` from legacy knobs → env contract via engine |
| `aplicar_proyecto` (319) / `actualizar` (348) | public, nuke-bound | **facade — critical compat path** (knobChanged entry) |
| `refrescar_fuentes` (331) | public, nuke-bound | facade |
| `es_nodo_rutas` (560) / `encontrar_nodos_rutas` (586) / `es_version_actual` (595) / `refrescar_estado` (458) | nuke-bound detection/knowledge | facade copies (pure-ish knob inspection; keep behavioral equivalent) |
| `ruta_nk_por_defecto` (551) / `_seleccionar` (610) / `_enfocar_nodo` (633) / `_reconstruir_nodo` (658) / `crear_o_reutilizar` (734) / `avisar_duplicados` (790) / `cambiar_proyecto` (414) / `refrescar_fuentes_boton` (443) | nuke-bound node lifecycle / UX | **stubs** — no V2 caller (no menu, no TAB, no `nodos/`); MUST exist so `from SamanTools import rutas` never breaks; body = import-safe no-op or minimal docstring + `pass`/`return None` |

### Shim testability without a conftest stub

V1 imports `nuke` at module top (rutas.py:18) and relied on the conftest stub (V1 tests/conftest.py). V2's
conftest is deliberately stub-free (`tests/conftest.py:4-6`). **Proposal: the shim lazy-imports `nuke`
inside nuke-bound function bodies** (try/except at call time, mirroring V1's own inner
`from SamanTools import entorno` tolerance, rutas.py:46). Consequences:

- `import SamanTools.rutas` succeeds headless → testable: "imports clean + pure helpers delegate" with zero stub.
- Nuke-bound paths (facades/stubs) get 0% coverage — acceptable per V1 precedent (ARQUITECTURA §6:
  "registro.py/frame_manager.py 0% es aceptable — UI Nuke sin lógica pura testeable").
- Optional (recommended): a **test-local** minimal `nuke`/node fake inside the shim test module (NOT conftest)
  to unit-test `actualizar()` knobChanged compat — precedent: V1 `NodoFake`/`KnobFake` (conftest.py:46-98),
  but V2 keeps conftest pristine and scopes the fake to the test file.

---

## C. `nuke_profiles.json` location in production (open question — decision required in design)

Repo is public: the store MUST live outside the repo; no real paths in code (spec.md:5, config.yaml:19-20).
Engine API takes `path` as parameter everywhere (`leer_perfiles/guardar_perfiles/resolver_perfil/asegurar_perfil`,
rutas_engine.py:102-337) — location is fully injectable by the loader's `obtener_ruta_store()` helper.

Relevant precedents:
- V1 per-user home config: `~/.config/saman/rutas_global.json` (rutas_global.py:23-25).
- V1 per-project config at base root: `{base}/.saman/studio_config.json` (ARQUITECTURA §8.7).
- User vision: `[Lucid]/Proyecto_X/config/nuke_profiles.json` (per-project, shared on LucidLink).
- Engine design hints at a **shared, multi-process** store: hostname-keyed schema (D2), cross-process exclusive
  lock with merge (D6/D3, spec "concurrent onboarding does not lose profiles" incl. render nodes), user-only AND
  hostname-only fallbacks (only meaningful when the store aggregates several machines per user).

| Option | Default location | Global vs per-project | Pros | Cons |
|---|---|---|---|---|
| **O1 — env var + per-user home fallback** | `NUKE_PROFILES_PATH` env var; fallback `~/.config/saman/nuke_profiles.json` | per-machine (user), override possible (→ shared if env points to LucidLink) | Public-repo safe; simplest; V1 precedent (rutas_global path); per-machine onboarding is private; no mount dependency to read your own config | Onboarding per machine (N workers → N onboardings, fictitious roots on render nodes); hostname-only fallback meaningless on single-user machines; studio must set env on every machine |
| **O2 — project-shared (user vision)** | `[Lucid]/Proyecto_X/config/nuke_profiles.json` via env/config | per-project, shared by all artists + workers | Matches artist vision; one store per study year/project; hostname precedence shines (user → any machine); render onboarding populates the same store; engine's lock+merge designed exactly for this | Requires the mount to resolve a profile (no mount → env not set → red nodes; needs fallback); multi-project setups duplicate stores; artists need write access to the shared file (Lock/Lucid perms) |
| **O3 — checkout-relative / repo-root file** | `<checkout>/nuke_profiles.json` | per-clone | trivial | **REJECTED**: public repo leaks real paths on push; git pull conflicts on dirty file; ARQUITECTURA §8.1 forbids |

Recommended resolution chain for the loader (to be confirmed in design): `NUKE_PROFILES_PATH` →
project-shared path supplied by the setup script (O2 philosophy) → per-user home fallback (O1) → default
fictitious onboarding (engine behavior, spec.md:133). Whether the default for a bare artist machine is
per-project (O2) or per-user (O1) is the actual decision — recommend O2 taken by the studio setup script,
O1 as engine fallback. `config_local.py` (gitignored, .gitignore:22) remains available for studio override,
consistent with ARQUITECTURA §8.7 (`RENDER_LOCAL_CONFIG` precedent) — it can hold the store path, not the store itself.
Also record the design.md open question: sibling `nuke_profiles.json.lock` persists by design (design.md:332-334).

---

## D. Testability of the injector (no nuke stub)

### 1. V1 callback precedent

**None.** grep for `addOnScriptLoad|addOnScriptSave|onScriptLoad` across V1 finds zero hits (only the V2
engine docstring mentions `addOnScriptLoad` as the future consumer, rutas_engine.py:52, 481). The callback
pattern is new — do not claim a copied V1 pattern. The only save-time behavior precedent is the
user-triggered `limpiar.sanitizar_archivo` menu command (registro.py:53-78), not a callback.

### 2. Proposed split (pure vs thin)

```python
# SamanTools/ui/injector.py (or loader.py — name for design)
def armar_estado_env(perfil, so, ruta_plato, base=None) -> dict:   # PURE, injected params, no nuke
    # base = base or core.rutas_engine.ruta_para_plataforma(perfil, so)
    # ctx  = core.rutas_engine.get_context(perfil, ruta_plato)
    # if not ctx["base"]: ctx = {**ctx, "base": base, "so": so}    # memory #2286 gap
    # return core.rutas_engine.variables_entorno(ctx)              # {"PROJECT_ROOT", PYTHON_*}
def aplicar_entorno(env: dict) -> None:      # THIN: os.environ.update(env) + __main__.__dict__.update(env)
def registrar_callbacks() -> None:           # THIN: nuke.addOnScriptLoad(...) / addOnScriptSave(...)
```

- `armar_estado_env` is fully testable without nuke (conftest unchanged): inject profile dict + `so` + plate
  path, assert `PROJECT_ROOT` + `PYTHON_*` keys. This covers the ONLY non-obvious logic (the
  base/so assembly gap: `get_context` returns `base=None/so=None` when the plate path is not under any root —
  e.g. untitled script — and `variables_entorno` returns `{}` for a context without base, rutas_engine.py:483-488;
  confirmed by demo memory #2286).
- `aplicar_entorno` + `registrar_callbacks` are 2-4-line wrappers → 0% coverage acceptable (ARQUITECTURA §6 rule).
- The shim `actualizar()` facade shares the same pure core (env contract) — its knob-reading side stays untested.

### 3. Callback semantics (decision inputs, not taken)

- **addOnScriptLoad**: resolve profile (loader reads ambient identity — allowed: the engine's
  injectable-identity guarantee is only for `core/`), detect SO (`core.entorno.detectar_so`), assemble
  context from `nuke.root().name()` plate path, apply env. Effect: TCL `[getenv PROJECT_ROOT]` in
  Read/Write nodes resolves; the engine spec explicitly marks this as the missing link (spec.md:123).
- **addOnScriptSave**: with the env var set at save time, Nuke serializes `[getenv PROJECT_ROOT]` tokens
  directly — so save needs **no rewrite** for relativization. Minimum viable: no-op hook registered for
  symmetry/future hygiene; alternative: re-assert env (idempotent). Whether save also re-runs a
  `limpiar`-style volatile-knob sanitize is a design decision (precedent exists only as manual menu action).
- Must be idempotent with the shim's `actualizar()`: a V1 comp opened in V2 triggers BOTH the injector
  (profile-driven) and knobChanged (knob-driven; rutas.py:4-6). Both end in the same `os.environ`/`__main__`
  contract; ordering/source-of-truth (profile wins vs knob wins) is a design decision — flagging it here as HIGH risk.

---

## Risks

| Severity | Risk | Evidence |
|---|---|---|
| HIGH | `~/.nuke/menu.py` auto-sync war + V1 uninstaller may delete V2 bootstrap during coexistence | bootstrap/menu.py:394-420, 256-270 |
| HIGH | Double sourcing of env on V1 comps in V2: injector (profile) vs knobChanged `actualizar` (legacy knobs) — must be idempotent, ordered | rutas.py:4-6, 348-378; injector spec.md:123 |
| MED | `get_context` may yield `base=None`/`so=None` (untitled / path outside roots) → `variables_entorno` returns `{}` → `PROJECT_ROOT` never set → red nodes | rutas_engine.py:447, 483-488; Engram #2286 |
| MED | Top-level `import nuke` in the shim breaks `from SamanTools import rutas` under pytest (no stub) and headless envs — lazy import required | V1 rutas.py:18 vs V2 tests/conftest.py:4-6 |
| LOW-MED | `_aplicar_config`'s `{PYTHON_COMP}/Scripts` rescan side effect has no V2 home; legacy `[python ...]` Read scripts keep working only if `PYTHON_*` are written to `__main__` | rutas.py:234-240; proyecto.py:90 |
| LOW | Shims/stubs keep the full V1 public surface — dead code with an import contract; must be documented as compat-only so it is not "revived" | 813-line V1 surface vs V2 needs |

## Ready for Proposal

Yes — the four ambiguities have evidence-backed proposals; two decisions must be surfaced to the user in
the proposal/design phase: (1) profile store location (C: recommend env-var → project-shared → per-user-home
chain; confirm shared-vs-per-machine), (2) addOnScriptSave semantics + knob-vs-profile precedence on legacy
comps (D). Everything else (marker, target, shim classification, testability split, bootstrap preservation
list) is ready to be written as proposal + spec.