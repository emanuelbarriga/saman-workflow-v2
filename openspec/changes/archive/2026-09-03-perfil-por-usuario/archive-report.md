# Archive Report: perfil-por-usuario — user-only profile model (3×3)

**Change**: perfil-por-usuario
**Archived at**: `openspec/changes/archive/2026-09-03-perfil-por-usuario/`
**Archive date**: 2026-09-03 (ISO 8601)
**Artifact store mode**: openspec (filesystem) + Engram traceability (hybrid per `openspec/config.yaml` and prior change convention)
**Phase**: sdd-archive
**Final status**: implementation complete, verified with warnings, archived

This is the terminal record of the SDD cycle at CLOSE time. It supersedes the
intermediate snapshots (`verify-report` #2320, final-state summary #2322) for
any claim about the current state of the change. Per the Final-State Authority
hierarchy, the persisted tasks artifact and `verify-report` are the source of
truth for completion and verification facts; the launch brief is the most
recent account and outranks intermediate snapshots where it differs.

---

## 1. Final State

- **Implementation**: COMPLETE — 5 slices S1–S5 shipped as 5 conventional
  commits, `8913c11..c062a25`. Final code commit: `c062a25`
  (`docs(v2): update architecture for per-user profile model (S5)`).
- **Tasks**: 23/23 implementation tasks checked `[x]` in the persisted
  `tasks.md` (groups S1 ×8, S2 ×6, S3 ×3, S4 ×3, S5 ×3; verified by
  `rg '^\s*- \[ \]'` → zero matches at archive time). No stale unchecked
  tasks; no reconciliation needed.
- **Verification**: PASS WITH WARNINGS (`pass_with_warnings`) — 350 tests
  green (`QT_QPA_PLATFORM=offscreen python3 -m pytest -q`, exit 0, 3.03 s,
  output sha256 `26bc2781…`), py_compile of 7 touched `.py` exit 0,
  24/24 delta requirements and 42/42 spec scenarios compliant, zero CRITICAL,
  zero blockers, 1 WARNING (by-design, see §4), 1 SUGGESTION. Evidence
  revision sha256 `06698a8d…`.
- **Model change (the core of this change)**: the profile model moved from
  user+hostname (`hosts`/`default` ladder, one base per OS) to **user-only**
  `{user: {TO_VFX|COMP|FROM_VFX: {macOS, Windows, Linux}}}` — three independent
  per-space roots per platform. Store moves to
  `{proyecto}/.saman/nuke_profiles.json` (project-first chain with anti-hang
  probe); Path Manager gains a profile selector combo with apply-on-select;
  legacy-shape stores regenerate with a UI warning; V1 shim (`SamanTools/rutas.py`)
  untouched (D8).
- **Archive**: change folder moved to
  `openspec/changes/archive/2026-09-03-perfil-por-usuario/` preserving
  proposal, exploration, design, tasks, verify-report and all 5 delta specs;
  the active changes directory now contains only `archive/`.
- **Specs**: 5 MAIN specs merged (§2). This change MODIFIES existing specs —
  the first destructive merge in this repo's archive history (breaking schema,
  inverted store chain). The `config.yaml` archive rule ("Warn before merging
  destructive deltas") required the warning recorded in §2.

## 2. Specs Synced — Main Specs (source of truth)

All 5 delta specs MODIFY existing MAIN specs; the merge replaced
MODIFIED requirements by heading and re-applied RENAMED requirements to their
new names (Reason/Migration notes preserved inline as `(Previously: ...)`
paragraphs in the merged requirements). ADDED requirements were appended at the
end of the Requirements section. Requirements NOT mentioned in the deltas were
preserved untouched:

- `core-rutas-engine`: **`String-level relativization` preserved** (not in delta)
- `load-injector`: **`Thin environment application`, `No disk or lock on save`,
  `Callback registration` preserved** (not in delta)
- `panel-path-manager-helper`: no untouched requirements (all 5 MODIFIED)
- `panel-path-manager-widget`: **`Env purity outside aplicar_entorno` preserved**
  (not in delta)
- `core-entorno`: 6 existing requirements preserved; 1 ADDED appended

| Domain | Action | Delta blocks | Merged main spec (headings) | Scenarios (merged) |
|--------|--------|--------------|------------------------------|--------------------|
| `openspec/specs/core-rutas-engine/spec.md` | MODIFIED (7) + RENAMED (2) | 9 blocks | 8 requirements | 17 |
| `openspec/specs/core-entorno/spec.md` | ADDED (1) | 1 block | 7 requirements | 18 |
| `openspec/specs/load-injector/spec.md` | MODIFIED (2) | 2 blocks | 5 requirements | 11 |
| `openspec/specs/panel-path-manager-helper/spec.md` | MODIFIED (5) + ADDED (2) | 7 blocks | 7 requirements | 12 |
| `openspec/specs/panel-path-manager-widget/spec.md` | MODIFIED (4) + ADDED (1) | 5 blocks | 6 requirements | 9 |
| **Total** | 5 domains | **24 blocks / 42 delta scen** | **33 headings** | **67** |

**Count note (delta vs merged):** the verify report counts the delta as
24 requirement blocks / 42 scenarios (core-rutas-engine 9 reqs counts the two
RENAMED markers as blocks). After the rename+modify merge in
`core-rutas-engine`, each RENAMED+MODIFIED pair collapses into a single
renamed requirement heading, so the merged main spec has 33 requirement
headings while preserving all 42 delta scenarios (plus untouched main-spec
scenarios). The authoritative verification figures remain **24/24 reqs —
42/42 scenarios** per the `verify-report` envelope.

**`config.yaml` archive rule — destructive-merge warning (applied):**
the rule "Warn before merging destructive deltas" FIRES for this archive.
Two MODIFIED merges are breaking: (1) `core-rutas-engine` — `JSON profile
store` schema rewritten user-only 3×3 (legacy `hosts`/`default` shape
detected → regenerated with flag) and `Profile resolution by user` removes the
hostname ladder; (2) `load-injector` — `Profile store resolution` chain
inverted to project-first (project store always wins; `NUKE_PROFILES_PATH` /
`config_local` demoted to fallbacks). Both were intentional per the change's
own design (breaking-but-regenerative, V2 pre-release, AD1/AD2/AD5/AD6), were
specified in the delta specs, implemented in commits
`8913c11`/`7b9e381`, and verified (42/42 compliant). Mode was `auto` with no
user confirmation requested; the warning is recorded here instead. No
requirement heading was deleted wholesale (2 renames + replaces, 1 heading
preserved per domain where applicable).

## 3. Verification Summary (at close)

Per `verify-report` #2320 (written at verification time; `c062a25` S5 was the
terminal slice, so the snapshot is also the final state — corroborated by the
final-state summary #2322 written after S5):

| Metric | Value |
|--------|-------|
| Tests | **350 passed / 0 failed / 0 skipped** (`QT_QPA_PLATFORM=offscreen python3 -m pytest -q`, exit 0, 3.03 s) |
| py_compile | 7/7 touched `.py` OK, exit 0 (`rutas_engine.py`, `entorno.py`, `injector.py`, `path_manager.py`, `path_manager_panel.py`, `menu.py`, `rutas.py` shim) |
| Requirements | 24/24 COMPLIANT (delta blocks) |
| Scenarios | 42/42 COMPLIANT (0 UNTESTED, 0 FAILING, 0 PARTIAL) |
| Coverage (informational) | avg 87% across changed files: rutas_engine 90%, entorno 90%, injector 88%, path_manager 96%, panel 83%, menu 76% (threshold config 0) |
| Verdict | PASS WITH WARNINGS — 0 CRITICAL, 0 blockers, 1 WARNING, 1 SUGGESTION |
| Evidence revision | `sha256:06698a8d0929fb03045d6054dd683169139d5c745d4e40bbd19092d7ccbdb463` |
| Test output hash | `sha256:26bc2781196e37c19ca8aeba0f62fb07800ae0a7d3d5ff01d87b2423dab3c59b` |
| TDD compliance | 6/6 checks passed (RED/GREEN confirmed, 350/350 green, triangulation adequate, safety net 349/349 prior per slice) |

Design conformance: AD1–AD10 all followed per the verify-report Coherence
section (D10 slices confirmed: suite green per slice, commits S1→S5 stacked).

## 4. Residual Findings (classified → follow-ups)

**CRITICAL**: None.

**WARNING — 1, by-design, does not block archive:**

1. **W (load-ui/menu coverage)** — `SamanTools/ui/menu.py` at 76% < 80%.
   Uncovered lines are the nuke-bound layer (`_identidad_ambiental` real,
   `instalar()` with effect) — accepted by design (ADR-7: ui nuke-bound with
   module-level import; threshold config 0). Headless branches tested with
   `fake_nuke`. Not blocking; reported honestly.

**SUGGESTION — 1:**

1. `SamanTools/ui/menu.py:94-107` — `_identidad_ambiental()` still collects
   `hostname` (`socket.gethostname`) as a second return value; the call-site
   `_resolver_contexto_carga` discards it (`usuario, _hostname`). Pre-existing
   code from the load-contract change (H4), NOT in this change's diff, and no
   profile signature uses it (verified by `test_firmas_publicas_sin_hostname`).
   Optional cleanup in a future change to honor AD2 fully (hostname fully out).

**Tracked open questions (from design.md, carried forward) — 1:**
1. `carpeta_salida` token change is breaking for `get_context` consumers:
   `carpeta_salida` is now ALWAYS `"[getenv PROJECT_ROOT]/COMP/"` (AD3), never
   an absolute path — any consumer reading it as a filesystem path must switch
   to `absolutizar`/injector env first. Flagged in design.md "Open Questions";
   no known V2 consumer yet (Export Manager is the future one).

## 5. Residual Risks Carried Forward (mission brief)

1. **`carpeta_salida` breaking token** — `get_context` consumers expecting an
   absolute output folder now receive `[getenv PROJECT_ROOT]`-relative tokens;
   must be resolved via the injector env or `absolutizar` before filesystem use.
2. **`NUKE_PROFILES_PATH` loses top-override status** — the chain is now
   project-first; the env var can no longer override a project store. Studio
   global override, if ever needed, must be a NEW concept (B5 exploration).
3. **Legacy regeneration** — old-schema home stores (`hosts`/`default`) are
   detected as unknown and re-onboarded with the new shape on next write;
   regenerated stores are dev data (V2 pre-release). No real-data migration
   exists by design.
4. **Project-store precedence may surprise** (R4) — silently changes behavior
   for users who relied on the env-var override; documented in
   `docs/ARQUITECTURA-V2.md` release note (S5.1).

## 6. Review Gate

No native review artifacts exist for this change (no `reviews/` directory in
the change folder before or after the move; no ledger/receipt/gate-context
found). Delivery is treated as `disabled/unmanaged` (kill switch off, no
review governs this change) — the only relaxation the native gate permits, and
it does not manufacture `allow`. Archive proceeded under the standard gates:
Task Completion Gate passed (23/23 `[x]`, zero stale unchecked), no CRITICAL
verification findings (gate: pass_with_warnings, blockers 0), and the
destructive-merge warning rule (§2) was applied in auto mode per the launch
brief ("NO preguntes al usuario").

## 7. Commit Traceability

| Slice | Commit | Content |
|-------|--------|---------|
| S1 | `8913c11` | `feat(core): user-only profile schema (S1)` — engine 3×3 + ladder out + entorno cut |
| S2 | `7b9e381` | `feat(ui): project-first store chain (S2)` — injector + probe + menu call-sites |
| S3 | `721762f` | `feat(ui): profile listing and selection helper (S3)` |
| S4 | `6d56266` | `feat(ui): profile selector with apply-on-select (S4)` |
| S5 | `c062a25` | `docs(v2): update architecture for per-user profile model (S5)` — **terminal commit** |

Stacked-to-main chain (D10); suite green per slice; `SamanTools/rutas.py`
shim deliberately OUT of the diff (D8, proven by `test_shim.py` passing
unchanged).

## 8. Engram Traceability

Engram observations for this change (project `saman-workflow-v2`, scope
`project`):

| Artifact | Observation ID | Topic |
|----------|----------------|-------|
| explore | #2316 | `sdd/perfil-por-usuario/explore` |
| spec | #2317 | `sdd/perfil-por-usuario/spec` |
| design | #2318 | `sdd/perfil-por-usuario/design` |
| verify-report | #2320 | `sdd/perfil-por-usuario/verify-report` |
| final-state summary | #2322 | (closing observation after S5) |
| archive-report | #2323 | `sdd/perfil-por-usuario/archive-report` |

`proposal.md` and `tasks.md` were NOT persisted as separate Engram
observations — filesystem-only within the archived change folder (openspec
store, same convention as the load-contract archive; the apply phase of S3/S4
also did not persist per-slice apply-progress to Engram, noted in #2322).

## 9. Archive Compliance

- Tasks artifact: 23/23 `[x]`, zero stale unchecked implementation tasks — no
  reconciliation needed; archive is NOT intentional-with-warnings.
- All artifacts present in the archived folder: proposal ✅, exploration ✅,
  5 delta specs ✅, design ✅, tasks ✅ (23/23), verify-report ✅,
  archive-report ✅ (this file).
- The archive is an AUDIT TRAIL: source artifacts were moved, not modified
  (the only write inside it is this archive-report).
- Source code was NOT modified by this phase. `tasks.md`/`verify-report.md`
  contents untouched — only relocated.
- Main specs synced BEFORE the archive move (execution order respected) —
  5 main specs merged by heading; PRESERVED requirements confirmed per §2.
- Destructive-merge warning recorded per `config.yaml` archive rule (§2); mode
  auto, no user confirmation requested by the orchestrator.
- Commit of the archive move and the 5 merged main specs is PENDING — the
  orchestrator performs the commit (explicit note: same convention as the
  load-contract archive §9).

## 10. Next Steps (beyond this change)

- **Next change (recommended): Export Manager (Ctrl+Alt+E)**
  (`export_panel` per config.yaml context). It is the natural successor
  because (1) the mass-relativization now deferred (proposal "Out of Scope")
  is exactly the Export Manager's core job — writing plate reads/writes with
  `[getenv PROJECT_ROOT]` strings; (2) it is the first consumer of the new
  `get_context` `carpeta_salida` token contract (§4 open question 1), which
  was flagged as breaking-but-consumerless in this change; and (3) with the
  3×3 user-only model now shipped, exports resolve `carpeta_salida` per the
  selected user's actual space roots. Later: `vfxflow/` (core +
  `panel_comentarios` Ctrl+Alt+C) and `render/` per config.yaml context.
- The `_identidad_ambiental` hostname-tuple cleanup (SUGGESTION §4) can ride
  along the next `ui/menu.py` touch.