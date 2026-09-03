# Delta for core-entorno

## ADDED Requirements

### Requirement: Project root from structural cut

`raiz_proyecto_desde_ruta(ruta, marcadores=("TO_VFX","COMP","FROM_VFX"))` MUST be a pure stdlib function (no filesystem access, no nuke/PySide). It MUST return the project root: the portion of `ruta` preceding the FIRST segment that matches any marker (case-insensitive, segment-boundary — a marker not preceded by a separator MUST NOT match), with backslashes normalized to forward slashes and trailing separators stripped. No marker segment or empty path MUST return `None`. This is the PRIMARY project-root derivation for `PROJECT_ROOT` (base detection is secondary).

#### Scenario: cut at COMP yields project root

- GIVEN ruta `"/Volumes/estudio/2026/CINE/COMP/EP_100/foo.nk"`
- WHEN `raiz_proyecto_desde_ruta(ruta)` runs
- THEN it returns `"/Volumes/estudio/2026/CINE"`

#### Scenario: cut at FROM_VFX yields project root

- GIVEN ruta `"/Volumes/estudio/2026/CINE/FROM_VFX/ep_050.nk"`
- WHEN `raiz_proyecto_desde_ruta(ruta)` runs
- THEN it returns `"/Volumes/estudio/2026/CINE"`

#### Scenario: no marker returns None

- GIVEN ruta `"/Volumes/estudio/2026/CINE/artwork/x.nk"`
- WHEN `raiz_proyecto_desde_ruta(ruta)` runs
- THEN it returns `None`

#### Scenario: Windows slashes normalize

- GIVEN ruta `"L:\\VFX\\2026\\CINE\\TO_VFX\\ep.nk"`
- WHEN `raiz_proyecto_desde_ruta(ruta)` runs
- THEN it returns `"L:/VFX/2026/CINE"`