# SamanTools V2 — Architecture & V1/V2 Coexistence

> Technical artifact (English). Changes `load-contract` (slice H5) and
> `perfil-por-usuario` (slice S5, per-user profile model). Fictitious paths
> only — this repository is PUBLIC and must never carry real studio
> absolute paths, credentials, or hostnames.

## Overview

V2 keeps the pure core (`SamanTools/core/`) invisible to Nuke and adds a
visibility layer: a self-contained artist bootstrap (`bootstrap/menu.py`), a
lazy-import compat shim (`SamanTools/rutas.py`), a pure/thin load injector
(`SamanTools/ui/injector.py`) and a minimal exec target
(`SamanTools/ui/menu.py`). The env contract stays data-driven; the injector
applies it at `addOnScriptLoad` so TCL `[getenv PROJECT_ROOT]` resolves in
Read/Write nodes, and re-asserts the cached dict at `addOnScriptSave`
(memory only — no disk, no lock). Composition roots come from a **per-user
profile store** (3 spaces × 3 OS per user) resolved project-first — see
[Per-user profile model](#per-user-profile-model) below.

## V1/V2 Coexistence

V1 and V2 never run side by side silently. The model is: **V2 replaces V1
with explicit consent**, and the transition period is temporary and
documented here only.

### Distinct bootstrap marker

- The V2 installer writes `~/.nuke/menu.py` carrying the marker
  **`SamanTools V2 bootstrap`**.
- This marker is deliberately different from the V1 marker, so the **V1
  uninstaller can never delete the V2 bootstrap** during a temporary
  coexistence window.
- Symmetrically, the V2 uninstaller removes the installed `menu.py` only
  when it carries its own V2 marker; a foreign or V1 file is left intact.

### Replace-with-consent model

- No silent takeover: migrating means the artist (or the studio installer,
  in a future change) explicitly consents to removing V1.
- Rollback is additive: all V2 files are new, so `git revert` restores the
  V1-only state; the V1 `~/.nuke/menu.py` is never touched by V2.

### Migration steps

1. Back up or remove the V1 checkout: delete `~/.nuke/SamanTools` and the
   V1 `~/.nuke/menu.py` (only after V1 is no longer needed).
2. Install V2 (installer or the bootstrap's own maintenance buttons) into
   the same `~/.nuke/SamanTools` checkout path — the repository checkout IS
   the tools folder.
3. Confirm the consent dialog when the V2 bootstrap asks to replace the
   previous install.
4. Restart Nuke. The V2 bootstrap then loads `SamanTools/ui/menu.py` from
   the checkout (exec target probe), syncs itself from
   `bootstrap/menu.py` (md5), and offers Actualizar/Desinstalar under
   SamanTools > Configuración.

### Shim keeps V1 comps alive

- During coexistence, legacy comps still call `rutas.actualizar(nuke.thisNode())`.
- The V2 shim (`SamanTools/rutas.py`) re-exports the V1 constants and
  delegates to the core, so existing Rutas nodes keep working without V1.
- The shim follows the same precedence chain as the injector and never
  clobbers an environment the injector already wrote this session
  (`_env_inyectado` guard).
- The per-user model leaves this shim untouched (D8): it holds no
  hostname-signed profile call and never imports the profile engine, so the
  V1 knob contract above keeps working unchanged.

## Profile store: project-first chain

The profile-store path (AD5, `perfil-por-usuario`) resolves PROJECT-FIRST:

1. `{project_root}/.saman/nuke_profiles.json` — the project store; ALWAYS
   wins when the file exists. Existence is probed against dead mounts
   (anti-hang), and `.saman/` is NEVER created on read: it is born lazily
   on the first write, under lock.
2. `NUKE_PROFILES_PATH` (env) → scoped `SamanTools.config_local` → JSON
   sibling `config_local.json` → `~/.config/saman/nuke_profiles.json`
   (final default).

The project root comes from `nuke.root().name()` via
`core.entorno.raiz_proyecto_desde_ruta` (structural cut at the first
`TO_VFX|COMP|FROM_VFX` marker segment; `.saman` is deliberately NOT a
marker). Untitled scripts or plates outside any root start the chain at the
env link.

## Per-user profile model

- Schema (D1/AD1): envelope
  `{"perfiles": {user: {TO_VFX|COMP|FROM_VFX: {macOS|Windows|Linux: root}}}}`
  — one store file, users as keys, three independent spaces × three OS
  roots per user.
- Resolution is USER-ONLY (AD2): `resolver_perfil(user, path)` reads
  `perfiles.get(user)` directly; the V1 hostname ladder and the
  foreign-host fallback are GONE. Unknown or legacy users get silent
  onboarding with fictitious 3×3 roots.
- `carpeta_salida` is always the token `[getenv PROJECT_ROOT]/COMP/`,
  resolved at script-load time (R4 — breaking for consumers of the old
  resolved path).

## Local studio override (gitignored)

The local override MUST be a scoped module **inside the package**
(`SamanTools/config_local.py`), never a bare `config_local.py` at the
repository root: the repo root enters `sys.path` inside Nuke and a generic
module name there collides with any other studio plugin using the same name.

`SamanTools/config_local.py` is gitignored (`.gitignore`: `config_local.py`,
a basename pattern that matches at any depth) and is NEVER committed to this
public repository. The injector tolerates its absence. The studio installer
(future change) writes the shared per-project path here. Template
(placeholder only — no real paths):

```python
# SamanTools/config_local.py — scoped local override (gitignored, NEVER commit)
NUKE_PROFILES_PATH = ""
```

Alternatives: leave the file absent (fall through to home default) or ship a
sibling `config_local.json` next to the module with the same key.

## Path Manager selector

- `SamanTools > Path Manager...` (Ctrl+Alt+R, fallback Ctrl+Alt+O on
  collision) opens the profile selector dialog.
- The combo lists the users present in the resolved store, preselecting the
  ambient user (`getpass.getuser()`).
- Selecting a user applies the profile instantly: `preparar_seleccion_perfil`
  → `cachear_env` + `aplicar_entorno` → re-evaluate Read nodes so
  `[getenv PROJECT_ROOT]` resolves with the new env. A stale store
  (`ValueError`) is reported without applying a partial env.
- Unknown users get the onboarding form (base → fictitious 3×3 roots);
  known users can change the base per space. Headless sessions degrade
  silently (no window, no exception). A legacy-shaped entry triggers a
  one-time regeneration warning on open (read-only flag; the engine
  regenerates the row on the next write).

## Release note R4

- Project store wins: `{project_root}/.saman/nuke_profiles.json` beats any
  shared or home store when it exists.
- Foreign-host fallback gone: hostname no longer participates in profile
  resolution (AD2); resolution is per user only.
- `carpeta_salida` → `[getenv PROJECT_ROOT]/COMP/` (token resolved at load;
  breaking for consumers of the old resolved path).
- Legacy profile rows regenerate to the 3×3 shape on the next write, with a
  one-time UI warning.

## Integrity chain

The complete-checkout probe verifies the pure V2 engine at
`SamanTools/core/rutas_engine.py`; the exec target is
`SamanTools/ui/menu.py`; the auto-sync source is `bootstrap/menu.py`. If any
link is missing, the bootstrap repairs the checkout (`git reset --hard`
origin) or stays silent.