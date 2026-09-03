# Delta for panel-path-manager-widget

## MODIFIED Requirements

### Requirement: Thin dialog bound to the helper

`PathManagerDialog` MUST import PySide via the V1 dual-import pattern (PySide2 first, PySide6 fallback) and MUST NOT compute profile/state itself: it MUST consume the pure helper's data (profile, unit status, profile list). It MUST NOT write to `os.environ` except through `injector.aplicar_entorno`. User identity is `usuario` only (no hostname).

(Previously: identity was the `(usuario, hostname)` pair.)

#### Scenario: profile and status rendered from helper data

- GIVEN helper data with COMP roots `{"macOS": "/Volumes/estudio/2026/CINE/COMP", "Windows": "L:/VFX/2026/CINE/COMP", "Linux": "/mnt/estudio/2026/CINE/COMP"}` and unit state `{"conectado": True, "ruta": "/Volumes/estudio/2026/CINE/COMP", "detalle": "Conectado."}`
- WHEN the dialog builds its UI (pytest-qt)
- THEN the labels show the fictitious macOS COMP root and the connected status, and `os.environ` is unchanged

### Requirement: Onboarding flow

Given an onboarding marker, the dialog MUST show a base form; on submit it MUST call the helper's onboarding preparation (engine `asegurar_perfil` under the hood, lock-safe) with the form base, then `cachear_env` + `aplicar_entorno` with the returned env delta.

(Previously: onboarding for a `(usuario, hostname)` pair.)

#### Scenario: new user submits base and env propagates

- GIVEN the dialog shows the onboarding form for `"nuevo"` and the user enters base `/Volumes/estudio/2026/CINE/COMP`
- WHEN the form submits
- THEN `asegurar_perfil("nuevo", <store>, base=...)` runs once, `injector.cachear_env` and `injector.aplicar_entorno` receive the env delta, and `os.environ["PROJECT_ROOT"]` equals the fallback/cut root

### Requirement: Change-base flow

The dialog MUST send the new SPACE root to the helper's change-base (persisted merged profile), then re-apply env via `cachear_env` + `aplicar_entorno` with the returned delta. The widget MUST NOT write roots or env itself.

(Previously: changed the single matched base for the user/hostname pair.)

#### Scenario: change base re-applies env

- GIVEN a known profile and a new macOS COMP root `/Volumes/estudio/2026/CINE2/COMP` entered in the dialog
- WHEN the user confirms the change
- THEN the helper's change-base persists the merged profile and, after applying, `os.environ["PROJECT_ROOT"]` equals the cut root, with no direct env assignment in the widget's own code

### Requirement: Modal entry point

The module MUST expose an entry function (e.g. `abrir_dialogo()`) that shows the dialog modally as the menu command's callback target, MUST take `usuario` (no hostname), and MUST degrade gracefully (never raise upward) when no GUI session or helper data exists. On open it MUST refresh the profile list from the store.

(Previously: took `(usuario, hostname)` and had no profile-list refresh.)

#### Scenario: no GUI degrades silently

- GIVEN a headless/console context where `nuke.GUI` is false or PySide fails to load
- WHEN the entry function runs
- THEN no exception propagates and no window is created

#### Scenario: open refreshes the profile list

- GIVEN a store that gained `"pedro"` after the previous dialog open
- WHEN `abrir_dialogo` opens the dialog
- THEN the combo lists `"pedro"`

## ADDED Requirements

### Requirement: Profile selector combo

The dialog MUST show a `QComboBox` listing the store's usernames (from `path_manager.listar_perfiles`), refreshed on every open. Selecting a user MUST apply that profile immediately: `preparar_seleccion_perfil` → `cachear_env` + `aplicar_entorno` → refresh Read nodes so `[getenv PROJECT_ROOT]` paths re-evaluate. A failed selection (stale-store race → `ValueError`) MUST be surfaced without applying a partial env. An empty store MUST yield an empty combo plus the onboarding form (existing flow). A legacy-regeneration flag from the helper MUST trigger the regeneration warning message.

#### Scenario: selecting a profile applies env and refreshes Reads

- GIVEN the combo lists `"ana"` and `"pedro"` and the user selects `"ana"`
- WHEN the selection handler runs
- THEN `preparar_seleccion_perfil("ana", ...)` returns env data, `cachear_env` + `aplicar_entorno` apply it, and Read nodes refresh

#### Scenario: stale selection is surfaced without partial env

- GIVEN the combo lists `"ana"` but the store no longer contains her
- WHEN the selection handler runs
- THEN the `ValueError` is surfaced via the message callback and no partial env reaches `os.environ`

#### Scenario: legacy store warns before onboarding

- GIVEN helper data flagging a legacy-shaped entry
- WHEN the dialog opens
- THEN it shows the regeneration warning message and the onboarding flow proceeds with the new shape