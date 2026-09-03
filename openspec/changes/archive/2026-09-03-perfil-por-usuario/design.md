# Design: Perfil por usuario (perfil-por-usuario)

## Technical Approach

Rewrite the profile model end-to-end: engine schema `{user: {space: {os: root}}}` with user-only resolution (ladder deleted), env from per-space×per-platform roots with structural-cut `PROJECT_ROOT`, store chain project-first (`{raiz}/.saman/` → env → `config_local` → home) with a hang-safe probe, combo applying roots on selection.

## Architecture Decisions

| # | Choice | Alternatives | Rationale |
|---|---|---|---|
| 1 Schema+legacy | `{user:{TO_VFX/COMP/FROM_VFX:{os:root}}}`; `leer_perfiles` validates envelope only; pure `detectar_forma_perfil`→`"nuevo"\|"legacy"`; write merge replaces legacy | Silent regen; write-side flag only | Delta mandates read-only regen flag; resolve-time detection keeps `leer_perfiles` contract |
| 2 hostname | Removed from all signatures | Ignored compat param | V2 pre-release; dead param misleads; foreign-host fallback wrong |
| 3 Engine API | Signatures below; `variables_entorno(contexto, perfil=None)`; contexto gains `espacio`, `project_root` | Roots embedded in contexto | Keeps contexto data-only; injector passes perfil explicitly |
| 4 `raiz_proyecto_desde_ruta` | Pure stdlib; backslash→slash; first case-insensitive marker segment → prefix; `None` no-marker/empty; `.saman` NOT marker; Windows→`L:/VFX/2026/CINE` | In `rutas_engine` | `core.entorno` owns path-shape logic; `proyecto_desde_ruta` untouched |
| 5 Store chain | `obtener_ruta_store(raiz_proyecto=None)`; menu/panel compute root from `nuke.root().name()`; project store ALWAYS wins when file exists | Drop home fallback | Delta order; clean fallback for untitled/Desktop; legacy home handled by D1 |
| 6 R2 probe | `_probe_store = estado_unidad(dirname)["conectado"] and os.path.isfile(ruta)` + 10 s cache; never creates `.saman/` on read | Bare isfile | `estado_unidad` already bounds dead SMB via subprocess timeout |
| 7 R6 env | `PROJECT_ROOT` = cut root → injected base → current-SO space root; missing space → sibling `reconstruir_rutas(dirname,basename)[comp_SERVER_+suf]` stripped; unresolvable → omit key, never `""` | Emit `""`; fail hard | `[getenv PROJECT_ROOT]` must never resolve empty; `reconstruir_rutas` untouched |
| 8 Shim | `SamanTools/rutas.py` UNCHANGED | Port selector into shim | Imports only entorno/nombres/injector; no hostname-signed call; V1 knob contract kept |
| 9 Testability | Per-slice fixture migration (R1): 3×3 `_perfil_por_defecto()`; ladder tests deleted; green suite per slice | One big rewrite | Budgeted churn; strict TDD |
| 10 Slices | S1 motor+entorno → S2 injector → S3 helper → S4 widget → S5 shim/docs | — | Dependency order |

## Data Flow

    root = nuke.root().name() ──raiz_proyecto_desde_ruta──▶ obtener_ruta_store(root) → {root}/.saman/… ─probe─▶ env/config_local/home
    leer_perfiles → perfiles.get(user) → perfil 3×3 → get_context → variables_entorno → env
    cachear_env + aplicar_entorno ──▶ TCL [getenv PROJECT_ROOT]
    combo (listar_perfiles) ─preparar_seleccion_perfil─┘   selección ⇒ refrescar Reads

## File Changes

