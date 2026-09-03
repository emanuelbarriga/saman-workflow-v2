# SamanTools V2 Bootstrap Contract Specification

## Purpose

NEW artist bootstrap (`bootstrap/menu.py`), installed at `~/.nuke/menu.py`. It MUST preserve the eleven V1 update rules; only structural probes change (V2 marker, V2 exec target, distinct uninstall marker, V2 sync source). The bootstrap MUST stay self-contained and maintenance-only and MUST NOT modify the checkout at startup. V2 replaces V1 with explicit consent; coexistence is temporary and documented. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Fetch-only startup

At startup the bootstrap MUST only `git fetch origin <BRANCH>` and compare local HEAD against `origin/<BRANCH>`. It MUST NOT pull, clone, or reset at startup, and MUST NOT modify the working tree.

#### Scenario: checkout up to date

- GIVEN a checkout whose HEAD equals `origin/main` after fetch
- WHEN the startup state check runs
- THEN it reports "ok" and the working tree hash is unchanged

### Requirement: Consent-based update

An automatic alert MUST appear at most once per 6 hours, guarded by the `LOCK_FILE` mtime, and MUST only offer the update. Applying an update MUST require explicit artist consent (`nuke.ask`).

#### Scenario: update available and deferred

- GIVEN `_estado_update()` reports "disponible" and the 6-hour lock allows a check
- WHEN the alert asks and the artist declines
- THEN no pull runs and work continues on the current version

#### Scenario: alert rate-limited

- GIVEN a `LOCK_FILE` modified less than 6 hours ago
- WHEN the automatic alert runs
- THEN no alert and no update dialog are shown

### Requirement: Apply only via fast-forward pull

Applying an update MUST use `git pull --ff-only`. A failed or non-fast-forward pull MUST be reported as a failure message, never force-resolved.

#### Scenario: non-fast-forward pull rejected

- GIVEN `git pull --ff-only` returns non-zero
- WHEN the update applies
- THEN a failure message is shown and the tree is not force-resolved

### Requirement: Silence without checkout

Without a checkout the bootstrap MUST NOT clone at startup, MUST NOT show errors, and MUST fail silently, leaving only maintenance buttons.

#### Scenario: never installed or uninstalled

- GIVEN no `.git` directory under the tools dir
- WHEN the real-menu load runs
- THEN it returns False with no clone attempt and no dialog

### Requirement: Atomic clone via temp + rename

Installation MUST clone into a temporary directory and then `os.rename` it to the tools dir. A failed clone MUST remove the temp and leave the target untouched; partial checkouts MUST NOT persist.

#### Scenario: failed clone leaves target untouched

- GIVEN no checkout and a clone that fails mid-transfer
- WHEN the install runs
- THEN the temp dir is removed and the tools dir remains absent

### Requirement: Silent reset repair

A git checkout missing the marker file MUST be repaired by `git reset --hard origin/<BRANCH>` after fetch, silently, before the menu loads.

#### Scenario: broken checkout repaired

- GIVEN a git checkout without the V2 marker file
- WHEN the load path runs
- THEN `reset --hard` runs, the marker appears, and the real menu loads

### Requirement: Content-hash auto-sync

Each startup the installed bootstrap MUST be compared by MD5 against `<checkout>/bootstrap/menu.py`; on difference it MUST copy the repo version over the installed file.

#### Scenario: repo bootstrap differs from installed

- GIVEN the installed bootstrap's MD5 differs from `<checkout>/bootstrap/menu.py`
- WHEN startup auto-sync runs
- THEN the repo version is copied over the installed file

### Requirement: Maintenance menu only when checkout exists

The SamanTools menu MUST be created only when a checkout exists; the uninstalled state MUST leave the menu completely clean.

#### Scenario: uninstalled state leaves menu clean

- GIVEN no checkout
- WHEN the maintenance-menu wiring runs
- THEN no SamanTools menu item is created

### Requirement: Update button reinstalls

The manual update action with no checkout MUST ask consent and then clone; with a checkout it MUST report state and, on consent, pull.

#### Scenario: manual update reinstalls when checkout missing

- GIVEN no checkout and the artist consents to install
- WHEN the manual update action runs
- THEN a clean clone appears in the tools dir

### Requirement: Self-contained bootstrap

The bootstrap MUST import only stdlib and `nuke`, never repo code, so it works even when the checkout is broken.

#### Scenario: broken checkout still offers maintenance

- GIVEN a checkout whose marker file is missing but `.git` exists
- WHEN `instalar()` runs
- THEN no repo code is imported and the maintenance buttons still appear

### Requirement: Definitive uninstall

Uninstall, after consent, MUST delete the checkout, any `*.desinstalado_*` backups, and the installed bootstrap when it carries the V2 marker. No backups accumulate.

#### Scenario: uninstall removes backups

- GIVEN consent and a tools dir with `*.desinstalado_*` leftovers and a bootstrap carrying the V2 marker
- WHEN uninstall runs
- THEN checkout, backups and the bootstrap are deleted and nothing accumulates

### Requirement: V2 structural probes

`_checkout_completo` MUST probe `SamanTools/core/rutas_engine.py`; `_cargar_menu_real` MUST exec `<checkout>/SamanTools/ui/menu.py`; auto-sync MUST read `<checkout>/bootstrap/menu.py`.

#### Scenario: full V2 checkout loads the target

- GIVEN a complete V2 checkout with `SamanTools/core/rutas_engine.py` and `SamanTools/ui/menu.py`
- WHEN the real-menu load runs
- THEN `SamanTools/ui/menu.py` is exec'd and the call returns True

### Requirement: Distinct V2 uninstall marker

The V2 bootstrap MUST carry the marker string "SamanTools V2 bootstrap" and MUST NOT contain the V1 marker text "bootstrap de artista", so the V1 uninstaller can never delete it.

#### Scenario: V1 uninstaller ignores V2 bootstrap

- GIVEN `~/.nuke/menu.py` containing the V2 marker but not the V1 marker
- WHEN the V1 uninstaller checks the marker
- THEN the file is left untouched