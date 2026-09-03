# Core Entorno Specification

## Purpose

Detect the host OS, verify network-unit mount state, and enumerate fictitious per-OS base roots. Pure stdlib (no nuke/PySide), extracted by copy from V1 `SamanTools/entorno.py`; real paths/tokens (`wupm`, `LucidLink`, `HTLR`, `PCF`) neutralized to fictitious equivalents. Real studio paths MUST NOT appear in module or tests.

## Requirements

### Requirement: OS detection and SO tables

`detectar_so()` MUST return `"macOS"`, `"Windows"` or `"Linux"` (Darwin/Windows/Linux). `sufijo_so(so)` MUST map macOS→`MAC`, Windows→`WINDOWS`, Linux→`ARTIST`, unknown→`ARTIST`. `usuario_activo(so)` MUST map macOS→`MacServer`, Windows→`Windows`, Linux→`Artist`, unknown→`Artist`.

#### Scenario: Darwin maps to macOS

- GIVEN `platform.system()` returns `"Darwin"`
- WHEN `detectar_so()` runs
- THEN the result is `"macOS"`

#### Scenario: SO tables for the three platforms

- GIVEN `so` is `"macOS"`, `"Windows"` or `"Linux"`
- WHEN `sufijo_so(so)` and `usuario_activo(so)` run
- THEN they return `(MAC, MacServer)`, `(WINDOWS, Windows)` or `(ARTIST, Artist)`

### Requirement: Neutralized base roots per SO

`rutas_base(so, extra=None)` MUST return fictitious candidates in priority order: macOS → `/Volumes/estudio/2026`, then `/Volumes/estudioCloud/2026`; Windows → `L:/VFX/2026`, then a drive-letter scan A–Z minus L for existing `<letra>:/VFX/2026`; Linux → `/mnt/estudio/2026`; unknown SO → `[]`. `extra` (str or list) MUST be prepended without duplicating defaults. No literal containing `wupm`, `LucidLink`, `HTLR` or `PCF` MAY appear.

#### Scenario: macOS order

- GIVEN `so` is `"macOS"`
- WHEN `rutas_base("macOS")` runs
- THEN it starts with `"/Volumes/estudio/2026"` and contains `"/Volumes/estudioCloud/2026"`

#### Scenario: Windows scan without duplication

- GIVEN `os.path.isdir` stubbed to accept only `"Z:/VFX/2026"` and `"T:/VFX/2026"`
- WHEN `rutas_base("Windows")` runs
- THEN it starts with `"L:/VFX/2026"`, contains both scanned letters, and `"L:/VFX/2026"` appears once

#### Scenario: user extra wins

- GIVEN `extra="/miespacio/prueba"`
- WHEN `rutas_base("macOS", extra)` runs
- THEN result starts with `"/miespacio/prueba"`

### Requirement: Unit state with timeout and cache

`estado_unidad(ruta_base)` MUST return `{"conectado": bool, "ruta": str|None, "detalle": str}`. Empty/`None`/whitespace base MUST report `conectado=False`. A dead SMB mount (`subprocess.TimeoutExpired`) MUST report disconnected with `detalle` mentioning the timeout and MUST NOT hang. Results MUST be cached ~10 s at module level.

#### Scenario: existing directory connects

- GIVEN an existing `tmp_path`
- WHEN `estado_unidad(str(tmp_path))` runs
- THEN `conectado is True` and `ruta` equals the path

#### Scenario: hung mount is disconnected

- GIVEN `subprocess.run` raises `TimeoutExpired`
- WHEN `estado_unidad("/Volumes/estudio/2026")` runs
- THEN `conectado is False`, `ruta is None` and `detalle` contains `"timeout"`

#### Scenario: cache avoids rechecks

- GIVEN a first `estado_unidad` call on a `tmp_path`
- WHEN the same path is queried again
- THEN the verifier runs exactly once

### Requirement: First available root

`primera_ruta_disponible(so, extra=None)` MUST return the first `rutas_base` candidate whose `estado_unidad` reports `conectado`, else `None`.

#### Scenario: extra path available

- GIVEN `extra` pointing to an existing `tmp_path`
- WHEN `primera_ruta_disponible("macOS", extra)` runs
- THEN it returns that path

#### Scenario: nothing responds

- GIVEN `rutas_base` stubbed to return only a nonexistent path
- WHEN `primera_ruta_disponible("macOS")` runs
- THEN it returns `None`

### Requirement: Knob route reconstruction

`reconstruir_rutas(ruta_base, proyecto)` MUST generate exactly `{TO_VFX|comp|FROM_VFX}_SERVER_{MAC|WINDOWS|ARTIST}` (9 keys) with forward slashes and trailing slash: `{base}/{proyecto}/{PREFIJO}/`. Slashes/whitespace on inputs MUST be stripped.

**Casing decision (deliberate, do not 'fix'):** the middle prefix is `comp` (lowercase) while `TO_VFX`/`FROM_VFX` are uppercase. This is the V1 legacy knob contract — the actual Rutas node knobs are literally named `comp_SERVER_MAC` etc. (V1 `entorno.py` `PREFIJOS = ("TO_VFX", "comp", "FROM_VFX")`). Unifying to `COMP_SERVER_*` would break existing node-knob lookups and saved comps. V2 MUST keep the exact legacy casing in `reconstruir_rutas`; any future unification is a separate, explicitly-versioned migration, never a silent rename.

#### Scenario: nine keys under neutralized base

- GIVEN base `"/Volumes/estudio/2026"` and proyecto `"CINE"`
- WHEN `reconstruir_rutas(base, proyecto)` runs
- THEN 9 keys are returned and `TO_VFX_SERVER_MAC == "/Volumes/estudio/2026/CINE/TO_VFX/"`

#### Scenario: Windows stays forward-slash

- GIVEN base `"L:/VFX/2026"` and proyecto `"CINE"`
- WHEN `reconstruir_rutas(base, proyecto)` runs
- THEN no value contains `"\\"`

### Requirement: Project extraction from path

`proyecto_desde_ruta(ruta, base=None, so=None)` MUST return the first segment under `base` (`"CINE"` from `/Volumes/estudio/2026/CINE/COMP/...`); `None` when the path is empty, equals the base, falls outside every base, or only shares a partial prefix (`/Volumes/estudio2026/...`). Backslashes MUST normalize to `/`. Without `base`, candidates come from `rutas_base(so or detectar_so())`.

#### Scenario: project under macOS base

- GIVEN ruta `"/Volumes/estudio/2026/CINE/COMP/EP_100/foo.nk"`, base `"/Volumes/estudio/2026"`
- WHEN `proyecto_desde_ruta(ruta, base=base)` runs
- THEN it returns `"CINE"`

#### Scenario: partial prefix is not a match

- GIVEN ruta `"/Volumes/estudio2026/CINE/COMP/foo.nk"`, base `"/Volumes/estudio/2026"`
- WHEN `proyecto_desde_ruta(ruta, base=base)` runs
- THEN it returns `None`