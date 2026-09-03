# Design: load-contract — V2 visibility layer (bootstrap, shim, injector, menu)

## Technical Approach

Deliver the four new layers that make the pure core visible to Nuke and keep the V1 comp contract alive: a self-contained artist bootstrap (`bootstrap/menu.py`, V1 copy with V2 probes/marker), a lazy-import compat shim (`SamanTools/rutas.py`, delegation only), a pure/thin load injector (`SamanTools/ui/injector.py`), and a minimal exec target (`SamanTools/ui/menu.py`). `SamanTools/core/` is NOT touched. Env contract is data-driven (`core.rutas_engine.variables_entorno`); the injector applies it at `addOnScriptLoad` so TCL `[getenv PROJECT_ROOT]` resolves, and re-asserts the cached dict at `addOnScriptSave` (memory only). A single precedence chain — render-farm env → manual script override → profile → fictitious onboarding — governs both injector and shim so the knobChanged vs injector double-sourcing is idempotent.

## Architecture Decisions (ADR)

### ADR-1: Module name — `injector.py` (not `loader.py`)
**Choice**: `SamanTools/ui/injector.py`. **Alternatives**: `loader.py` — rejected: "loader" is overloaded in V1 (`cargar_scripts_proyecto`, menu-loading) and suggests script loading, not env injection; the engine's own contract names the future consumer the injection layer. **Rationale**: the module's dominant, unique contract is environment injection (`os.environ` + `__main__`) at script load; spec title `load-injector` and exploration "TCL environment injector" agree. Kept as the single load-layer module.

