# Delta for panel-path-manager-helper

## MODIFIED Requirements

### Requirement: Pure, deterministic data layer

The helper MUST NOT import nuke or PySide, MUST NOT read or mutate `os.environ`, and MUST take identity (`user` only — hostname REMOVED) and store path as injectable parameters. Identical inputs MUST yield identical outputs.

(Previously: identity was the `(user, hostname)` pair.)

#### Scenario: same inputs, same outputs, no env access

- GIVEN `"ana"`, an injected store path, and a snapshot of `os.environ`
- WHEN the profile read runs twice
- THEN both results are identical and `os.environ` is unchanged

### Requirement: Active profile read with onboarding marker

For a known user the helper MUST return the resolved profile (3 spaces × 3 platforms). For an unknown user it MUST return an onboarding marker, never raise, and never persist during detection, so the widget can show the base form before any write. A legacy-shaped entry (`hosts`/`default`, no space keys) MUST be reported with a regeneration flag — read-only, no write — so the widget can warn.

(Previously: matched the user/hostname pair through the exact→default→foreign-host ladder.)

#### Scenario: known user resolves

- GIVEN a store with `"ana"` COMP roots `{"macOS": "/Volumes/estudio/2026/CINE/COMP", "Windows": "L:/VFX/2026/CINE/COMP", "Linux": "/mnt/estudio/2026/CINE/COMP"}`
- WHEN the helper reads the profile for `"ana"`
- THEN the returned profile matches those fictitious space roots

#### Scenario: unknown user returns marker without write

- GIVEN a store without `"nuevo"`
- WHEN the helper reads the profile for `"nuevo"`
- THEN an onboarding marker is returned, no exception is raised, and the store file stays unchanged

#### Scenario: legacy entry flags regeneration without write

- GIVEN a store where `"ana"` has `hosts`/`default` and no space keys
- WHEN the helper reads the profile for `"ana"`
- THEN the result reports the legacy regeneration flag and the store file stays unchanged

### Requirement: Unit status for the current-OS base

The helper MUST return `entorno.estado_unidad` data (`{conectado, ruta, detalle}`) for the current platform's SPACE ROOT of the resolved profile (e.g. the COMP root), never hanging on a dead mount (timeout + cache respected).

(Previously: unit status for the current-OS root of a per-platform base dict.)

#### Scenario: connected unit

- GIVEN a current-OS space root `/Volumes/estudio/2026/CINE/COMP` that responds
- WHEN the helper queries unit status
- THEN result has `conectado == True` and `ruta == "/Volumes/estudio/2026/CINE/COMP"`

#### Scenario: disconnected unit

- GIVEN a space root that does not respond (or a hung mount timing out)
- WHEN the helper queries unit status
- THEN result has `conectado == False`, `ruta == None` and a non-empty `detalle`

### Requirement: Change-base prepares merged roots and env delta

`preparar_cambio_base(usuario, ruta_store, so, espacio, nueva_ruta, ruta_plato="")` MUST build a fresh per-space per-platform profile (only the `(espacio, so)` entry replaced; other spaces, other OS and other users preserved — spaces are independent), persist it via the engine's public `guardar_perfiles` (READ-MERGE-WRITE under lock), and return `{"perfil", "env", "unidad"}` — env delta from `armar_estado_env`, unit status of the new root. It MUST NOT apply anything to `os.environ`. No user match MUST raise `ValueError` (never silent onboarding).

(Previously: replaced the matched platform root of a per-platform roots dict, tracking exact/default/foreign-host sources.)

#### Scenario: macOS COMP change persists, others intact

- GIVEN `"ana"` with COMP macOS `/Volumes/estudio/2026/CINE/COMP`, TO_VFX macOS `/Volumes/estudio/2026/CINE/TO_VFX`, and unrelated `"pedro"` in the store
- WHEN `preparar_cambio_base("ana", ruta_store, "macOS", "COMP", "/Volumes/estudio/2026/CINE2/COMP", ruta_plato="/Volumes/estudio/2026/CINE2/COMP/EP_100/x.nk")` runs
- THEN the store keeps TO_VFX and `"pedro"` unchanged, COMP macOS becomes the new root, and the returned env delta has `"PROJECT_ROOT": "/Volumes/estudio/2026/CINE2"`

### Requirement: Onboarding preparation

`preparar_onboarding(usuario, ruta_store, base, so, ruta_plato="")` MUST persist a new-shape profile via the engine's public `asegurar_perfil(usuario, ruta_store, base=base)` (lock-safe, slot-matching base into 3 spaces × 3 OS) and return `{"perfil", "env", "unidad"}` as data, without touching `os.environ`.

(Previously: persisted a user/hostname pair with `hosts`/`default`.)

#### Scenario: onboarding persists the user profile

- GIVEN no profile for `"nuevo"` and form base `/Volumes/estudio/2026/CINE/COMP`
- WHEN `preparar_onboarding("nuevo", ruta_store, base, "macOS")` runs
- THEN the store gains `"nuevo"` with macOS roots for the three spaces plus fictitious Windows/Linux roots, and the returned env delta contains the macOS COMP root

## ADDED Requirements

### Requirement: Profile listing

`listar_perfiles(ruta_store)` MUST return the sorted usernames present in the store, as data. A missing or corrupt store MUST yield `[]` without raising.

#### Scenario: sorted users from the store

- GIVEN a store with `"pedro"` and `"ana"`
- WHEN `listar_perfiles(ruta_store)` runs
- THEN it returns `["ana", "pedro"]`

#### Scenario: missing store is empty

- GIVEN a store path with no file
- WHEN `listar_perfiles(ruta_store)` runs
- THEN it returns `[]` without raising

### Requirement: Profile selection

`preparar_seleccion_perfil(usuario, ruta_store, so, ruta_plato="")` MUST return `{"perfil", "env", "unidad"}` for an existing user: read store → `perfiles.get(usuario)` → env via `injector.armar_estado_env` → `entorno.estado_unidad` on the current-SO space root. A missing user MUST raise `ValueError` (selection is not creation). Selection MUST NOT onboard and MUST NOT write.

#### Scenario: selection returns env data without writing

- GIVEN a store with `"ana"` and a plate under her COMP root
- WHEN `preparar_seleccion_perfil("ana", ruta_store, "macOS", ruta_plato)` runs
- THEN the result contains her profile, an env dict with her space roots and the cut `PROJECT_ROOT`, a unit state, and the store file stays unchanged

#### Scenario: missing user raises without writing

- GIVEN a store without `"nuevo"`
- WHEN `preparar_seleccion_perfil("nuevo", ruta_store, "macOS")` runs
- THEN it raises `ValueError` and the store file stays unchanged