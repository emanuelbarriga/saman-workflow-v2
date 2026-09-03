# Design: Core Rutas Engine — V2 Foundation

> Scope note: this document exceeds the 800-word skill budget deliberately — the
> security specs already did, and decisions D1–D9 carry binding rationale that
> `sdd-tasks` must not re-derive. English (config.yaml defines no Spanish-design
> rule; Spanish is scoped to code docstrings by the apply rules).

## Technical Approach

Three layers, one public-repo constraint:

1. **Extraction by copy** of `entorno.py`, `nombres.py`, `limpiar.py` from V1 into
   `SamanTools/core/` with logic intact. The ONLY edits are (a) neutralization of
   real routes/tokens (`wupm→estudio`, `wupmCloud→estudioCloud`, `L:/2026→L:/VFX/2026`,
   `/mnt/wupm→/mnt/estudio`, `HTLR/PCF→CINE`) and (b) relative-import fidelity
   (`from .entorno import` inside `core/`). Real paths in module docstrings, fixtures
   and comments are neutralized too (proposal: "Open Decision").
2. **New engine** `core/rutas_engine.py`: JSON profile store, user/hostname
   resolution, tri-platform mapping, string-level `[getenv PROJECT_ROOT]`
   relativization with pre-normalization, context API, data-only env contract,
   locked onboarding. Zero ambient `getpass`/`socket`/`platform` in engine logic.
3. **Purity guard** from commit one: `tests/test_no_import_nuke_en_core.py` with a
   single testable matcher (static + dynamic imports + token hygiene).

Maps to proposal approach (copy, neutralized) and every spec capability
(core-entorno, core-nombres, core-limpiar, core-rutas-engine, core-purity-guard).

## Architecture Decisions

### D1 — `nuke_profiles.json` schema

**Choice** — evaluated proposal accepted in shape, minus `proyecto`:

```json
{
  "perfiles": {
    "ana": {
      "hosts": {
        "ws1": {
          "macOS": "/Volumes/estudio/2026",
          "Windows": "L:/VFX/2026",
          "Linux": "/mnt/estudio/2026"
        }
      },
      "default": {
        "macOS": "/Volumes/estudio/2026",
        "Windows": "L:/VFX/2026",
        "Linux": "/mnt/estudio/2026"
      }
    }
  }
}
```

| Option | Tradeoff | Decision |
|---|---|---|
| `{"perfiles": {...}, "proyecto": "..."}` (evaluated) | wrapper isolates user namespace; `proyecto` has NO consumer — proyecto is derived per-plate by `parsear_plato`/`proyecto_desde_ruta`, never read from the store | Accept wrapper; **reject `proyecto`** (dead key, no spec scenario; wrapper leaves room to add it later without schema break) |
| Flat `{"<usuario>": {...}}` | a user literally named `version`/`proyecto` collides with future top-level metadata | Rejected — `perfiles` wrapper separates user namespace from envelope metadata |
| Flat `{"usuario#host": roots}` | no user-only fallback possible; ugly key parsing | Rejected — breaks spec scenario "fallback to user only" |
| Roots only, no per-user envelope | cannot express user-only vs host-scoped roots | Rejected — precedence needs both `hosts` and `default` |

Semantics: on-disk envelope is `{"perfiles": <inner dict>}`; `leer_perfiles(path)`
returns the **inner dict**; `guardar_perfiles` wraps inner and **preserves unknown
top-level keys** on rewrite (future `version`/`proyecto` metadata survives).
Unknown inner keys (e.g. a future per-user field) are ignored by the engine.

### D2 — `resolver_perfil` precedence and return contract

Canonical order, evaluated against `_emparejar_perfil(user, hostname, perfiles)`:

1. **Exact pair** — `perfiles[user]["hosts"][hostname]` → that roots dict (full profile).
2. **User-only** — `perfiles[user]["default"]` → that roots dict (partial profile).
3. **Hostname-only** — first user in document (insertion) order whose
   `hosts[hostname]` exists → that roots dict (partial profile; shared workstations
   where the machine is known but the user is not). Deterministic because Python
   dicts preserve JSON object order.
4. **Miss** — `None` = the onboarding marker (never an exception, never returned to
   callers as a special object; the public API absorbs it — see D3).

