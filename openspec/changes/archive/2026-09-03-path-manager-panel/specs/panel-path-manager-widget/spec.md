# SamanTools Path Manager Widget Specification

## Purpose

NEW thin modal widget (`SamanTools/ui/path_manager_panel.py`): `PathManagerDialog(QDialog)` following the V1 `cambiar_colorspace` pattern (PySide2/PySide6 dual import). It renders helper data (profile, unit status, onboarding form) and applies env changes ONLY through `injector.cachear_env` + `injector.aplicar_entorno`. All logic lives in the pure helper; widget tests run with pytest-qt + fakes (available: pytest-qt 4.5.0), and if Qt is unavailable the widget MAY be 0% covered. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Thin dialog bound to the helper

`PathManagerDialog` MUST import PySide via the V1 dual-import pattern (PySide2 first, PySide6 fallback) and MUST NOT compute profile/state itself: it MUST consume the pure helper's data. It MUST NOT write to `os.environ` except through `injector.aplicar_entorno`.

#### Scenario: profile and status rendered from helper data

- GIVEN helper data with profile roots `{"macOS": "/Volumes/estudio/2026", "Windows": "L:/VFX/2026", "Linux": "/mnt/estudio/2026"}` and unit state `{"conectado": True, "ruta": "/Volumes/estudio/2026", "detalle": "Conectado."}`
- WHEN the dialog builds its UI (pytest-qt)
- THEN the labels show the fictitious macOS root and the connected status, and `os.environ` is unchanged

### Requirement: Onboarding flow

Given an onboarding marker, the dialog MUST show a base form; on submit it MUST call the helper's onboarding preparation (engine `asegurar_perfil` under the hood, lock-safe) with the form base, then `cachear_env` + `aplicar_entorno` with the returned env delta.

#### Scenario: new user submits base and env propagates

- GIVEN the dialog shows the onboarding form for `("nuevo", "pc9")` and the user enters base `/Volumes/estudio/2026`
- WHEN the form submits
- THEN `asegurar_perfil("nuevo", "pc9", <store>, "/Volumes/estudio/2026")` runs once, `injector.cachear_env` and `injector.aplicar_entorno` receive the env delta, and `os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"`

### Requirement: Change-base flow

The dialog MUST send the new base to the helper's change-base (persisted merged roots), then re-apply env via `cachear_env` + `aplicar_entorno` with the returned delta. The widget MUST NOT write roots or env itself.

#### Scenario: change base re-applies env

- GIVEN a known profile and a new macOS base `/Volumes/estudio/2027` entered in the dialog
- WHEN the user confirms the change
- THEN the helper's change-base persists the merged roots and, after applying, `os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2027"` with no direct env assignment in the widget's own code

### Requirement: Env purity outside aplicar_entorno

All `os.environ` mutation in the module MUST pass through `injector.aplicar_entorno`.

#### Scenario: snapshot unchanged on cancel

- GIVEN a snapshot of `os.environ`
- WHEN the dialog opens, renders, and the user cancels without submitting
- THEN `os.environ` equals the snapshot

### Requirement: Modal entry point

The module MUST expose an entry function (e.g. `abrir_dialogo()`) that shows the dialog modally as the menu command's callback target, and MUST degrade gracefully (never raise upward) when no GUI session or helper data exists.

#### Scenario: no GUI degrades silently

- GIVEN a headless/console context where `nuke.GUI` is false or PySide fails to load
- WHEN the entry function runs
- THEN no exception propagates and no window is created