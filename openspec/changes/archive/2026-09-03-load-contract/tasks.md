# Tasks: load-contract — V2 bootstrap, shim, injector, menu

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,500-1,700 (H1 380 / H2 430 / H3 650 / H4+H5 140) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1=H1 → PR2=H2 → PR3=H3 → PR4=H4+H5 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| H1 | Injector+tests | PR 1 | pytest tests/test_injector.py | N/A, pure no Nuke | revert injector.py+test |
| H2 | Shim+tests | PR 2 | pytest tests/test_shim.py | N/A, headless | revert rutas.py+test |
| H3 | Bootstrap+tests | PR 3 | pytest tests/test_bootstrap.py | N/A, fakes | revert bootstrap+test |
| H4+H5 | menu+docs+gate | PR 4 | pytest && py_compile | N/A, ui 0% by design | revert menu/docs/config |

## H1 — Injector (`SamanTools/ui/injector.py`, `tests/test_injector.py`)

- [x] 1.1 RED: `armar_estado_env` (root-env, untitled+base #2286, determinism, env-snapshot purity) → implement pure fn `(perfil, so, ruta_plato, base=None)` in `ui/injector.py`; py_compile
- [x] 1.2 RED: `obtener_ruta_store` chain — env → scoped `SamanTools.config_local` → `~/.config/saman/nuke_profiles.json`; tolerant ImportError; no root `config_local.py` → implement; green
- [x] 1.3 RED: `aplicar_entorno` idempotent (`os.environ` + `__main__`) → implement + `_env_cache`; green
- [x] 1.4 RED: `_override_proyecto_desde_root` (`project_directory` declared/empty/missing, fake root) → implement; green
- [x] 1.5 RED: `registrar_callbacks` — load flow: farm pre-set `PROJECT_ROOT` no-op/no-onboarding → `_override_proyecto_desde_root` → perfil → `armar_estado_env` → `aplicar_entorno`; no-profile → fictitious onboarding, no raise; save memory-only, no store/lock; idempotent once → implement; fictitious paths only

> Nota H1 (apply): esta entrega la maquinaria PURA del flujo — `_aplicar_precedencia`
> (preexistente headless gana → override → perfil), `cachear_env` (`_env_cache` +
> `_env_inyectado`, save memory-only) y el helper de override. El propio
> `registrar_callbacks()` (bind `nuke.addOnScriptLoad`/`addOnScriptSave`) requiere
> nuke.ui y se implementa en H4, como escalo el orchestrator.

## H2 — Shim (`SamanTools/rutas.py`, `tests/test_shim.py`)

- [x] 2.1 RED: headless import, no stub (conftest untouched), string annotations, fake node only in `test_shim.py` → create module; green
- [x] 2.2 RED: constants = V1 literals — `KNOBS_RUTAS_BASE` 9-tuple, `SUFIJOS`, `KNOBS_VERSION_ACTUAL`, `_KNOBS_A_MIGRAR` (.nk-serialized) → re-export from V1 `rutas.py`; green
- [x] 2.3 RED: `actualizar(fake)` bool + `_env_inyectado` guard (ADR-3); `es_nodo_rutas`; `es_version_actual` → facades delegate core + `injector.aplicar_entorno`; green
- [x] 2.4 RED: `aplicar_proyecto`, `refrescar_fuentes`, `encontrar_nodos_rutas`, `refrescar_estado` + `_texto_estado`/`_reescribir_proyecto_en_rutas` copies → implement; green
- [x] 2.5 RED: 5 stubs (`crear_o_reutilizar`, `cambiar_proyecto`, `avisar_duplicados`, `refrescar_fuentes_boton`, `ruta_nk_por_defecto`) no-op `None`; docstring compat-only → implement; green
- [x] 2.6 Verify: purity guard `test_no_import_nuke_en_core.py` passes; `core/` untouched; suite + py_compile; anti-leak

## H3 — Bootstrap (`bootstrap/menu.py` V1 copy, `tests/test_bootstrap.py`)

- [x] 3.1 RED: 11 V1 rules via `sys.modules` nuke fake + git/subprocess monkeypatch (fetch-only, consent+6 h lock, ff-only, silence, tmp+rename, reset repair, md5 sync, menu-on-checkout, update-button reinstalls, uninstall, self-contained) → port V1 `bootstrap/menu.py` rules; green
- [x] 3.2 RED: V2 probes — `_checkout_completo` probes `core/rutas_engine.py`; `_cargar_menu_real` execs `ui/menu.py` (source-string until H4); sync reads `bootstrap/menu.py` → adapt probes; green
- [x] 3.3 RED: marker "SamanTools V2 bootstrap", NOT "bootstrap de artista" (V1 immune) → docstring; green; generic `REPO_URL`/`BRANCH`, no real paths

## H4 — Exec target (`SamanTools/ui/menu.py`)

- [x] 4.1 RED: bootstrap exec True, callbacks once, menu exists; shim failure tolerated → thin module (top-level nuke, `try/except` shim, SamanTools menu + Configuración, no panels/PySide); py_compile
- [x] 4.2 Verify: suite + py_compile green (ui 0% by design)

## H5 — Docs + final gate

- [x] 5.1 gitignored `SamanTools/config_local.py` sample (scoped `NUKE_PROFILES_PATH` override, `.gitignore:22`)
- [x] 5.2 `docs/` V1/V2 coexistence + replace-with-consent note, fictitious paths
- [x] 5.3 final gate: `python3 -m pytest` + py_compile every touched .py; conventional commits, suite green each commit