Every match returns the **same-shaped roots dict** (`{"macOS","Windows","Linux"}`);
"full vs partial" is provenance, not shape. `ruta_para_plataforma(perfil, so)`
indexes that dict (`perfil.get(so)` — `None` for a missing platform, no raise).

### D3 — Onboarding under lock

Onboarding is a single function, `asegurar_perfil(user, hostname, path, base=None)`,
wrapped by the public `resolver_perfil` on miss:

```
resolver_perfil(user, hostname, path)
  → leer_perfiles(path)                 # no lock
  → _emparejar_perfil(...)              # match? return roots (no write)
  → None ⇒ asegurar_perfil(...):
       with _lock_perfiles(path):       # exclusive, timeout+retry
         store = leer_perfiles(path)    # RE-READ under lock (fresh)
         match = _emparejar_perfil(...) # re-resolve
         if match: return match         # race won: another process onboarded us
         store[user] = merge(store.get(user), {"hosts": {hostname: roots},
                                               "default": roots})
         write_atomic(store)            # temp + os.replace, keep envelope keys
       return roots
```

Key properties:

- **Race "profile created between resolution and write"**: the re-read + re-resolve
  inside the lock means the loser does NOT overwrite; it returns the winner's profile.
- **Cross-user lost update**: `guardar_perfiles` performs a per-user **merge** (hosts
  merged per-host, `default` overridden, other users untouched) — never a blind
  replace. Scenario "concurrent onboarding does not lose profiles" (ana/ws1 +
  pedro/ws2) passes structurally: each merge only touches its own user.
- **Roots built by `crear_perfil_default(base)`**: fictitious per-platform defaults
  (`/Volumes/estudio/2026`, `L:/VFX/2026`, `/mnt/estudio/2026`); an injected `base`
  fills the slot matching its shape (`/Volumes/`→macOS, `^[A-Za-z]:`→Windows,
  `/mnt/`→Linux), else defaults keep all three. Both `hosts[hostname]` and `default`
  are written so the user-only fallback works for their other machines.
- `guardar_perfiles(path, perfiles)` is independently public (spec: round-trip +
  concurrency scenarios target it directly) and shares the same locked merge kernel.

### D4 — Public API and core dependency graph

```
entorno.py   (os, platform, string, subprocess, time)      standalone
nombres.py   → entorno.proyecto_desde_ruta                 copy-intact (V1 edge)
limpiar.py   (os, re)                                      standalone
rutas_engine.py → entorno.{reconstruir_rutas, proyecto_desde_ruta}
                → nombres.parsear_plato
core/ → never imports ui/ ; stdlib only (guard-enforced)
```

Division of responsibility: `entorno` keeps OS/unit/base detection exactly as V1
(identity untouched); `rutas_engine` owns profiles, mapping, relativization,
context, env contract, persistence, onboarding. The engine makes **no ambient
calls**; where a ported helper is ambient (`parsear_plato` → `proyecto_desde_ruta(ruta)`
uses detected SO), `get_context` overrides the result with
`proyecto_desde_ruta(ruta_plato, base=<matched root>)` — injected base, deterministic.

```python
# SamanTools/core/rutas_engine.py  (all params injected; stdlib only)
def leer_perfiles(path: str) -> dict                     # {} if missing; ValueError if malformed
def guardar_perfiles(path: str, perfiles: dict) -> None  # lock + merge + atomic write
def resolver_perfil(user: str, hostname: str, path: str) -> dict  # resolve → onboard on miss → roots
def _emparejar_perfil(user, hostname, perfiles) -> dict | None    # pure precedence matcher (D2)
def ruta_para_plataforma(perfil: dict, so: str) -> str | None
def relativizar(ruta_absoluta: str, base: str) -> str
def absolutizar(ruta: str, base: str) -> str
def get_context(perfil: dict, ruta_plato: str) -> dict   # {proyecto, plano, version, carpeta_salida, base, so}
def variables_entorno(contexto: dict) -> dict            # {"PROJECT_ROOT": ...} + PYTHON_* if applicable
def crear_perfil_default(base: str | None) -> dict
def _normalizar_para_comparar(path: str) -> str          # D5
def _lock_perfiles(path: str) -> contextmanager          # D6
```

