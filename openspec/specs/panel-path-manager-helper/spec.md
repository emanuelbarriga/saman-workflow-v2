# SamanTools Path Manager Helper Specification

## Purpose

NEW pure helper (`SamanTools/ui/path_manager.py`): reads the active profile, reports unit status, detects unknown users (returns an onboarding marker) and prepares change-base/onboarding writes. PURE: no nuke, no PySide, no `os.environ` reads or writes — it returns data for the thin widget to render and apply. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Pure, deterministic data layer

The helper MUST NOT import nuke or PySide, MUST NOT read or mutate `os.environ`, and MUST take identity (`user`, `hostname`) and store path as injectable parameters. Identical inputs MUST yield identical outputs.

#### Scenario: same inputs, same outputs, no env access

- GIVEN `("ana", "ws1")`, an injected store path, and a snapshot of `os.environ`
- WHEN the profile read runs twice
- THEN both results are identical and `os.environ` is unchanged

### Requirement: Active profile read with onboarding marker

For a known pair, the helper MUST return the resolved profile (user/hostname + per-platform roots). For an unknown pair it MUST return an onboarding marker, never raise, and never persist during detection, so the widget can show the base form before any write.

#### Scenario: known user resolves

- GIVEN a store with `"ana"/"ws1"` roots `{"macOS": "/Volumes/estudio/2026", "Windows": "L:/VFX/2026", "Linux": "/mnt/estudio/2026"}`
- WHEN the helper reads the profile for `("ana", "ws1")`
- THEN the returned profile matches those three fictitious roots

#### Scenario: unknown user returns marker without write

- GIVEN a store without `"nuevo"/"pc9"`
- WHEN the helper reads the profile for `("nuevo", "pc9")`
- THEN an onboarding marker is returned, no exception is raised, and the store file stays unchanged

### Requirement: Unit status for the current-OS base

The helper MUST return `entorno.estado_unidad` data (`{conectado, ruta, detalle}`) for the current platform's base, never hanging on a dead mount (timeout + cache respected).

#### Scenario: connected unit

- GIVEN a current-OS base `/Volumes/estudio/2026` that responds
- WHEN the helper queries unit status
- THEN result has `conectado == True` and `ruta == "/Volumes/estudio/2026"`

#### Scenario: disconnected unit

- GIVEN a base that does not respond (or a hung mount timing out)
- WHEN the helper queries unit status
- THEN result has `conectado == False`, `ruta == None` and a non-empty `detalle`

### Requirement: Change-base prepares merged roots and env delta

`preparar_cambio_base(perfil, so, nueva_base)` MUST build a fresh per-platform roots dict (edited platform replaced, other platforms preserved), persist it via the engine's public `guardar_perfiles` (READ-MERGE-WRITE under lock), and return the updated profile plus the env delta from `armar_estado_env` as DATA. It MUST NOT apply anything to `os.environ`.

#### Scenario: macOS base change persists, others intact

- GIVEN `("ana", "ws1")` with macOS `/Volumes/estudio/2026`, Windows `L:/VFX/2026`, Linux `/mnt/estudio/2026`, and unrelated `"pedro"/"ws2"` in the store
- WHEN `preparar_cambio_base(perfil, "macOS", "/Volumes/estudio/2027")` runs
- THEN the store now has macOS `/Volumes/estudio/2027` while Windows/Linux roots and the `"pedro"` profile remain unchanged, and the returned env delta has `"PROJECT_ROOT": "/Volumes/estudio/2027"`

### Requirement: Onboarding preparation

`preparar_onboarding(user, hostname, base)` MUST persist a new profile via the engine's public `asegurar_perfil` (lock-safe, slot-matching base) and return the resulting profile plus env delta as data, without touching `os.environ`.

#### Scenario: onboarding persists with user base

- GIVEN no profile for `("nuevo", "pc9")` and form base `/Volumes/estudio/2026`
- WHEN `preparar_onboarding("nuevo", "pc9", "/Volumes/estudio/2026")` runs
- THEN the store gains `"nuevo"/"pc9"` with macOS `/Volumes/estudio/2026` plus fictitious Windows/Linux roots, and the returned env delta contains that macOS root