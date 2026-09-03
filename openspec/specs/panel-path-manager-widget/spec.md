# SamanTools Path Manager Widget Specification

## Purpose

NEW thin modal widget (`SamanTools/ui/path_manager_panel.py`): `PathManagerDialog(QDialog)` following the V1 `cambiar_colorspace` pattern (PySide2/PySide6 dual import). It renders helper data (profile, unit status, onboarding form) and applies env changes ONLY through `injector.cachear_env` + `injector.aplicar_entorno`. All logic lives in the pure helper; widget tests run with pytest-qt + fakes (available: pytest-qt 4.5.0), and if Qt is unavailable the widget MAY be 0% covered. Scenario paths MUST be fictitious.

## Requirements

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

### Requirement: Env purity outside aplicar_entorno

All `os.environ` mutation in the module MUST pass through `injector.aplicar_entorno`.

#### Scenario: snapshot unchanged on cancel

- GIVEN a snapshot of `os.environ`
- WHEN the dialog opens, renders, and the user cancels without submitting
- THEN `os.environ` equals the snapshot

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

### Requirement: Extra-spaces section as a separate subtree

The dialog MUST keep the canonical advanced section EXACTLY as before — `campos_avanzados` MUST remain exactly `["COMP", "FROM_VFX", "TO_VFX"]` in that order — and MUST render a SEPARATE extra-spaces subtree below it: one dynamic row per extra space with fields `[name][path][Buscar...][OK][-]`, a per-row OS selector (`macOS|Windows|Linux`), and a `[ + Agregar espacio extra ]` action. The detected OS MUST be shown as an info label (`entorno.detectar_so()`). Each row's unit status MUST come from `entorno.estado_unidad` on the row's root for the row's SELECTED OS; a missing/empty root MUST render the disconnected "Ruta base vacia" state.

#### Scenario: canonical key order stays intact

- GIVEN a dialog built from a profile with canonical spaces and extras
- WHEN the advanced fields render
- THEN `list(dialogo.campos_avanzados) == ["COMP", "FROM_VFX", "TO_VFX"]` and the extra rows live in a separate subtree

#### Scenario: extra rows render from the profile

- GIVEN a profile with extras `"3D"` and `"MATTE_PAINT"` (macOS roots)
- WHEN the dialog builds its extra section
- THEN two rows appear, each showing the extra name and its root for the detected OS, with a unit status from `estado_unidad`

#### Scenario: per-row OS selector switches the slot

- GIVEN an extra `"3D"` with a macOS root but no Windows root
- WHEN the row selector switches to Windows
- THEN the row renders the disconnected state for that slot, and switching back to macOS restores the root and status

### Requirement: Extra-spaces add and remove flows

The `[ + Agregar espacio extra ]` action MUST validate the name through `sanitizar_espacio_extra`, call the helper's add (persisted merge), and re-apply env ONLY through `injector.cachear_env` + `injector.aplicar_entorno` with the returned delta. Each `[-]` action MUST call the helper's remove (engine `eliminar_espacio_store`), leaving canonical rows untouched, and re-apply env the same way. The widget MUST NOT write roots or `os.environ` itself.

#### Scenario: add validates, persists and re-applies env

- GIVEN an extra section with new name input `"preview"` and a root for the detected OS
- WHEN the add action runs
- THEN `sanitizar_espacio_extra` returns `"PREVIEW"`, the helper persists the extra slot, and `cachear_env` + `aplicar_entorno` receive a delta containing `"PYTHON_PREVIEW"`

#### Scenario: remove deletes the extra, canonical untouched

- GIVEN an extra row for `"3D"` beside the canonical rows
- WHEN its `[-]` action runs
- THEN the helper removes `"3D"` via `eliminar_espacio_store`, the canonical rows remain rendered, and env re-applies without `"PYTHON_3D"`

#### Scenario: invalid name is surfaced without write

- GIVEN an extra-section name input of `"hosts"`
- WHEN the add action runs
- THEN the validation error is surfaced, no write occurs, and the canonical rows are unchanged