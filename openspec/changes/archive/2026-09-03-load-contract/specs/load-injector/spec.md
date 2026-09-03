# SamanTools Load Injector Specification

## Purpose

NEW load layer (`SamanTools/ui/injector.py`, name confirmed in design): resolves profile and SO, assembles the environment as pure data, applies it to `os.environ` and `__main__` so TCL `[getenv PROJECT_ROOT]` resolves in Read/Write nodes, and registers load/save callbacks. Pure/thin split: `armar_estado_env` MUST be fully testable without nuke. Scenario paths MUST be fictitious.

## Requirements

### Requirement: Pure environment assembly

`armar_estado_env(perfil, so, ruta_plato, base=None) -> dict` MUST be pure: no nuke import, no global state, MUST NOT mutate `os.environ`. It MUST assemble the context with explicit `so` and a base from the `base` parameter or `ruta_para_plataforma(perfil, so)`, correcting the engine gap where an untitled script or a path outside every root yields `base=None`.

#### Scenario: comp under root yields full env

- GIVEN a profile with base `/Volumes/estudio/2026`, `so="macOS"` and plate path `/Volumes/estudio/2026/CINE/TO_VFX/ep.nk`
- WHEN `armar_estado_env(perfil, "macOS", ruta)` runs
- THEN the dict has `"PROJECT_ROOT": "/Volumes/estudio/2026"` plus `PYTHON_TO_VFX` / `PYTHON_COMP` / `PYTHON_FROM_VFX` derived from that base

#### Scenario: untitled script still gets a base

- GIVEN `ruta_plato=""` (untitled) and base `/Volumes/estudio/2026` passed explicitly
- WHEN `armar_estado_env(perfil, "macOS", "", base="/Volumes/estudio/2026")` runs
- THEN `PROJECT_ROOT` equals the injected base although `get_context` would return `base=None`

#### Scenario: deterministic across calls

- GIVEN identical `(perfil, so, ruta_plato, base)` inputs
- WHEN `armar_estado_env` runs twice
- THEN both returned dicts are identical

#### Scenario: purity — no os.environ mutation

- GIVEN a snapshot of `os.environ` before the call
- WHEN `armar_estado_env` runs
- THEN `os.environ` is unchanged

### Requirement: Thin environment application

`aplicar_entorno(env)` MUST write `env` into `os.environ` and into `__main__.__dict__`, and MUST be idempotent: repeating the same dict MUST NOT duplicate or alter values.

#### Scenario: apply repeats without duplication

- GIVEN `env` produced by `armar_estado_env`
- WHEN `aplicar_entorno(env)` runs twice
- THEN `os.environ["PROJECT_ROOT"]` and `__main__.PROJECT_ROOT` equal the single expected value after both calls

### Requirement: No disk or lock on save (latency guard)

The loader MUST cache the last assembled `env` dict in memory after `addOnScriptLoad`. `addOnScriptSave` MUST NOT re-read the profile store, MUST NOT acquire the file lock, MUST NOT call the engine's store functions, and MUST only re-assert the cached in-memory dict via `aplicar_entorno`. Auto-save frequency MUST NOT cause disk I/O or lock contention on shared storage (LucidLink): the save path MUST be pure memory.

#### Scenario: save re-asserts from memory only

- GIVEN a load that assembled `env` once and cached it
- WHEN `addOnScriptSave` fires repeatedly
- THEN no store read and no lock acquisition occurs (store read/lock counters stay at their load-time values) and `os.environ` keeps the cached values

### Requirement: Callback registration

`registrar_callbacks()` MUST register `addOnScriptLoad` — resolve ambient identity into a profile, `detectar_so()`, context from `nuke.root().name()`, `armar_estado_env`, `aplicar_entorno` — and `addOnScriptSave` — idempotent re-assert of the cached in-memory env (see "No disk or lock on save"). The load flow MUST be injector-first (profile is source of truth) and MUST NOT raise when no profile resolves (fictitious onboarding fallback).

**Precedence (overrides — MUST be respected, in this order):**
1. **Headless/render farm**: if `PROJECT_ROOT` (or the store path) is ALREADY present in `os.environ` BEFORE the callback runs — injected upstream by the render orchestrator (Deadline/Tractor/`render_distribuido`) — the loader MUST NOT replace it, MUST NOT resolve the profile, and MUST NOT trigger onboarding. The existing value wins and the callback is a no-op for environment writes.
2. **Manual script override**: if the script declares an explicit per-project override (e.g. `nuke.root()` `project_directory` knob or a documented manual override flag), the loader MUST respect that local value instead of silently overwriting it with the profile root. Detecting the override MUST follow the same string-level, injectable pattern as the engine (no ambient assumptions).

#### Scenario: script load resolves TCL env

- GIVEN a script whose root name is `/Volumes/estudio/2026/CINE/TO_VFX/ep.nk`
- WHEN the addOnScriptLoad callback fires
- THEN `os.environ` contains `PROJECT_ROOT` and TCL `[getenv PROJECT_ROOT]` evaluates

#### Scenario: render farm env wins

- GIVEN `os.environ["PROJECT_ROOT"]="/mnt/estudio/2026/CINE"` injected by an orchestrator before launch, and a profile store without that user
- WHEN the addOnScriptLoad callback fires
- THEN `PROJECT_ROOT` keeps `/mnt/estudio/2026/CINE`, no onboarding happens, and no other value is written

#### Scenario: manual script override respected

- GIVEN a script whose root declares `project_directory="/Volumes/estudio/2026/OTRO_COMP"` explicitly
- WHEN the addOnScriptLoad callback fires
- THEN `PROJECT_ROOT` equals `/Volumes/estudio/2026/OTRO_COMP` (profile root not applied)

### Requirement: Profile store resolution

The loader MUST resolve the profile-store path in this order: `NUKE_PROFILES_PATH` env var, then the shared per-project path supplied by the studio setup (fictitious in artifacts, e.g. under a project `config/` folder), then `~/.config/saman/nuke_profiles.json`, then engine fictitious onboarding.

**No module-name collision:** the local override MUST NOT be a bare `config_local.py` at the repository root — the repo root enters `sys.path` in Nuke and a generic module name there collides with any other studio plugin using the same name. The override MUST live INSIDE the package as an importable `SamanTools.config_local` module (gitignored) or as a local `.json` read by a `SamanTools.config_local` loader. The store path is config data read through that scoped module, never a naked top-level module.

#### Scenario: env var wins

- GIVEN `NUKE_PROFILES_PATH` set to a fictitious project-shared store and a populated `~/.config/saman/nuke_profiles.json`
- WHEN the store path resolves
- THEN the env-var path is used