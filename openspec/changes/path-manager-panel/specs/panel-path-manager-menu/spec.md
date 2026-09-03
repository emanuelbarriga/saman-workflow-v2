# SamanTools Path Manager Menu Registration Specification

## Purpose

NEW registration slice on `SamanTools/ui/menu.py`: a "Path Manager" menu item with shortcut Ctrl+Alt+R that opens the panel dialog on demand. It EXTENDS the load-ui-menu contract: menu.py keeps NO PySide import (deferred, indirect) and creates no panel at install time. The existing `test_menu` source guards (`test_sin_pyside_ni_creacion_de_paneles`, `test_importa_nuke_a_nivel_de_modulo`) MUST keep passing. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Path Manager item registration

`instalar()` MUST register a "Path Manager" item on the SamanTools menu whose command invokes the panel entry point, using the shortcut from a single module constant. Registration MUST be idempotent (findItem guard, same pattern as existing items) and MUST NOT open the dialog at install.

#### Scenario: item present, not duplicated

- GIVEN a Nuke GUI session with the nuke menu fake
- WHEN `instalar()` runs twice
- THEN the SamanTools menu has exactly one "Path Manager" item with shortcut "Ctrl+Alt+R" and no dialog was opened by the install itself

### Requirement: Deferred, indirect PySide access

menu.py MUST NOT contain a literal `import PySide` or `from PySide` statement at ANY indentation (the existing test_menu regex guard also matches indented imports), and MUST NOT create panels. The command callback MUST load the dialog lazily (indirect import machinery or importing the panel module only at click time), so PySide enters the process only when the user invokes Path Manager.

#### Scenario: exec without invocation does not import PySide

- GIVEN sys.modules keys recorded before execution and no invocation of the command
- WHEN menu.py executes (bootstrap-style exec)
- THEN PySide2/PySide6 are not newly present in sys.modules and the menu still builds

#### Scenario: source guard keeps passing

- GIVEN the menu.py source as registered in the repo
- WHEN the existing test regex `^\s*(?:import\s+PySide|from\s+PySide)` scans it
- THEN no match is found and `instalar()` still builds the menu

#### Scenario: PySide loads only on invocation

- GIVEN a session without PySide imported yet
- WHEN the "Path Manager" command is invoked
- THEN the dialog module (and PySide with it) is imported at that moment and the dialog opens

### Requirement: Shortcut collision handling

The shortcut MUST come from a single module constant; if another plugin already owns it at registration time, the item MUST degrade to the documented fallback key instead of failing the menu build.

#### Scenario: collision degrades, menu still builds

- GIVEN another plugin already registered "Ctrl+Alt+R" in the session
- WHEN `instalar()` runs
- THEN the Path Manager item is registered with the documented fallback shortcut and the SamanTools menu still exists