`get_context` returns the 4 spec keys plus `base` (absolute, prefix-matched) and
`so` (the platform whose root matched): `variables_entorno` consumes them so the
injector applies the contract "without re-deriving profiles" (spec mandate).
`carpeta_salida = "[getenv PROJECT_ROOT]/{proyecto}/COMP/"` — uppercase prefix,
consistent with `reconstruir_rutas` folder naming. `variables_entorno`:
`PROJECT_ROOT = base`; plus `PYTHON_TO_VFX/PYTHON_COMP/PYTHON_FROM_VFX` from
`reconstruir_rutas(base, proyecto)` filtered to `sufijo_so(so)` when `so` is known.
`os.environ` is never mutated.

### D5 — Normalization helper

`_normalizar_para_comparar(path) -> str` — **canonical string, not a tuple** (a
tuple adds nothing: only the normalized base length is consumed downstream):

1. `str(path).replace("\\", "/")`
2. `.strip()` then `.rstrip("/")`
3. fold case — `.lower()` — of the WHOLE string (`L:/VFX/2026` → `l:/vfx/2026`, and `l:\vfx\2026` → `l:/vfx/2026`)

**Two-track rule (comparison vs emission):** the canonical string is used ONLY
for prefix comparisons AND length accounting. `relativizar` performs the
prefix guard against the canonical copy (case-insensitive on the whole root,
so drive AND volume casing variants match: `l:\vfx\2026\CINE\...` under base
`L:/VFX/2026` matches), then slices **the separator-normalized original** (not
the canonical copy) at `len(base_normalizada)` — every transform is
length-preserving, so the relative remainder keeps its ORIGINAL casing:
`CINE/TO_VFX/ep.nk` stays `CINE/TO_VFX/ep.nk` (never lowercased to
`cine/to_vfx/...`). Concretely:

```python
ruta_s = ruta.replace("\\", "/")                 # keep original casing
base_s = base.replace("\\", "/")
clave  = ruta_s.lower()                          # comparison copy
clave_base = base_s.lower()
if clave.startswith(clave_base + "/"):           # partial-prefix guard
    resto = ruta_s[len(base_s):].lstrip("/")     # original casing
    return f"[getenv PROJECT_ROOT]/{resto}"
return ruta_s
```

`absolutizar` substitutes the **injected base verbatim** (original drive
casing, forward slashes) for `[getenv PROJECT_ROOT]`. Partial-prefix guard:
`startswith(clave_base + "/")` rejects `/Volumes/estudio2026/...` under base
`/Volumes/estudio/2026`. Lives in `rutas_engine.py` (engine scope; `entorno`'s
own normalization stays V1-verbatim per copy-intact).

This is the ONLY mechanism that satisfies the binding spec equivalence
`l:/vfx/2026 ≡ L:/VFX/2026` AND the scenario output preserving `CINE/TO_VFX`.

### D6 — Lock concretization

`_lock_perfiles(path)` context manager over a **sibling** lock file
`path + ".lock"` — never the target: `os.replace` swaps the target inode, so a
lock held on the target is orphaned after the first write and the next process
locks a different inode (mutual exclusion silently lost). The sibling file is
stable across replaces.

| Platform | Mechanism | Attempt |
|---|---|---|
| POSIX | `fcntl.lockf(fd, LOCK_EX \| LOCK_NB)` | poll every 0.25 s within a **2.0 s** attempt |
| Windows | `msvcrt.locking(fd, LK_NBLCK, 1)` after `seek(0)` (+ pad file to ≥1 byte) | same poll/attempt |
| neither | documented degraded no-op: atomic `os.replace` still prevents torn reads/writes; cross-process cross-user lost updates possible; same-pair last-writer-wins | no block |

Retries: **3 attempts** of ≤2.0 s each (worst ~6.25 s), then raise
`TimeoutError("No se pudo adquirir lock de perfiles")` — never a silent overwrite.
Lock scope: acquire → fresh `leer_perfiles` → merge → temp write → `os.replace` →
release. Readers never lock (atomic replace ⇒ readers always see a full inode).
A dedicated `_lock_clase(plataforma)` factory is unit-tested with injected platform
names so both fcntl and msvcrt branches are covered on the macOS dev machine; the
real fcntl path is exercised by the process-based concurrency test.

