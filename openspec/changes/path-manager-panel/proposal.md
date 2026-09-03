# Proposal: path-manager-panel

## Intent

First visible V2 panel: on-demand modal dialog (Ctrl+Alt+R) to onboard unknown users, show the active resolved profile (user/hostname + base per OS), change the current profile base with immediate env propagation, and report unit status.

## Scope

### In Scope

- `SamanTools/ui/path_manager.py` (new, PURE): resolve store+identity+profile; build per-platform roots; assemble env delta via injector; no nuke/PySide import.
- `SamanTools/ui/path_manager_panel.py` (new, THIN): PySide6/PySide2 `QDialog` (V1 `cambiar_colorspace` pattern): onboarding form (base per platform), profile view, change-base, unit status (`entorno.estado_unidad`), env apply.
- `SamanTools/ui/menu.py` (modified): "Path Manager" via `addCommand(..., shortcut="Ctrl+Alt+R")`; PySide imported DEFERRED in the callback (menu stays PySide-free).
- Tests: helper Qt-free; widget via pytest-qt + local nuke fake.

Extraction: V1 `panel_rutas.py` (reworked), `cambiar_colorspace.py` (dialog pattern); else new V2 code.

### Out of Scope

Mass Read/Write relativization (Export Manager, Ctrl+Alt+E); docked panel (future); `core/` edits; installer; `vfxflow/`; `render/`.

## Capabilities

- New: `panel-path-manager` — onboarding, profile view, change-base + env propagation, unit status, menu shortcut.
- Modified: None.

## Approach

Pure/thin split (injector precedent). Onboarding writes all 3 roots via public `guardar_perfiles` merge (no core edit). Change-base re-assembles env with explicit base → `cachear_env` + `aplicar_entorno`. Shortcut: single constant, collision-checked at apply.

## Affected Areas

| Area | Impact | What |
|------|--------|------|
| `SamanTools/ui/path_manager.py` | New | Pure helper |
| `SamanTools/ui/path_manager_panel.py` | New | QDialog |
| `SamanTools/ui/menu.py` | Modified | Command + shortcut, lazy PySide |
| `tests/test_path_manager{, _panel}.py` | New | Helper + widget tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| config.yaml says Ctrl+Alt+O; decision Ctrl+Alt+R | Med | Registry check; constant; fallback key |
| menu.py MUST NOT import PySide (test asserts) | High | Deferred import in callback |
| Nuke PySide vs dev PySide6 6.10.2 | Med | V1 dual-import pattern |
| pytest-qt offscreen flake | Med | Qt-optional `skipif`; helper Qt-free |
| No one-call write of 3 roots | Low | `guardar_perfiles` (public), no core edit |

## Rollback Plan

All new files except one additive menu delta: `git revert`, or delete new modules/tests + drop the `addCommand` line. Menu item disappears lazily (guarded import); suite green.

## Dependencies

- `core-rutas-engine`: `resolver_perfil`, `asegurar_perfil`, `ruta_para_plataforma`, `get_context`, `variables_entorno`, `guardar_perfiles` (verified).
- `load-injector`: `armar_estado_env`, `aplicar_entorno`, `cachear_env`, `obtener_ruta_store`.
- `core-entorno`: `estado_unidad`. pytest-qt 4.5.0, PySide6 6.10.2.

## Success Criteria

- [ ] Dialog opens via Ctrl+Alt+R, no collisions.
- [ ] Onboarding persists fictitious per-platform profile and propagates env.
- [ ] Change-base rewrites profile under lock and re-applies env.
- [ ] `python3 -m pytest` green; `py_compile` on touched files.

## Proposal question round

Assumptions for spec: (1) ambient identity, injectable; (2) manual env writes win, then `cachear_env`; (3) unit status covers current-OS base.