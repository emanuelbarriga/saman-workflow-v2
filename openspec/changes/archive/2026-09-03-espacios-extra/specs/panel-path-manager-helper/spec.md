# Delta for SamanTools Path Manager Helper

## ADDED Requirements

### Requirement: Extra-space name validation (`sanitizar_espacio_extra`)

`sanitizar_espacio_extra(nombre, perfil)` MUST return the sanitized extra-space name (UPPER, `A-Z0-9` kept, space→`_`, collapse, strip) and the sanitized result MUST be the stored profile key. It MUST raise `ValueError` with a clear message when: the result is empty; the result equals a canonical space case-insensitively (`TO_VFX`/`COMP`/`FROM_VFX` — it would collide with the fixed `PYTHON_*` trio); the literal name is `"hosts"` or `"default"` (legacy keys, hygiene — R2); the literal name is `"PROJECT_ROOT"` (reserved); the result already exists among the profile's other extras (intra-extra duplicate); or the input is path-like or JSON-reserved-looking (contains `/`, `{}`, etc. — R8).

#### Scenario: valid names sanitize

- GIVEN the names `"3D"` and `"matte paint"` and a profile without those extras
- WHEN the sanitizer runs
- THEN it returns `"3D"` and `"MATTE_PAINT"`

#### Scenario: canonical duplicate rejected case-insensitively

- GIVEN the name `"comp"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: legacy reserved names rejected (R2)

- GIVEN the name `"hosts"` or `"default"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: PROJECT_ROOT reserved rejected

- GIVEN the literal name `"PROJECT_ROOT"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: intra-extra duplicate rejected

- GIVEN a profile already holding extra `"3D"` and the incoming name `"3d"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: path-like or JSON-reserved-looking rejected (R8)

- GIVEN the name `"foo/bar"` or `"{}"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

#### Scenario: empty-after-sanitize rejected

- GIVEN the name `"---"`
- WHEN the sanitizer runs
- THEN it raises `ValueError`

### Requirement: Extra roots in `raices_para_so`

`raices_para_so(perfil, so)` MUST return `{espacio: raiz}` for the given `so` including extras: canonical keys first (canonical `_ESPACIOS` order), then extra keys sorted. Identical inputs MUST yield an identical dict.

#### Scenario: canonical first, extras sorted

- GIVEN a profile with canonical roots plus extras `"MATTE_PAINT"` and `"3D"`
- WHEN `raices_para_so(perfil, "macOS")` runs
- THEN the dict starts with the canonical trio in order and lists the extras as `"3D"`, `"MATTE_PAINT"` (sorted)

### Requirement: Add/remove extra-space helpers

The helper MUST expose `agregar_espacio_extra(usuario, ruta_store, so, nombre, nueva_ruta)` — validate the name via `sanitizar_espacio_extra`, merge `{usuario: {<nombre>: {<so>: nueva_ruta}}}` through the engine's `guardar_perfiles` (read-merge-write under lock), preserving all other spaces, extras and users — and `eliminar_espacio_extra(usuario, ruta_store, espacio)` delegating to the engine's `eliminar_espacio_store`. Both MUST return `{"perfil", "env", "unidad"}` as data (the env delta includes `PYTHON_<extra>` once the engine iterates all keys) and MUST NOT touch `os.environ`.

#### Scenario: add persists the extra slot, others intact

- GIVEN `"ana"` with canonical roots and an existing extra `"3D"`
- WHEN `agregar_espacio_extra("ana", ruta_store, "macOS", "matte paint", "/Volumes/estudio/2026/CINE/MATTEPAINT")` runs
- THEN the store gains `MATTE_PAINT` with the macOS root, `"ana"` keeps canonical plus `"3D"`, and the returned env delta contains `"PYTHON_MATTE_PAINT"`

#### Scenario: remove keeps canonical and other extras

- GIVEN `"ana"` with canonical spaces plus extras `"3D"` and `"PREVIEW"`
- WHEN `eliminar_espacio_extra("ana", ruta_store, "3D")` runs
- THEN `"3D"` is gone from the store and canonical plus `"PREVIEW"` remain

### Requirement: Extras-only store data-loss warning (R3)

Canonical presence MUST remain the shape criterion (`detectar_forma_perfil` stays canonical-only): a hand-edited store entry holding extras but NO canonical space key is classified legacy and regenerated wholesale on the next write, losing the extras. The helper MUST document this behavior and MUST NOT produce such a store through its own flows (its add flow always coexists with the fixed canonical section). A read of such an entry MUST report the legacy regeneration flag (read-only) so the UI can warn.

#### Scenario: hand-edited extras-only entry is flagged, not written

- GIVEN a store where `"ana"` has only `{"3D": {...}}` and no canonical key
- WHEN the helper reads the profile for `"ana"`
- THEN it reports the legacy regeneration flag, the store stays unchanged, and any write regenerates the entry wholesale (extras lost) — never emitted by the helper's own add flow

## MODIFIED Requirements

### Requirement: Change-base prepares merged roots and env delta

`preparar_cambio_base(usuario, ruta_store, so, espacio, nueva_ruta, ruta_plato="")` MUST build a fresh per-space per-platform profile (only the `(espacio, so)` entry replaced; other spaces, other OS, other extras and other users preserved — spaces are independent), persist it via the engine's public `guardar_perfiles` (READ-MERGE-WRITE under lock), and return `{"perfil", "env", "unidad"}` — env delta from `armar_estado_env`, unit status of the new root. The `espacio` argument MUST be accepted when it is canonical (`_ESPACIOS`) OR profile-known (an existing key of the user's profile), checked BEFORE the transient TODOS path-like branch; any other name MUST raise `ValueError`. It MUST NOT apply anything to `os.environ`. No user match MUST raise `ValueError` (never silent onboarding).

(Previously: `preparar_cambio_base` accepted only canonical `_ESPACIOS` names, with a path-like transient TODOS branch; any other name fell through to `ValueError`.)

#### Scenario: macOS COMP change persists, others intact

- GIVEN `"ana"` with COMP macOS `/Volumes/estudio/2026/CINE/COMP`, TO_VFX macOS `/Volumes/estudio/2026/CINE/TO_VFX`, and unrelated `"pedro"` in the store
- WHEN `preparar_cambio_base("ana", ruta_store, "macOS", "COMP", "/Volumes/estudio/2026/CINE2/COMP", ruta_plato="/Volumes/estudio/2026/CINE2/COMP/EP_100/x.nk")` runs
- THEN the store keeps TO_VFX and `"pedro"` unchanged, COMP macOS becomes the new root, and the returned env delta has `"PROJECT_ROOT": "/Volumes/estudio/2026/CINE2"`

#### Scenario: profile-known extra accepted before the TODOS branch

- GIVEN `"ana"` whose profile already has extra `"3D"` with a macOS root
- WHEN `preparar_cambio_base("ana", ruta_store, "macOS", "3D", "/Volumes/estudio/2026/CINE/3D/v2")` runs
- THEN only the `("3D", "macOS")` slot is replaced, no exception is raised, and the env delta carries `"PYTHON_3D"` with the new root

#### Scenario: unknown space still raises

- GIVEN a space `"NOPE"` that is neither canonical nor a key of `"ana"`'s profile
- WHEN `preparar_cambio_base("ana", ruta_store, "macOS", "NOPE", "/Volumes/estudio/2026/NOPE")` runs
- THEN it raises `ValueError` and the store stays unchanged