### D7 — Guard matcher

One matcher serves both static and dynamic detection (spec: "a single tokenizer
function MUST serve both matchers"), driven by one forbidden-module set:

```python
_MODULOS_PROHIBIDOS = ("nuke", "nukescripts", "PySide2", "PySide6")
# one compiled pattern:
#   static:  ^\s*(?:import\s+(?:nuke|nukescripts|PySide2|PySide6)\b
#                  |from\s+(?:nuke|nukescripts|PySide2|PySide6)\b)
#   dynamic: (?:__import__|import_module)\s*\(\s*['"](?:nuke|nukescripts|PySide2|PySide6)['"]
def detectar_violaciones(texto: str) -> list[str]   # one result entry per offending line
```

- Static anchored to `^\s*` → `# import nuke` comments and mid-line string literals
  pass; real indented imports inside function bodies still match.
- Dynamic unanchored (appears mid-line in bodies); target whitelist means
  `importlib.import_module('os')` passes.
- The guard test itself calls `detectar_violaciones` with synthetic samples
  (meeting "the guard itself MUST be testable") and is exempt from the hygiene scan
  (it must name the tokens to define the regex).
- Hygiene scan `auditar_tokens(raiz)`: case-insensitive banned tokens
  `wupm|LucidLink|HTLR|PCF` over `SamanTools/` and `tests/` (skip `__pycache__`).
- Real scan: `SamanTools/core/**/*.py` through `detectar_violaciones`.

## Data Flow

```
resolver_perfil(user, hostname, path)
  │  leer (no lock) ── _emparejar ──> hit ──> roots dict ──────┐
  │                                     miss                   │
  │  asegurar_perfil: lock → re-read → re-resolve → merge →    │
  │                   atomic write → unlock → roots dict ◄─────┘
  │
ruta_para_plataforma(roots, so) → base
get_context(roots, plato): base ← prefix-match(roots, plato)
  → parsear_plato(plato) + proyecto override via proyecto_desde_ruta(plato, base)
  → {proyecto, plano, version, carpeta_salida, base, so}
variables_entorno(contexto) → {"PROJECT_ROOT": base, "PYTHON_*": ...}   # never touches os.environ
relativizar(abs, base) ──normalize→ prefix?──> "[getenv PROJECT_ROOT]/<rel>" | unchanged
absolutizar(rel, base) → base-as-injected + rel
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `SamanTools/__init__.py` | Create | `__version__ = "2.0.0"` (SemVer source of truth) |
| `SamanTools/core/__init__.py` | Create | package marker |
| `SamanTools/core/entorno.py` | Create | V1 copy, neutralized (`/Volumes/estudio/2026`, `estudioCloud`, `L:/VFX/2026` scan, `/mnt/estudio/2026`, CINE) |
| `SamanTools/core/nombres.py` | Create | V1 copy, neutralized; `from .entorno import` kept |
| `SamanTools/core/limpiar.py` | Create | V1 copy (no real tokens in docstrings) |
| `SamanTools/core/rutas_engine.py` | Create | engine: store, resolution, mapping, relativization, context, env contract, onboarding, lock |
| `tests/conftest.py` | Create | minimal, NO nuke stub |
| `tests/test_entorno.py` | Create | ported pure subset (V1 lines 37–267); stub block 304–533 deferred |
| `tests/test_nombres.py` | Create | ported, neutralized |
| `tests/test_limpiar.py` | Create | ported + synthetic inline regression sample (replaces `Review.gizmo`) |
| `tests/test_rutas_engine.py` | Create | new engine suite (store, resolution, mapping, relativization, context, env contract, onboarding, concurrency) |
| `tests/test_no_import_nuke_en_core.py` | Create | guard: static+dynamic matcher, core scan, token hygiene |

## Interfaces / Contracts

Schema (D1) and API signatures (D4) are the contracts. Additions beyond spec
letter, all documented at D1/D4: `contexto.base`, `contexto.so`, envelope-key
preservation, merge semantics of `guardar_perfiles`. `TimeoutError` on lock
exhaustion; `ValueError` on malformed JSON; permissive missing file.

## Testing Strategy

| Layer | Test file | Spec | Key cases |
|---|---|---|---|
| Unit | `tests/test_entorno.py` | core-entorno | SO tables; macOS/estudio order; Windows scan `Z:/VFX`+`T:/VFX` no-dup (L exempt); extra wins; timeout→disconnected; cache single verify; 9 keys `comp_SERVER_MAC` legacy casing; forward slashes; partial-prefix `estudio2026` → None |
| Unit | `tests/test_nombres.py` | core-nombres | canonical plate; EP folder authoritative; malformed version moved to end; `comp_SAMAN` metadata; bare basename; Windows backslashes; never raises |
| Unit | `tests/test_limpiar.py` | core-limpiar | three knobs stripped; legit untouched; idempotent; BOM+CRLF preserved; latin-1 byte 0xE9; unchanged → 0 no temp; missing → FileNotFoundError; mixed-tree summary; ext filter; synthetic sample |
| Unit | `tests/test_rutas_engine.py` | core-rutas-engine | determinism (ana/ws1 twice); missing file → {}; malformed → ValueError; atomic round-trip no temps; **concurrent onboarding** (multiprocess on POSIX: ana/ws1 + pedro/ws2 both persist, no leftovers); precedence exact→user-only→hostname-only; platform mapping; relativize macOS + Windows `l:\vfx\2026\CINE\...` case/separator variants **preserving output casing `CINE/TO_VFX`** (two-track D5: comparison on canonical copy, emission from separator-normalized original); outside base unchanged; absolutize casing-checks; context dict identity; env contract PROJECT_ROOT present + `os.environ` unmutated; onboarding persists + second resolve returns it; lock timeout → TimeoutError; `_lock_clase` factory covers fcntl/msvcrt/no-op branches |
| Unit | `tests/test_no_import_nuke_en_core.py` | core-purity-guard | `import nuke` fails; `importlib.import_module("nuke")` fails; `import_module("os")` passes; PySide6 `from` fails; `__import__('nuke')` fails; comment `# import nuke...` passes; banned tokens flagged; neutralized sources pass (self-exempt) |
| Integration | whole suite | core-purity-guard | `python3 -m pytest` green with no nuke installed; guard scans real `core/` |

Concurrency caveat (D6): POSIX `fcntl` locks are per-process, so two threads in
one process do not contend — the concurrency spec test uses `multiprocessing` with
a start barrier on POSIX; a thread-based merge assertion is the documented weaker
fallback elsewhere.

## Threat Matrix

| Boundary | Applicability | Rationale |
|---|---|---|
| Documentation-like paths | N/A | No executable docs/MDX/`README.sh` handling in this change |
| Git repository selection | N/A | No VCS invocation |
| Commit state | N/A | No commit/index manipulation |
| Push state | N/A | No push/refspec logic |
| PR commands | N/A | No PR automation |

Shell/subprocess note: extracted `entorno._verificar_ruta` runs fixed-argv
existence checks (`["ls","-d",r]` / `["cmd","/c","dir",r]`, no `shell=True`, no
user-controlled command names, `DEVNULL`, timeout). That is V1 behavior preserved
verbatim by the copy-intact mandate — not new process integration, and it is
unchanged by this design. The engine adds no subprocess/shell boundary.

## Migration / Rollout

No migration: V2 repo is blank, no data exists, profile store is created on first
onboarding. Rollback = per-commit revert; engine removes cleanly pre-UI (proposal).

## Open Questions

- [ ] `carpeta_salida` convention (`/{proyecto}/COMP/`) is a first definition — V1
      has no `get_context` precedent; verify against the future load layer.
- [ ] The sibling `nuke_profiles.json.lock` file persists after use (by design —
      deleting it reintroduces races); confirm the artist-side profile location
      (out of repo) at load-layer design.

## Key Learnings

1. Locking a file that gets `os.replace`d is broken — the sibling lock file is mandatory for atomic-write stores.
2. POSIX fcntl locks are per-process, so real concurrency tests need multiprocessing, not threads.
3. The `perfiles` envelope wrapper isolates arbitrary usernames from future metadata keys.
4. Length-preserving normalization (backslash→slash, drive-case lowering) keeps original-casing output safe to slice.
5. Copy-intact extraction preserves V1 ambient helpers; the engine overrides their ambient results with injected bases.