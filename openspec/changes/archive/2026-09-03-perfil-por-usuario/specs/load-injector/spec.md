# Delta for load-injector

## MODIFIED Requirements

### Requirement: Pure environment assembly

`armar_estado_env(perfil, so, ruta_plato, base=None) -> dict` MUST be pure: no nuke import, no global state, MUST NOT mutate `os.environ`. `PROJECT_ROOT` MUST be the plate's project root via structural cut (`raiz_proyecto_desde_ruta`, `core-entorno`) — NOT base detection. `PYTHON_TO_VFX` / `PYTHON_COMP` / `PYTHON_FROM_VFX` MUST be the profile's space roots for the explicit `so`. When the plate yields no project root (untitled script or no marker), `PROJECT_ROOT` MUST fall back to the injected `base`, then to the current-SO space root.

(Previously: `PROJECT_ROOT` was the single profile base; PYTHON_* were derived from `reconstruir_rutas` on that base.)

#### Scenario: comp under space root yields cut env

- GIVEN a profile with COMP root `/Volumes/estudio/2026/CINE/COMP` (macOS) and plate `/Volumes/estudio/2026/CINE/COMP/EP_100/ep.nk`
- WHEN `armar_estado_env(perfil, "macOS", ruta)` runs
- THEN the dict has `"PROJECT_ROOT": "/Volumes/estudio/2026/CINE"` and `PYTHON_TO_VFX`/`PYTHON_COMP`/`PYTHON_FROM_VFX` equal to the profile's macOS space roots

#### Scenario: untitled script still gets a root

- GIVEN `ruta_plato=""` (untitled) and base `/Volumes/estudio/2026/CINE/COMP` passed explicitly
- WHEN `armar_estado_env(perfil, "macOS", "", base="/Volumes/estudio/2026/CINE/COMP")` runs
- THEN `PROJECT_ROOT` equals the injected base (no structural cut possible) and no space root is lost

#### Scenario: deterministic across calls

- GIVEN identical `(perfil, so, ruta_plato, base)` inputs
- WHEN `armar_estado_env` runs twice
- THEN both returned dicts are identical

#### Scenario: purity — no os.environ mutation

- GIVEN a snapshot of `os.environ` before the call
- WHEN `armar_estado_env` runs
- THEN `os.environ` is unchanged

### Requirement: Profile store resolution

The loader MUST resolve the profile-store path in this order: **project store** `{raiz_proyecto}/.saman/nuke_profiles.json` where `raiz_proyecto` comes from the structural cut of the plate path; then `NUKE_PROFILES_PATH` env var; then `SamanTools.config_local` scoped override; then `~/.config/saman/nuke_profiles.json`. A project store MUST always win when it exists — `NUKE_PROFILES_PATH`/`config_local` become fallbacks for projects without `.saman/`. The project-store probe MUST NOT hang on a dead mount (timed/cached check) and MUST NOT create `.saman/` on read.

**No module-name collision:** the local override MUST NOT be a bare `config_local.py` at the repository root — the repo root enters `sys.path` in Nuke and a generic module name there collides with any other studio plugin using the same name. The override MUST live INSIDE the package as an importable `SamanTools.config_local` module (gitignored) or as a local `.json` read by a `SamanTools.config_local` loader. The store path is config data read through that scoped module, never a naked top-level module.

(Previously: the env var was the top override — the chain started at `NUKE_PROFILES_PATH`.)

#### Scenario: project store wins

- GIVEN `NUKE_PROFILES_PATH` set and a project root whose `.saman/nuke_profiles.json` exists
- WHEN the store path resolves
- THEN the project store path is used

#### Scenario: env var is the fallback without .saman

- GIVEN no `.saman/` under the project root and `NUKE_PROFILES_PATH` set
- WHEN the store path resolves
- THEN the env-var path is used