# Core Rutas Engine Specification

## Purpose

NEW pure-stdlib engine (`SamanTools/core/rutas_engine.py`): JSON profile store, resolution by user (hostname removed), per-space tri-platform mapping, string-level `[getenv PROJECT_ROOT]` relativization, context API, unknown-user onboarding. Logic MUST be fully injectable (user, profile path, base as parameters); ambient `getpass`/`socket` MUST NOT appear in engine logic. Scenario paths MUST be fictitious or relative.

## Requirements

### Requirement: Injectable, deterministic API

All entry points MUST take `user`, profile `path` and base as parameters, never reading identity/environment themselves. The `hostname` parameter MUST be REMOVED: a profile is scoped to the user only. Engine tests MUST inject user/path/base.

(Previously: entry points took `user`, `hostname`, `path` and `base`; tests injected user/hostname/base.)

#### Scenario: same inputs, same outputs

- GIVEN `"ana"`, a store path and base `"/Volumes/estudio/2026/CINE/COMP"` injected identically twice
- WHEN resolution and mapping run on both calls
- THEN results are identical regardless of the host running the tests

### Requirement: JSON profile store

`leer_perfiles(path)` MUST load `nuke_profiles.json` into a dict keyed by user with per-space per-platform roots: `{user: {TO_VFX: {os: root}, COMP: {os: root}, FROM_VFX: {os: root}}}`. A missing file MUST yield an empty store (no error); malformed JSON MUST raise `ValueError`. `guardar_perfiles(path, perfiles)` MUST persist atomically (same-dir temp + `os.replace`) and round-trip: read-after-write equals the written store.

**Concurrent-write safety:** `guardar_perfiles` MUST serialize concurrent writers so parallel Nuke instances / render nodes on an unconfigured station do not lose each other's profiles. On POSIX it MUST use an exclusive advisory lock (`fcntl`) on a sibling lock file (or the target file); on Windows it MUST use `msvcrt.locking` (or equivalent best-effort exclusive lock). The lock MUST be held across read-merge-write: read current store under lock, merge the new profile into the in-memory dict (per-user, per-space), write atomically, release. A lock acquisition timeout (SHOULD be short, e.g. ≤ 2 s) MUST fall back to a retry, and an exhausted retry MUST raise a `TimeoutError`-style exception rather than silently overwrite. All locking MUST use stdlib modules only.

**Legacy shape:** a user entry carrying `hosts`/`default` and NO space keys (`TO_VFX`/`COMP`/`FROM_VFX`) MUST be recognized as legacy. Resolution MUST treat it as unknown and writes MUST regenerate it with the new shape, flagging the regeneration so the UI can warn. `.saman/` MUST be created lazily on FIRST WRITE (parent dir via `os.makedirs(dirname, exist_ok=True)` under the lock), never on read.

#### Scenario: missing file starts empty

- GIVEN a path with no `nuke_profiles.json`
- WHEN `leer_perfiles(path)` runs
- THEN it returns an empty store without raising

#### Scenario: malformed JSON fails loudly

- GIVEN `nuke_profiles.json` with invalid JSON
- WHEN `leer_perfiles(path)` runs
- THEN it raises `ValueError`

#### Scenario: atomic round-trip

- GIVEN a store written via `guardar_perfiles` with the new per-space shape
- WHEN it is read back
- THEN it equals the written store, with no temp files left

#### Scenario: concurrent onboarding does not lose profiles

- GIVEN two stores both starting empty at the same path, and two concurrent `guardar_perfiles` calls each adding a different user (`"ana"` and `"pedro"`), with the lock held across read-merge-write
- WHEN both calls complete
- THEN the final store contains BOTH users (no lost update), and no temp files remain

#### Scenario: legacy entry regenerates with a warning flag

- GIVEN a store where `"ana"` has `{"hosts": {...}, "default": {...}}` and no space keys
- WHEN a write for `"ana"` runs
- THEN the entry is replaced by the new per-space shape AND the write signals regeneration (for a UI warning)

### Requirement: Profile resolution by user

`resolver_perfil(user, path)` MUST match `perfiles.get(user)` directly (no hostname, no ladder). An unknown user MUST trigger onboarding, never raise and never return `None` publicly.

