# SamanTools Shim (rutas.py) Specification

## Purpose

NEW compatibility shim `SamanTools/rutas.py` keeps the V1 comp contract alive — comps run `from SamanTools import rutas; rutas.actualizar(nuke.thisNode())` — while delegating all logic to the pure core. `nuke` MUST be imported lazily inside function bodies so the module imports headless, and `SamanTools/core/` MUST NOT change. Node fakes MUST live only inside the shim's test module.

## Requirements

### Requirement: Headless import without a stub

The module MUST NOT import `nuke` at module level; any nuke access MUST happen lazily inside function bodies. `import SamanTools.rutas` MUST succeed under pytest (no stub) and on machines without Nuke. **Type-annotation rule:** no signature may reference a Nuke type that evaluates at import time — MUST use string annotations for Nuke types (`nodo: "nuke.Node"`, not `nodo: nuke.Node`) or `from __future__ import annotations` deferred evaluation; annotations MUST NOT force `nuke` resolution when the module imports.

#### Scenario: import ok without nuke

- GIVEN the V2 suite with no nuke stub (conftest untouched)
- WHEN `from SamanTools import rutas` runs
- THEN it succeeds and no `nuke` name is resolved at import time

#### Scenario: signature with Nuke type still imports headless

- GIVEN a shim function annotated `def actualizar(nodo: "nuke.Node") -> bool` (string form)
- WHEN the module imports under pytest with no stub
- THEN the import succeeds and `nuke.Node` is never evaluated at definition time

### Requirement: Re-export pure constants

`SUFIJOS`, `KNOBS_RUTAS_BASE`, `KNOBS_VERSION_ACTUAL` and `_KNOBS_A_MIGRAR` MUST be re-exported with values identical to V1: knob names and knob values are serialized in `.nk` files and MUST NOT change.

#### Scenario: KNOBS_RUTAS_BASE identical to V1

- GIVEN the V1 9-tuple `("TO_VFX_SERVER_MAC", "comp_SERVER_MAC", "FROM_VFX_SERVER_MAC", "TO_VFX_SERVER_WINDOWS", "comp_SERVER_WINDOWS", "FROM_VFX_SERVER_WINDOWS", "TO_VFX_SERVER_ARTIST", "comp_SERVER_ARTIST", "FROM_VFX_SERVER_ARTIST")`
- WHEN the shim's `KNOBS_RUTAS_BASE` is read
- THEN it equals that tuple in the same order

#### Scenario: SUFIJOS mapping preserved

- GIVEN V1's mapping `{"MacServer": "MAC", "Windows": "WINDOWS", "Artist": "ARTIST"}`
- WHEN `SUFIJOS` is read
- THEN it equals that dict

### Requirement: Thin nuke-bound facades

`actualizar`, `aplicar_proyecto`, `refrescar_fuentes`, `es_nodo_rutas`, `es_version_actual`, `encontrar_nodos_rutas` and `refrescar_estado` MUST keep V1 signatures and return types; their logic MUST delegate to `SamanTools.core.rutas_engine` and `core.entorno`, and any environment write MUST go through the injector's `aplicar_entorno` (same env contract as the injector). Reading legacy knobs stays nuke-bound and is not unit-covered.

#### Scenario: actualizar with a fake node returns without exception

- GIVEN a minimal node fake defined ONLY inside the shim test module, exposing `knobs()`
- WHEN `rutas.actualizar(fake)` runs
- THEN it returns a bool and raises no exception

#### Scenario: es_nodo_rutas detects by knobs

- GIVEN a fake node whose `knobs()` include `"UsuarioActivo"` and any `TO_VFX_SERVER_*` knob
- WHEN `rutas.es_nodo_rutas(fake)` runs
- THEN it returns True regardless of the node name

### Requirement: Compat-only stubs

Node-lifecycle and UX functions with no V2 caller (`crear_o_reutilizar`, `cambiar_proyecto`, `avisar_duplicados`, `refrescar_fuentes_boton`, `ruta_nk_por_defecto`) MUST exist as import-safe no-ops so `from SamanTools import rutas` never breaks. The shim docstring MUST mark them compat-only and never revived.

#### Scenario: crear_o_reutilizar is a no-op

- GIVEN the shim imported headless
- WHEN `rutas.crear_o_reutilizar()` runs
- THEN it returns None without accessing nuke and without raising

### Requirement: Core untouched

The shim MUST NOT modify any file under `SamanTools/core/`; the core purity guard test (no `import nuke` / PySide in core) MUST keep passing.

#### Scenario: core purity guard keeps passing

- GIVEN the V2 suite with the core import-guard test
- WHEN tests run after the shim lands
- THEN the guard passes and no `nuke`/PySide import exists under `SamanTools/core/`