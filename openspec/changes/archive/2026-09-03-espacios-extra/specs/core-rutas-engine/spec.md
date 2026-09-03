# Delta for Core Rutas Engine

## ADDED Requirements

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

## MODIFIED Requirements

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