(Previously: `Profile resolution by user/hostname` — matched exact user+hostname, then user-only, then hostname-only through a precedence ladder. Reason for rename: the hostname level disappears — a profile is a username with independent per-platform space roots; the precedence ladder is removed. Migration: update resolver/tests/doc references from pair identity to user-only.)

#### Scenario: known user resolves

- GIVEN a store with profile for `"ana"`
- WHEN `resolver_perfil("ana", path)` runs
- THEN the 3-space profile is returned

#### Scenario: absent user triggers onboarding

- GIVEN a store without `"nuevo"`
- WHEN `resolver_perfil("nuevo", path)` runs
- THEN no exception is raised, onboarding persists a new-shape profile, and a later resolve returns it

### Requirement: Per-space tri-platform mapping

A resolved profile MUST expose one root per space per platform. `ruta_para_espacio(perfil, espacio, so)` MUST return the root for `espacio` in (`TO_VFX`, `COMP`, `FROM_VFX`) on `so` in (`macOS`, `Windows`, `Linux`); a missing combination MUST yield `None` without raising. The three spaces are INDEPENDENT (may live on different disks). Roots MUST be fictitious (`/Volumes/estudio/2026/CINE/TO_VFX`, `L:/VFX/2026/CINE/TO_VFX`, `/mnt/estudio/2026/CINE/TO_VFX`) or `[getenv PROJECT_ROOT]`-relative; never real studio paths.

(Previously: `Tri-platform mapping` — one base root per platform via `ruta_para_plataforma(perfil, so)`. Reason for rename: roots are now per space AND per platform — three independent roots per OS, no single base per profile. Migration: replace `ruta_para_plataforma(perfil, so)` call sites/tests with the space-aware lookup.)

#### Scenario: independent space roots map per platform

- GIVEN a profile whose COMP root for macOS is `/Volumes/estudio/2026/CINE/COMP` and for Windows is `L:/VFX/2026/CINE/COMP`
- WHEN `ruta_para_espacio(perfil, "COMP", so)` runs for each `so`
- THEN each returns its fictitious root

### Requirement: String-level relativization

`relativizar(ruta_absoluta, base)` MUST convert a path under `base` to `"[getenv PROJECT_ROOT]/<rel>"`; a path outside `base` MUST be returned unchanged. `absolutizar(ruta, base)` MUST expand `[getenv PROJECT_ROOT]` into the injected `base`. Both MUST be pure string ops (no filesystem access).

**Normalization precondition (Windows safety):** before any prefix comparison, BOTH inputs MUST be normalized: backslashes converted to `/`, drive-letter case lowercased on Windows-style roots (`l:/vfx/2026` ≡ `L:/VFX/2026`), trailing slashes stripped. A comparison against raw, non-normalized strings MUST NOT be used: it would silently fail to relativize Windows paths that differ only in separator or drive case. `absolutizar` output SHOULD keep the injected `base`'s original casing and use forward slashes.

#### Scenario: absolute to placeholder

- GIVEN ruta `"/Volumes/estudio/2026/CINE/TO_VFX/ep.nk"`, base `"/Volumes/estudio/2026"`
- WHEN `relativizar(ruta, base)` runs
- THEN result equals `"[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk"`

#### Scenario: placeholder back to absolute

- GIVEN ruta `"[getenv PROJECT_ROOT]/CINE/ep.nk"`, base `"/Volumes/estudio/2026"`
- WHEN `absolutizar(ruta, base)` runs
- THEN result equals `"/Volumes/estudio/2026/CINE/ep.nk"`

#### Scenario: outside base untouched

- GIVEN ruta `"/elsewhere/x.nk"`, base `"/Volumes/estudio/2026"`
- WHEN `relativizar(ruta, base)` runs
- THEN result is unchanged

#### Scenario: Windows casing and separator variants relativize

- GIVEN ruta `"l:\\vfx\\2026\\CINE\\TO_VFX\\ep.nk"` and base `"L:/VFX/2026"`
- WHEN `relativizar(ruta, base)` runs
- THEN result equals `"[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk"`

#### Scenario: Windows variant round-trips back