### ADR-2: `addOnScriptSave` — memory re-assert ONLY
**Choice**: save hook calls `aplicar_entorno(_env_cache)` from the in-memory cache; no store read, no lock, no engine call, no `limpiar.sanitizar_archivo`. **Alternatives**: (a) also run `limpiar.sanitizar_archivo` on save — rejected: it is disk I/O (violates the spec's no-disk-on-save latency guard), rewrites the file under Nuke's own save, and V1 precedent (`registro.py:53-78`) is a manual menu action, not a callback; it becomes a separate opt-in hook in a future change. (b) no-op hook — rejected: re-assert keeps env consistent if a node knobChanged overwrote vars mid-session. **Rationale**: Nuke serializes `[getenv PROJECT_ROOT]` tokens at save time only if the var is set — re-asserting is the minimal guarantee, pure memory, idempotent.

### ADR-3: knobChanged ↔ precedence (HIGH) — same chain, injector cache wins
**Choice**: `actualizar()` (shim) follows the SAME precedence chain as the injector and never clobbers an env the injector already wrote this session. Chain: (1) `PROJECT_ROOT` already in `os.environ` **before the loader wrote anything** → no env write (render farm); (2) manual script override → use it; (3) profile-driven (injector) — else knob-derived (shim). **Mechanism**: injector keeps module-global `_env_cache` and sets `_env_inyectado=True` after its own write. Shim `actualizar()` computes the knob-derived env (`_env_desde_knobs(n)`) and, if `_env_inyectado` is set, SKIPS the env write (still syncs node knobs: usuario, visibilidad, estado). If knobChanged fires before `addOnScriptLoad`, the injector later overrides with the profile (it does not consult the shim's writes). **Result**: final state is profile-driven whenever the injector ran after; knob-driven only if it never ran; render-farm wins in all cases. Idempotent, order-independent.

### ADR-4: Headless detection — minimal: `PROJECT_ROOT` pre-present
**Choice**: headless/upstream = `"PROJECT_ROOT" in os.environ` at `addOnScriptLoad` time, BEFORE any loader write. If present → no-op for env writes, no profile resolution, no onboarding. **Alternatives**: `nuke.env.get("nukeVersion")` — always present, useless; batch-mode flags — render farms also launch GUI Nuke with `-t`; `NUKE_PROFILES_PATH` as signal — rejected: studio setup legitimately sets it on artist machines (false positives → red nodes). **Rationale**: the orchestrator's injection IS `PROJECT_ROOT`; spec scenario "render farm env wins" is satisfied by this single check. The spec's "(or the store path)" parenthetical is narrowed deliberately — documented, not re-opened.

### ADR-5: Manual override detection — root `project_directory` knob
**Choice**: pure helper `_override_proyecto_desde_root(root) -> str | None` in the injector: declared iff the root exposes knob `project_directory` AND its `.value()` is a non-empty string; the override base = value normalized to forward slashes. Empty/`None`/missing knob = not declared. Lives in ui (engine stays pure); injectable with a fake root for tests. **Rationale**: Nuke's root exposes per-script project directory this way; string-level, no ambient assumptions — matches the engine's injectable pattern. **Integration risk**: exact knob metadata varies across Nuke versions; validate on real Nuke 13/14/15 during apply (see Risks).

### ADR-6: Store resolution — `obtener_ruta_store()` chain
**Choice**: `os.environ["NUKE_PROFILES_PATH"]` → `SamanTools.config_local` scoped config (module attr `NUKE_PROFILES_PATH`, else sibling `SamanTools/config_local.json` read via the same loader; both gitignored — verified `.gitignore:22` matches at any depth) → `~/.config/saman/nuke_profiles.json` (final default; onboarding persists fictitious roots there). Never a bare root-level `config_local.py` (repo root enters `sys.path` inside Nuke — generic-name collision). The studio installer (future change) writes the scoped module with the shared per-project path; until then the shared leg yields nothing and home is used. Tolerant read: `ImportError`/missing → next leg.

### ADR-7: `ui/menu.py` structure — thin, idempotent via injector flag
**Choice**: imports `nuke` at top (ui layer, 0% coverage accepted), imports `injector` normally and the shim tolerantly (`try/except ImportError`). `registrar_callbacks()` is made idempotent with `_callbacks_registrados` in the INJECTOR module (persists across bootstrap re-execs, since each exec gets a fresh namespace but `sys.modules` caches the package) — re-exec no-ops. Menu: `nuke.menu("Nuke").findItem("SamanTools")` else `addMenu("SamanTools")`; adds a "Configuración" submenu with minimal V2 items; the bootstrap's own maintenance buttons attach to the same submenu later (V1 pattern `bootstrap/menu.py:289-296`). No panels, no PySide.

### ADR-8: Shim signature matrix — see Interfaces/Contracts
Delegation matrix below; string annotations (`"nuke.Node"`) keep import headless.

### ADR-9: Testability without a stub
`test_injector.py`: `armar_estado_env` fixtures (profile dict/so/plate; untitled + outside-roots base gap; determinism; os.environ snapshot purity), `obtener_ruta_store` with `monkeypatch` (env + `HOME` + fake `SamanTools.config_local`), `_override_proyecto_desde_root` with a root fake. `test_shim.py`: headless import, constants equal V1 literals, `es_nodo_rutas`/`actualizar` with a node fake scoped to the test file (NOT conftest), stubs no-op without nuke. `test_bootstrap.py`: `nuke` module fake via `sys.modules` (test-local), `_ejecutar_git`/`subprocess` monkeypatched; marker test asserts the bootstrap SOURCE contains "SamanTools V2 bootstrap" and NOT "bootstrap de artista"; probes (`rutas_engine.py`, exec `ui/menu.py`) asserted by source string. `ui/menu.py`: 0% by design (V1 precedent ARQUITECTURA §6).

### ADR-10: Implementation order (suite always green)
H1 pure injector + `obtener_ruta_store` + tests → H2 shim + tests → H3 bootstrap + tests → H4 `ui/menu.py` (exec target lands after bootstrap so probe verification is real) → H5 docs (coexistence note, config_local sample) + full suite + `py_compile` gate + verify. Pure-first keeps the suite green at every commit (config.yaml tasks rule); H4 before H3 would make the bootstrap's exec-target probe untestable in-repo.

## Data Flow

```
Nuke startup → ~/.nuke/menu.py (V2 bootstrap)
  ├─ _auto_actualizar_bootstrap (md5 sync from <repo>/bootstrap/menu.py)
  ├─ _cargar_menu_real → exec <repo>/SamanTools/ui/menu.py
  │     └─ injector.registrar_callbacks()   [idempotent]
  │           ├─ addOnScriptLoad: PROJECT_ROOT pre-set?  → no-op [render farm]
  │           │       └─ override? (root project_directory) → apply override
  │           │               └─ perfil ← resolver_perfil(usuario, host, obtener_ruta_store())
  │           │                     └─ armar_estado_env(perfil, so, nuke.root().name(), base)  [PURE]
  │           │                           └─ aplicar_entorno(env) → os.environ + __main__; cache env
  │           └─ addOnScriptSave: aplicar_entorno(_env_cache)   [memory only]
  └─ _agregar_boton_menu (Actualizar/Desinstalar; only if checkout)

Legacy comp open → Rutas nodo knobChanged → rutas.actualizar(nuke.thisNode())
  └─ _env_desde_knobs(n) → _env_inyectado? skip write : aplicar_entorno (same chain, idempotent)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `SamanTools/ui/injector.py` | Create | Pure `armar_estado_env`; thin `aplicar_entorno`/`registrar_callbacks`; `obtener_ruta_store`; override helper; in-memory env cache |
| `SamanTools/rutas.py` | Create | Shim: re-exported constants, thin facades, compat-only stubs; lazy `import nuke` |
| `SamanTools/ui/menu.py` | Create | Bootstrap exec target: idempotent callbacks + minimal SamanTools menu |
| `bootstrap/menu.py` | Create | V1 copy (11 rules), V2 marker/probes/target/sync source, distinct uninstall marker |
| `tests/test_injector.py` | Create | Pure assembly, store chain, override helper |
| `tests/test_shim.py` | Create | Headless import, constants, node fakes (test-local), stubs |
| `tests/test_bootstrap.py` | Create | 11 rules via monkeypatched git/subprocess + nuke fake (test-local), marker string |
| `SamanTools/config_local.py` | Create (gitignored sample) | Studio override sample for `NUKE_PROFILES_PATH`; never committed |
| `docs/` | Create | V1/V2 coexistence + replace-with-consent note |

## Interfaces / Contracts

```python
# SamanTools/ui/injector.py
def armar_estado_env(perfil: dict, so: str, ruta_plato: str, base: str | None = None) -> dict: ...
def aplicar_entorno(env: dict) -> None: ...            # os.environ.update + __main__.__dict__.update; idempotent
def registrar_callbacks() -> None: ...                 # idempotent; addOnScriptLoad/addOnScriptSave
def obtener_ruta_store() -> str: ...                   # env → SamanTools.config_local → ~/.config/saman/nuke_profiles.json
def _override_proyecto_desde_root(root) -> str | None: ...  # PURE, fake-root testable
# module globals: _env_cache: dict | None, _env_inyectado: bool, _callbacks_registrados: bool
```

Shim delegation matrix (public surface; annotations string-form; `nuke` lazy in bodies):

| Function | Class | Delegation |
|---|---|---|
| `SUFIJOS`, `KNOBS_RUTAS_BASE`, `KNOBS_VERSION_ACTUAL`, `_KNOBS_A_MIGRAR`, `_texto_estado`, `_reescribir_proyecto_en_rutas` | re-export | identical V1 values (serialized in .nk); `_texto_estado`/`_reescribir_*` thin pure copies, core has no equivalent |
| `actualizar(n: "nuke.Node" = None) -> bool` | facade | `_env_desde_knobs(n)` → injector precedence guard → `injector.aplicar_entorno`; Read capture/re-eval facade copies |
| `aplicar_proyecto(n=None) -> bool` | facade | knob syncs (`core.entorno.{detectar_so,usuario_activo,primera_ruta_disponible}`, `core.nombres.parsear_plato`) + env apply via injector |
| `refrescar_fuentes(n=None, forzar=False) -> int` | facade | `_capturar_reads_dinamicos`/`_re_evaluar_y_recargar` facade copies (nuke-bound) |
| `es_nodo_rutas(n) -> bool` | facade (pure-ish) | knob-set inspection only (UsuarioActivo + any TO_VFX_SERVER_*) |
| `es_version_actual(n) -> bool` | facade (pure-ish) | `KNOBS_VERSION_ACTUAL.issubset(n.knobs())` |
| `encontrar_nodos_rutas() -> list` | facade | `nuke.allNodes()` + `es_nodo_rutas` |
| `refrescar_estado(n=None) -> bool` | facade | `core.entorno` estado + knob writes, re-entry guard `_refrescando` |
| `crear_o_reutilizar`, `cambiar_proyecto`, `avisar_duplicados`, `refrescar_fuentes_boton`, `ruta_nk_por_defecto` | stub | import-safe no-op → `None`; docstring marks compat-only, never revived |

`bootstrap/menu.py`: 11 V1 rules verbatim; `_checkout_completo` probes `SamanTools/core/rutas_engine.py`; `_cargar_menu_real` execs `<TOOLS_DIR>/SamanTools/ui/menu.py`; auto-sync from `<TOOLS_DIR>/bootstrap/menu.py`; uninstall marker "SamanTools V2 bootstrap" (must NOT contain "bootstrap de artista").

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit | `armar_estado_env` incl. base/so gap, determinism, purity | fixtures, no nuke |
| Unit | `obtener_ruta_store` chain, override helper | monkeypatch env/home + fakes |
| Unit | Shim headless import, constants, facades, stubs | node fakes test-local; string annotations |
| Unit | Bootstrap 11 rules, probes, markers | monkeypatched git/subprocess; nuke fake in `sys.modules` (test-local) |
| Integration | Suite green + core purity guard intact | `python3 -m pytest` |
| N/A | `ui/menu.py` behavior | 0% coverage accepted (ARQUITECTURA §6) |

## Threat Matrix

| Boundary | Applicability | Design response |
|---|---|---|
| Git repository selection | **Applicable** — bootstrap runs `git -C TOOLS_DIR ...` with fixed argv (fetch/pull/rev-parse/clone/reset), no `shell=True`, no user-controlled command names | Authority is always `TOOLS_DIR`; RED test: `_ejecutar_git` composes fixed argv; clone target is a private tmp dir under `~/.nuke`; path args never derive from .nk/user input |
| Commit state | **Applicable** — `pull --ff-only`, `reset --hard origin/<BRANCH>`, rev-parse HEAD | Fast-forward only; failed pull reported, never force-resolved; reset only for incomplete checkout; RED test: non-ff pull → failure message, no reset |
| Push state | N/A — no push/refspec logic in bootstrap |
| PR commands | N/A — no PR automation |
| Documentation-like paths / executable classification | **Applicable** — bootstrap copies/replaces `~/.nuke/menu.py` (md5 auto-sync) and uninstalls it only when it carries the V2 marker | RED test: marker string present / V1 marker absent; uninstall leaves foreign menu.py untouched |
| Shell/subprocess | **Applicable** — `subprocess.run` fixed-argv git (captured, timeout 60-180 s) | RED test: e.g. clone failure removes tmp and leaves target absent |

## Migration / Rollout

No data migration (new store created on first onboarding). Rollout: V2 installer documented as REPLACING V1 with explicit consent (delete `~/.nuke/SamanTools` + old menu.py); coexistence is temporary and only documented in `docs/`. Rollback: all files additive → `git revert`; V1 `~/.nuke/menu.py` untouched.

## Open Questions / Integration Risks

- [ ] Validate `project_directory` knob metadata (name/value semantics) on real Nuke 13/14/15 during apply; adjust `_override_proyecto_desde_root` if the knob auto-derives from `name()` when empty (must then require explicit non-default value).
- [ ] Confirm actual knobChanged-vs-addOnScriptLoad ordering in a real V1 comp inside Nuke; contract is order-independent by design, but log empirically.
- [ ] `PYTHON_*` rescan of `{PYTHON_COMP}/Scripts` (V1 `proyecto.py:90`) has no V2 home — deferred to the future vfxflow change; legacy `[python ...]` Read scripts keep working because `PYTHON_*` land in `__main__`.
- [ ] `_texto_estado`/`_reescribir_proyecto_en_rutas` stay as thin shim copies (candidate to promote into `core.nombres` later — separate change, optional).