# Core Purity Guard Specification

## Purpose

Enforce the core purity boundary by automated test: `SamanTools/core/` MUST NEVER import nuke/PySide, and the public repo MUST NOT leak real studio tokens or paths. Implemented as `tests/test_no_import_nuke_en_core.py` running under the minimal V2 `tests/conftest.py` (no nuke stub). The guard itself MUST be testable: its matcher MUST accept synthetic samples/paths so the test can prove both failure and pass cases without polluting real modules.

## Requirements

### Requirement: Forbidden import detection

The guard MUST scan every `.py` file under `SamanTools/core/` and fail when any line is an import statement of `nuke`, `nukescripts`, `PySide2` or `PySide6`. Static detection MUST match `import nuke`, `import nukescripts`, `from PySide6.QtWidgets import ...` etc., anchored to import lines only (`^\s*import ...` / `^\s*from ...`) so comments and string literals mentioning these names are NOT flagged. **Dynamic import detection:** the guard MUST ALSO fail when a line contains a dynamic import call whose target is one of the forbidden modules — `__import__('nuke')`, `importlib.import_module('nuke')`, `importlib.import_module("PySide6")`, `__import__("nukescripts")` (double- or single-quoted). Dynamic imports of modules that are NOT forbidden (e.g. `importlib.import_module('os')`) MUST NOT fail. A single tokenizer function MUST serve both matchers so the guard's own tests can drive it with synthetic samples.

#### Scenario: guard fails on real import

- GIVEN a synthetic sample containing a line `import nuke`
- WHEN the guard matcher inspects the sample
- THEN it reports a failure for that file

#### Scenario: dynamic import of forbidden module fails

- GIVEN a synthetic sample containing `importlib.import_module("nuke")` inside a function body
- WHEN the guard matcher inspects the sample
- THEN it reports a failure for that file

#### Scenario: dynamic import of stdlib module passes

- GIVEN a synthetic sample containing `importlib.import_module("os")`
- WHEN the guard matcher inspects the sample
- THEN it reports no failure

#### Scenario: guard fails on real import

- GIVEN a synthetic sample containing a line `import nuke`
- WHEN the guard matcher inspects the sample
- THEN it reports a failure for that file

#### Scenario: comment mentioning nuke passes

- GIVEN a synthetic sample whose only mention is a comment `# import nuke dentro del caller`
- WHEN the guard matcher inspects the sample
- THEN it reports no failure

#### Scenario: PySide import detected

- GIVEN a synthetic sample containing `from PySide6.QtWidgets import QWidget`
- WHEN the guard matcher inspects the sample
- THEN it reports a failure

#### Scenario: `__import__` of forbidden module detected

- GIVEN a synthetic sample containing a line `mod = __import__('nuke')`
- WHEN the guard matcher inspects the sample
- THEN it reports a failure

### Requirement: Minimal non-Nuke test harness

The suite MUST run with a minimal `tests/conftest.py` that provides NO nuke stub. All ported pure tests and engine tests MUST pass via `python3 -m pytest` on a machine without Nuke. The V1 nuke-stub integration block of `test_entorno.py` (lines 304–533) MUST NOT be ported (declared deferred); ported tests are the pure subset (lines 37–267).

#### Scenario: full suite green without Nuke

- GIVEN a machine with no `nuke` module installed
- WHEN `python3 -m pytest` runs from the repo root
- THEN every test passes, including the guard

### Requirement: Real token and path hygiene

The guard MUST fail when banned real studio tokens (`wupm`, `LucidLink`, `HTLR`, `PCF`) appear in scanned source surfaces: `SamanTools/` and `tests/`. The guard test file itself is exempt (it must name the tokens to define its regex). Ported fixtures MUST use fictitious equivalents (`/Volumes/estudio/2026`, `L:/VFX/2026`, `/mnt/estudio/2026`, `CINE`).

#### Scenario: banned token rejected

- GIVEN a core source file containing the literal `"/Volumes/wupm/2026"`
- WHEN the hygiene check inspects it
- THEN the audit reports a failure

#### Scenario: neutralized sources pass

- GIVEN core sources and fixtures using only fictitious paths and tokens (`estudio`, `CINE`)
- WHEN the hygiene check runs
- THEN the audit reports no failures