- GIVEN ruta `"[getenv PROJECT_ROOT]/CINE/ep.nk"` and base `"L:/VFX/2026"`
- WHEN `absolutizar(ruta, base)` runs
- THEN result uses forward slashes and matches `"L:/VFX/2026/CINE/ep.nk"` case-insensitively on the drive letter

### Requirement: Context API

`get_context(perfil, ruta_plato)` MUST return `{proyecto, plano, version, carpeta_salida}` plus the space root prefixing the plate and its SO — derived from the profile's space roots, not a single base. `proyecto` MUST be the project segment of the plate's project root (structural cut at `TO_VFX|COMP|FROM_VFX`, via `raiz_proyecto_desde_ruta`), falling back to the plate-name token. `carpeta_salida` MUST be `[getenv PROJECT_ROOT]`-relative (e.g. `[getenv PROJECT_ROOT]/COMP/`) or fictitious. Identical inputs MUST yield identical dicts.

(Previously: base/so derived from the first profile root prefixing the plate; proyecto via `proyecto_desde_ruta(plato, base)`.)

#### Scenario: context from a space root

- GIVEN a profile with COMP root `/Volumes/estudio/2026/CINE/COMP` and plate `"/Volumes/estudio/2026/CINE/COMP/EP_100/CINE_107_008_00100_V01.mov"`
- WHEN `get_context(perfil, ruta_plato)` runs
- THEN `proyecto=="CINE"`, `plano=="008_00100"`, `version=="V01"` and `carpeta_salida == "[getenv PROJECT_ROOT]/COMP/"`

### Requirement: Environment variables exposure (TCL contract)

The engine MUST expose the resolved environment contract as data, and MUST NOT mutate `os.environ` itself (purity). `variables_entorno(contexto)` MUST return at least `{"PROJECT_ROOT": <project root via structural cut>}` plus `PYTHON_TO_VFX` / `PYTHON_COMP` / `PYTHON_FROM_VFX` set to the profile's space roots for the current SO. `PROJECT_ROOT` MUST be the plate's project root derived by structural cut (`raiz_proyecto_desde_ruta`), NOT base detection, and the cut markers MUST remain canonical-only: an extra space MUST NEVER act as a cut marker (extras are env-only, non-goal R6). For every EXTRA profile key the dict MUST include `PYTHON_<extra>` (key via `_clave_env_para_espacio`) set to that extra's root for the current SO. Iteration MUST be deterministic: canonical spaces first (their `_ESPACIOS` order), extras sorted lexicographically. When a CANONICAL space root is missing, derivation MUST fall back to `reconstruir_rutas` semantics (V1 knob contract unchanged); when an EXTRA root is missing, the key MUST be OMITTED — never `""`, with no sibling fallback. This is the ONLY contract that lets Nuke's TCL resolve `[getenv PROJECT_ROOT]`; the injector applies it at script load.

(Previously: `variables_entorno(contexto)` iterated only the canonical `_ESPACIOS` trio; extra profile keys were not exposed.)

#### Scenario: env contract contains cut PROJECT_ROOT and space roots

- GIVEN a profile with COMP root `/Volumes/estudio/2026/CINE/COMP` (macOS) and a plate under that root
- WHEN `variables_entorno(contexto)` runs
- THEN the dict has `"PROJECT_ROOT": "/Volumes/estudio/2026/CINE"` and `"PYTHON_COMP": "/Volumes/estudio/2026/CINE/COMP"`, and the engine has NOT modified `os.environ`

#### Scenario: extras emit sorted sanitized keys after the canonical trio

- GIVEN a profile with canonical roots plus extras `"3D"` and `"matte paint"` for the current SO
- WHEN `variables_entorno(contexto)` runs
- THEN the keys start `PYTHON_TO_VFX`, `PYTHON_COMP`, `PYTHON_FROM_VFX` (canonical order) followed by `PYTHON_3D`, `PYTHON_MATTE_PAINT` (sorted), and identical inputs yield an identical dict

#### Scenario: missing extra root omits the key

- GIVEN an extra `"3D"` with no root for the current SO and no sibling fallback
- WHEN `variables_entorno(contexto)` runs
- THEN `"PYTHON_3D"` is absent from the dict and no `""` value appears

#### Scenario: plate under an extra root gets no structural cut

