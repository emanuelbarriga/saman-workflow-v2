# Delta for SamanTools Path Manager Widget

## ADDED Requirements

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