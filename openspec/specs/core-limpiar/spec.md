# Core Limpiar Specification

## Purpose

Sanitize volatile machine-specific knobs out of serialized `.nk`/`.gizmo` text with corruption-proof writes. Pure stdlib (os, re), no nuke/PySide; extracted by copy from V1 `SamanTools/limpiar.py`. V2 replaces the real `Review.gizmo` regression fixture with a synthetic inline sample so no studio gizmo ships in the public repo.

## Requirements

### Requirement: Volatile knob text removal

`sanitizar_texto_nk(contenido)` MUST remove every full line (including the optional newline, `re.MULTILINE`) matching `mov64_prraw_plugin`, `render_settings_schema` or `monitorOutNDISenderName`, and MUST leave legitimate lines untouched. It MUST be idempotent.

#### Scenario: the three knobs are stripped

- GIVEN text with `mov64_prraw_plugin Standard`, `render_settings_schema false` and `monitorOutNDISenderName "NukeX - ..."` inside Read/Viewer blocks
- WHEN `sanitizar_texto_nk` runs
- THEN none of the three knob names remain and `file "clip.mov"`, `name Read1`, `xpos 100` are preserved

#### Scenario: legit knobs untouched

- GIVEN text `Read {\n  colorspace DaVinci Intermediate WideGamut\n  name Read1\n}\n`
- WHEN `sanitizar_texto_nk` runs
- THEN the result equals the input

#### Scenario: idempotent

- GIVEN any text with volatile knobs
- WHEN sanitization is applied twice
- THEN the second pass returns the output of the first pass unchanged

### Requirement: Safe atomic file sanitization

`sanitizar_archivo(ruta)` MUST return `1` when content changed and `0` when unchanged (in which case it MUST NOT rewrite or create temporaries). It MUST preserve a UTF-8 BOM, CRLF line endings, and non-UTF-8 bytes recoded 1:1 via latin-1. The rewrite MUST be atomic: temp file in the same directory plus `os.replace`, keeping the original intact on any failure. `OSError` (e.g. missing file) MUST propagate.

#### Scenario: CRLF and BOM preserved

- GIVEN a file with `\r\n` endings and a UTF-8 BOM containing a volatile knob
- WHEN `sanitizar_archivo` runs
- THEN it returns `1`, the BOM bytes and `\r\n` endings survive, and the knob line is gone

#### Scenario: non-UTF-8 bytes survive

- GIVEN a latin-1 file containing byte `0xE9` and a volatile knob
- WHEN `sanitizar_archivo` runs
- THEN byte `0xE9` remains and the knob line is gone

#### Scenario: unchanged file is untouched

- GIVEN a clean file
- WHEN `sanitizar_archivo` runs
- THEN it returns `0` and file bytes are unchanged

#### Scenario: missing file raises

- GIVEN a path that does not exist
- WHEN `sanitizar_archivo` runs
- THEN `FileNotFoundError` propagates

### Requirement: Recursive folder sanitization

`sanitizar_carpeta(ruta, extensiones=(".nk", ".gizmo"))` MUST walk recursively without following directory symlinks, process only files whose extension (case-insensitive) is listed, and return `{"limpiados": int, "sin_cambios": int, "errores": [(ruta, str)]}`. It MUST NEVER raise: each file runs in its own try/except, collecting `OSError` into `errores`.

#### Scenario: mixed tree summary

- GIVEN a tree with one dirty `.nk`, one clean `.gizmo` and one dirty `.nk` in a subfolder
- WHEN `sanitizar_carpeta` runs
- THEN `limpiados == 2`, `sin_cambios == 1`, `errores == []` and the dirty files are clean on disk

#### Scenario: only listed extensions count

- GIVEN a `.py` file containing volatile-knob text
- WHEN `sanitizar_carpeta` runs
- THEN the summary is `{"limpiados": 0, "sin_cambios": 0, "errores": []}` and the `.py` bytes are untouched

### Requirement: Inline regression sample

The V2 test module MUST ship a synthetic inline sample exercising all three volatile knobs plus legitimate knobs, replacing the V1 `Review.gizmo` fixture. The sample MUST be fully fictitious and MUST NOT reference studio paths or gizmos.

#### Scenario: synthetic sample regression

- GIVEN the inline `.nk`-style sample with all three volatile knobs and legit knobs
- WHEN `sanitizar_texto_nk(sample)` runs
- THEN volatile knobs are absent and every legit knob/line from the sample is still present