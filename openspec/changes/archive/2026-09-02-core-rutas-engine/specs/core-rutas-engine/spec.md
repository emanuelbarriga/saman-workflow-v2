# Core Rutas Engine Specification

## Purpose

NEW pure-stdlib engine (`SamanTools/core/rutas_engine.py`): JSON profile store, resolution by user/hostname, tri-platform mapping, string-level `[getenv PROJECT_ROOT]` relativization, context API, unknown-user onboarding. Logic MUST be fully injectable (user, hostname, profile path, base as parameters); ambient `getpass`/`socket` MUST NOT appear in engine logic. Scenario paths MUST be fictitious or relative.

## Requirements

### Requirement: Injectable, deterministic API

All entry points MUST take `user`, `hostname`, profile `path` and base as parameters, never reading identity/environment themselves. Engine tests MUST inject user/hostname/base.

#### Scenario: same inputs, same outputs

- GIVEN `"ana"`, `"ws1"`, base `"/Volumes/estudio/2026"` injected identically twice
- WHEN resolution and mapping run on both calls
- THEN results are identical regardless of the host running the tests

### Requirement: JSON profile store

`leer_perfiles(path)` MUST load `nuke_profiles.json` into a dict keyed by user/hostname with per-platform roots. A missing file MUST yield an empty store (no error); malformed JSON MUST raise `ValueError`. `guardar_perfiles(path, perfiles)` MUST persist atomically (same-dir temp + `os.replace`) and round-trip: read-after-write equals the written store.

**Concurrent-write safety:** `guardar_perfiles` MUST serialize concurrent writers so parallel Nuke instances / render nodes on an unconfigured station do not lose each other's profiles. On POSIX it MUST use an exclusive advisory lock (`fcntl`) on a sibling lock file (or the target file); on Windows it MUST use `msvcrt.locking` (or equivalent best-effort exclusive lock). The lock MUST be held across read-merge-write: read current store under lock, merge the new profile into the in-memory dict, write atomically, release. A lock acquisition timeout (SHOULD be short, e.g. ≤ 2 s) MUST fall back to a retry, and an exhausted retry MUST raise a `TimeoutError`-style exception rather than silently overwrite. All locking MUST use stdlib modules only.

#### Scenario: missing file starts empty

- GIVEN a path with no `nuke_profiles.json`
- WHEN `leer_perfiles(path)` runs
- THEN it returns an empty store without raising

#### Scenario: malformed JSON fails loudly

- GIVEN `nuke_profiles.json` with invalid JSON
- WHEN `leer_perfiles(path)` runs
- THEN it raises `ValueError`

#### Scenario: atomic round-trip

- GIVEN a store written via `guardar_perfiles`
- WHEN it is read back
- THEN it equals the written store, with no temp files left

#### Scenario: concurrent onboarding does not lose profiles

- GIVEN two stores both starting empty at the same path, and two concurrent `guardar_perfiles` calls each adding a different profile (`"ana"/"ws1"` and `"pedro"/"ws2"`), with the lock held across read-merge-write
- WHEN both calls complete
- THEN the final store contains BOTH profiles (no lost update), and no temp files remain

### Requirement: Profile resolution by user/hostname

`resolver_perfil(user, hostname)` MUST match exact user+hostname, then user-only, then hostname-only (documented precedence). An unknown user MUST trigger onboarding, never raise.

#### Scenario: known pair resolves

- GIVEN a store with profile for `"ana"`/`"ws1"`
- WHEN `resolver_perfil("ana", "ws1")` runs
- THEN the profile is returned

#### Scenario: fallback to user only

- GIVEN a store containing only user `"ana"`
- WHEN `resolver_perfil("ana", "otra-maquina")` runs
- THEN the user-only profile is returned

### Requirement: Tri-platform mapping

A resolved profile MUST expose one base root per platform. `ruta_para_plataforma(perfil, so)` MUST return the root for `"macOS"`, `"Windows"` or `"Linux"`. Roots MUST be fictitious (`/Volumes/estudio/2026`, `L:/VFX/2026`, `/mnt/estudio/2026`) or `[getenv PROJECT_ROOT]`-relative; never real studio paths.

#### Scenario: known profile maps each platform

- GIVEN a profile with fictitious roots for macOS, Windows and Linux
- WHEN `ruta_para_plataforma(perfil, so)` runs for each `so`
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

`get_context(perfil, ruta_plato)` MUST return `{proyecto, plano, version, carpeta_salida}` derived only from the injected profile and plate. `carpeta_salida` MUST be `[getenv PROJECT_ROOT]`-relative or fictitious. Identical inputs MUST yield identical dicts.

#### Scenario: context from injected data

- GIVEN a profile with base `/Volumes/estudio/2026` and plate `"CINE_107_008_00100_V01.mov"`
- WHEN `get_context(perfil, ruta_plato)` runs
- THEN `proyecto=="CINE"`, `plano=="008_00100"`, `version=="V01"` and `carpeta_salida` starts with `"[getenv PROJECT_ROOT]"`

### Requirement: Environment variables exposure (TCL contract)

The engine MUST expose the resolved environment contract as data, and MUST NOT mutate `os.environ` itself (purity). `variables_entorno(contexto)` MUST return a dict of at least `{"PROJECT_ROOT": <resolved absolute base>}` (plus PYTHON_TO_VFX / PYTHON_COMP / PYTHON_FROM_VFX equivalents derived from `reconstruir_rutas`, if applicable). This is the ONLY contract that lets Nuke's TCL interpreter resolve `[getenv PROJECT_ROOT]` in Read/Write node file paths: a later UI/load layer (out of scope here) reads this dict and applies it to `os.environ` at script load (`addOnScriptLoad`). Without that injected variable, TCL `[getenv PROJECT_ROOT]` evaluates empty and nodes go red — the spec MUST keep this mapping purely data-driven so the injector can apply it without re-deriving profiles.

#### Scenario: env contract contains PROJECT_ROOT

- GIVEN a resolved profile with base `"/Volumes/estudio/2026"`
- WHEN `variables_entorno(contexto)` runs
- THEN the returned dict has `"PROJECT_ROOT": "/Volumes/estudio/2026"` and the engine has NOT modified `os.environ`

### Requirement: Unknown-user onboarding

When no profile matches, the engine MUST create and persist a default profile (fictitious per-platform roots, or the injected base) at the injected store path, without raising and without user interaction. A later `resolver_perfil` for that pair MUST return it.

#### Scenario: onboarding persists the profile

- GIVEN a store without `"nuevo"/"pc9"` and an injected writable path
- WHEN resolution triggers onboarding
- THEN no error is raised, the store now contains `"nuevo"/"pc9"`, and a second resolve returns it