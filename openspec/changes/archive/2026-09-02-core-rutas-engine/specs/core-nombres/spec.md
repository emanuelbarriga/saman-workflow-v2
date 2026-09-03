# Core Nombres Specification

## Purpose

Parse VFX plate/shot filenames into structured data, pure (no nuke/PySide), extracted by copy from V1 `SamanTools/nombres.py`. Canonical convention: `{PROYECTO}_{EP}_{escena}_{shot}_V{nn}.ext`, with `plano = "escena_shot"`. All scenario paths are fictitious (`/Volumes/estudio/2026`, `L:/VFX/2026`) with fictitious project tokens (`CINE`); real studio tokens MUST NOT appear.

## Requirements

### Requirement: Canonical plate parsing

`parsear_plato(ruta)` MUST return a dict with `proyecto`, `capitulo`, `escena`, `shot`, `plano`, `version`, `archivo`, `canonico`, `malformado`. It MUST return `None` for empty/`None` input, when the basename has fewer than 4 tokens, or when no numeric chapter follows the prefix. It MUST NEVER raise.

#### Scenario: canonical macOS path

- GIVEN ruta `"/Volumes/estudio/2026/CINE/TO_VFX/EP_107/20260826/CINE_107_008_00100_V01.mov"` and `entorno.detectar_so` stubbed to `"macOS"`
- WHEN `parsear_plato(ruta)` runs
- THEN `proyecto=="CINE"`, `capitulo==107`, `escena=="008"`, `shot=="00100"`, `plano=="008_00100"`, `version=="V01"`, `malformado is False` and `canonico == archivo`

#### Scenario: folder chapter is authoritative

- GIVEN ruta containing `EP_107/` but filename token `999`
- WHEN `parsear_plato(ruta)` runs
- THEN `capitulo == 107` and `canonico == "CINE_107_008_00100_V01.mov"`

### Requirement: Version normalization

A token matching `^[vV]\d+$` MUST be uppercased in `version`. When the version token is not the last token, `malformado` MUST be `True` and `canonico` MUST place the version at the end.

#### Scenario: malformed version moved to end

- GIVEN basename `"CINE_108_012_V01_0100.mov"`
- WHEN `parsear_plato` runs
- THEN `plano=="012_0100"`, `version=="V01"`, `malformado is True`, `canonico=="CINE_108_012_0100_V01.mov"`

#### Scenario: lowercase version uppercased

- GIVEN basename `"CINE_107_008_00100_v01.mov"`
- WHEN `parsear_plato` runs
- THEN `version == "V01"` and `canonico == "CINE_107_008_00100_V01.mov"`

### Requirement: Company suffix as metadata

Tokens after the `comp` marker MUST NOT enter `plano` but MUST be preserved in `canonico` at their original position.

#### Scenario: comp suffix does not contaminate the plate

- GIVEN basename `"CINE_100_000_00000_comp_SAMAN_V01.nk"`
- WHEN `parsear_plato` runs
- THEN `plano=="000_00000"` and `canonico == "CINE_100_000_00000_comp_SAMAN_V01.nk"`

#### Scenario: any owner token after comp is metadata

- GIVEN basename `"CINE_107_008_00100_comp_OTRA_V02.nk"`
- WHEN `parsear_plato` runs
- THEN `plano == "008_00100"` and canonico preserves `comp_OTRA` untouched

### Requirement: Version-less references and basenames

A reference without version token (e.g. PNG) MUST yield `version is None` and `malformado is False`. A bare basename (no directory) MUST still parse content, with `proyecto is None` unless a base matches.

#### Scenario: PNG reference without version

- GIVEN basename `"CINE_107_012_01500.png"`
- WHEN `parsear_plato` runs
- THEN `version is None`, `malformado is False`, `plano=="012_01500"`, `canonico == "CINE_107_012_01500.png"`

#### Scenario: bare basename parses

- GIVEN basename `"CINE_109_020_00300_V02.mov"`
- WHEN `parsear_plato` runs
- THEN `proyecto is None`, `capitulo==109`, `plano=="020_00300"`, `version=="V02"`

### Requirement: Platform-neutral path handling

Windows backslashes MUST be normalized before parsing; the result MUST NOT depend on the host OS (path-level determinism).

#### Scenario: Windows backslash path

- GIVEN ruta `r"L:\VFX\2026\CINE\TO_VFX\EP_110\20260901\CINE_110_055_01200_V03.mov"`
- WHEN `parsear_plato(ruta)` runs
- THEN `capitulo==110`, `plano=="055_01200"`, `version=="V03"`, `malformado is False`

### Requirement: Invalid inputs never raise

`parsear_plato` MUST return `None` for `""`, `None` and non-plate basenames such as `"foo.txt"`, without raising.

#### Scenario: invalid inputs

- GIVEN inputs `""`, `None` and `"foo.txt"`
- WHEN `parsear_plato` runs on each
- THEN each returns `None`