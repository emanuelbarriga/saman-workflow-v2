# SamanTools UI Menu Specification

## Purpose

NEW minimal `SamanTools/ui/menu.py`: the bootstrap's exec target. It MUST register the injector callbacks exactly once, import the injector and (import-safe) the shim, and build the SamanTools menu. It MUST NOT create panels. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Bootstrap exec target

`SamanTools/ui/menu.py` MUST be the file exec'd by the V2 bootstrap's `_cargar_menu_real` and MUST complete all setup (callbacks + menu) when executed through the bootstrap's namespace.

#### Scenario: bootstrap exec path

- GIVEN a complete V2 checkout whose bootstrap probes `SamanTools/core/rutas_engine.py`
- WHEN the bootstrap execs `SamanTools/ui/menu.py`
- THEN callbacks are registered, the SamanTools menu exists, and the load returns True

### Requirement: Idempotent callback registration

Executing the module twice MUST NOT register `addOnScriptLoad` or `addOnScriptSave` twice.

#### Scenario: re-exec does not duplicate

- GIVEN the module already executed once
- WHEN it executes again
- THEN registration counts stay at one per callback

### Requirement: Minimal menu without panels

The module MUST create a "SamanTools" menu, MAY attach the bootstrap-inherited maintenance commands (update/uninstall), and MUST NOT create any panel. It MUST NOT import PySide.

#### Scenario: menu built, no panels

- GIVEN a Nuke GUI session
- WHEN the module runs
- THEN a SamanTools menu item exists and no panel windows are created

### Requirement: Import-safe shim access

The module MUST import the injector normally and MUST import the shim tolerantly (lazy or guarded), so a shim import failure never breaks callbacks or the menu.

#### Scenario: shim import failure tolerated

- GIVEN the shim raising during import
- WHEN the module runs
- THEN callbacks still register and the menu still builds