| File | Action | Description |
|---|---|---|
| `core/entorno.py` | Modify | ADD `raiz_proyecto_desde_ruta` (pure, docstring ES) |
| `core/rutas_engine.py` | Modify | 3×3 schema; delete ladder (`_emparejar_perfil`, `_merge_perfil`, hosts branch, `ruta_para_plataforma`); ADD `ruta_para_espacio`, `detectar_forma_perfil`, `_espacio_prefijado`; user-only resolve/asegurar + `os.makedirs` bajo lock; `get_context`/`variables_entorno` rework (`project_root`, `espacio`, `carpeta_salida="[getenv PROJECT_ROOT]/COMP/"`) |
| `ui/injector.py` | Modify | `obtener_ruta_store(raiz_proyecto=None)` + `_probe_store` cache; `armar_estado_env` env from space roots, cut root, base→space fallback |
| `ui/menu.py` | Modify | `_resolver_contexto_carga` passes root; user-only |
| `ui/path_manager.py` | Modify | hostname out; ADD `listar_perfiles`, `preparar_seleccion_perfil`; `estado_panel`+`regeneracion`; cambio per-espacio |
| `ui/path_manager_panel.py` | Modify | combo (refresh on open; default ambient user), apply-on-select → `cachear_env`+`aplicar_entorno`+`_refrescar_reads()`, legacy warning, hostname out |
| `docs/ARQUITECTURA-V2.md` | Modify | store-chain order (66–68) + R4 release note |
| `tests/test_entorno.py` | Modify | ADDED: 4 delta scenarios + no-marker, base-sola, `.saman` non-marker, Windows |
| `tests/test_rutas_engine.py` | Rewrite | 3×3 fixtures; ladder tests out; legacy regen; per-space merge |
| `tests/test_injector.py` | Modify | chain + probe cache + space-root env + missing-space fallback |
| `tests/test_path_manager{,_panel}.py` | Modify | user-only; selector/listing; combo refresh/apply/stale-ValueError/legacy warning |
| `tests/test_menu.py` | Modify | root passing |
| `tests/test_shim.py` | Unchanged | proves shim survives (D8) |

## Interfaces / Contracts

```python
def raiz_proyecto_desde_ruta(ruta, marcadores=("TO_VFX","COMP","FROM_VFX")) -> str|None
def leer_perfiles(path) -> dict
def guardar_perfiles(path, perfiles)          # merge 3×3; legacy→replace; makedirs bajo lock
def crear_perfil_default(base=None) -> dict    # 3×3, base slot en un SO
def ruta_para_espacio(perfil, espacio, so) -> str|None
def detectar_forma_perfil(perfil) -> str
def asegurar_perfil(user, path, base=None) -> dict
def resolver_perfil(user, path) -> dict
def get_context(perfil, ruta_plato) -> dict    # + project_root, espacio
def variables_entorno(contexto, perfil=None) -> dict
def armar_estado_env(perfil, so, ruta_plato, base=None) -> dict
def obtener_ruta_store(raiz_proyecto=None) -> str
def listar_perfiles(ruta_store) -> list[str]
def preparar_seleccion_perfil(usuario, ruta_store, so, ruta_plato="") -> dict   # ValueError si falta
def preparar_cambio_base(usuario, ruta_store, so, espacio, nueva_ruta, ruta_plato="") -> dict
def preparar_onboarding(usuario, ruta_store, base, so, ruta_plato="") -> dict
def estado_panel(ruta_store, usuario, so) -> dict   # + regeneracion
```

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | entorno cut/None edges; engine round-trip, per-space merge, legacy regen, concurrency, env sibling fallback, purity; injector chain precedence, probe cache; helper listing/selection/`ValueError`/regen | pytest + monkeypatch; fixtures rewritten (R1) |
| Widget | combo refresh, apply + Reads refresh, stale `ValueError` no partial env, legacy warning, headless degrade | pytest-qt + fakes |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR, executable-classification, or process-integration boundary changed. Only subprocess use (`entorno._verificar_ruta`) is pre-existing and reused.

## Migration / Rollout

Legacy stores unknown at resolve; UI warns once on open; regenerated on next write (dev data, no real migration). `.saman/` created lazily on first write under lock, never on read. **R4 note**: project store wins; foreign-host fallback gone; `carpeta_salida` → `[getenv PROJECT_ROOT]/COMP/`. Rollback: `git revert`; stores re-seed from V1.

## Open Questions

None blocking — flagged items resolved per binding inputs. Residual: `carpeta_salida` token change is breaking for `get_context` consumers.