- GIVEN a plate `"/Volumes/estudio/2026/CINE/3D/ep.nk"` under an extra root
- WHEN `variables_entorno(contexto)` runs
- THEN `PROJECT_ROOT` falls back (no cut at `3D`), while `PYTHON_3D` is still present

### Requirement: Unknown-user onboarding

When no profile matches, the engine MUST create and persist a default 3-space profile (fictitious per-space per-platform roots, or the injected base slot-matched into each space) at the injected store path, without raising and without user interaction. A legacy-shaped entry MUST be re-onboarded with the new shape and regeneration flagged. A later `resolver_perfil(user, path)` MUST return it. The write MUST create the store's parent dir (`.saman/`) lazily under the lock.

(Previously: created per-platform roots plus `hosts[hostname]` and `default` for the user/hostname pair.)

#### Scenario: onboarding persists the profile

- GIVEN a store without `"nuevo"` and an injected writable path
- WHEN resolution triggers onboarding
- THEN no error is raised, the store now contains `"nuevo"` with 3 spaces × 3 OS roots derived from the injected base's slot, and a second resolve returns it

### Requirement: Space-name env-key sanitizer (`_clave_env_para_espacio`)

The engine MUST provide a pure sanitizer `_clave_env_para_espacio(nombre)` converting a space name into an env-key suffix: UPPERCASE; every char outside `A-Z0-9` → `_`; collapse runs of `_`; strip leading/trailing `_`. A result that is empty after sanitizing MUST raise `ValueError` (reject). The environment key MUST be `"PYTHON_" + <sanitized>`.

#### Scenario: valid names sanitize to stable keys

- GIVEN the space names `"3D"` and `"matte paint"`
- WHEN the sanitizer runs on each
- THEN the suffixes are `"3D"` and `"MATTE_PAINT"`, producing keys `"PYTHON_3D"` and `"PYTHON_MATTE_PAINT"`

#### Scenario: path-like name rejected (R8)

- GIVEN the name `"foo/bar"`
- WHEN the sanitizer runs
- THEN it raises `ValueError` and no key is produced

#### Scenario: JSON-reserved-looking name rejected (R8)

- GIVEN the name `"{}"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: empty-after-sanitize rejected

- GIVEN a name sanitizing to nothing (e.g. `"---"` or empty)
- WHEN the sanitizer runs
- THEN it raises `ValueError`

### Requirement: Lock-guarded extra-space removal (`eliminar_espacio_store`)

`eliminar_espacio_store(path, user, espacio)` MUST remove exactly the space key `espacio` from the user's entry and MUST NOT alter any other space, extra key or user. It MUST hold the same exclusive lock as `guardar_perfiles` across read-remove-write and write atomically (same-dir temp + `os.replace`), mirroring `renombrar_perfil_store`. Removing an absent space of an existing user MUST be a no-op (store unchanged). An unknown user MUST raise `ValueError`.

#### Scenario: removes only the target key

- GIVEN `"ana"` with canonical spaces plus extra `"3D"`, and `"pedro"` in the store
- WHEN `eliminar_espacio_store(path, "ana", "3D")` runs
- THEN `"ana"` keeps all canonical spaces, `"3D"` is gone, and `"pedro"` is unchanged

#### Scenario: concurrent removals of different keys both persist

- GIVEN two concurrent `eliminar_espacio_store` calls removing different extras of the same user
- WHEN both complete
- THEN the final store has neither extra and all remaining keys are intact (no lost update)

#### Scenario: removing an absent space is a no-op

- GIVEN `"ana"` whose profile has no `"PREVIEW"` key
- WHEN `eliminar_espacio_store(path, "ana", "PREVIEW")` runs
- THEN the store is unchanged and no error is raised

### Requirement: Canonical space definitions agreement (test)

There MUST be a test asserting that the module-level canonical space definitions of `rutas_engine`, `injector`, `path_manager` and `path_manager_panel` define the SAME set `{"TO_VFX", "COMP", "FROM_VFX"}`. `entorno.PREFIJOS` MUST be excluded from the equality (its middle prefix is deliberately V1-cased as `"comp"`).

#### Scenario: agreement holds across the four modules

- GIVEN the module-level constants of the four modules
- WHEN the agreement test runs
- THEN all four canonical sets are equal, and `entorno.PREFIJOS` is not part of the comparison