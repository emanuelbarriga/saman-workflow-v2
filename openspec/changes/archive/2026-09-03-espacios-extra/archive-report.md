# Archive Report: espacios-extra — Extra Spaces

**Change**: espacios-extra
**Archived at**: `openspec/changes/archive/2026-09-03-espacios-extra/`
**Archive date**: 2026-09-03 (ISO 8601)
**Artifact store mode**: openspec (filesystem) + Engram traceability (hybrid per `openspec/config.yaml` and prior change convention)
**Phase**: sdd-archive
**Final status**: implementation complete, verified with warnings, archived

This is the terminal record of the SDD cycle at CLOSE time. It supersedes the
intermediate snapshots (`apply-progress` #2333, `verify-report` #2334) for any
claim about the current state of the change. Per the Final-State Authority
hierarchy, the persisted tasks artifact and `verify-report` are the source of
truth for completion and verification facts; the launch brief is the most
recent account and outranks intermediate snapshots where it differs. Here the
launch brief and `verify-report` AGREE on every final-state fact (see §1), so
no contradiction needed recording.

---

## 1. Final State

- **Implementation**: COMPLETE — 22/22 implementation tasks checked `[x]` in
  the persisted `tasks.md` (verified by `rg '^\s*- \[ \]'` → zero matches at
  archive time). No stale unchecked tasks; no reconciliation needed.
- **Delivery**: 5 stacked PRs, 15 conventional commits on `main`
  (saman-workflow-v2), HEAD `3c91aee` (§7).
- **Verification**: PASS WITH WARNINGS (verdict `pass_with_warnings`, 0
  blockers, `critical_findings: 0`) — full suite **461 passed / 0 failed / 0
  skipped** (`python3 -m pytest`, exit 0, 17.08s; offscreen `QT_QPA_PLATFORM`
  run also 461 passed), py_compile of the 3 touched production modules exit 0,
  11/11 requirements and 32/32 spec scenarios COMPLIANT, 1 informational
  WARNING (non-blocking) and 3 SUGGESTION (§4), TDD compliance 6/6. Evidence
  revision `sha256:a9fb1cf5058adbe960b575ab8793a10c608d42f430a9e8a1bbdf32d7c68917dd`.
- **Scope honored**: production delta limited to the 3 declared modules —
  `SamanTools/core/rutas_engine.py`, `SamanTools/ui/path_manager.py`,
  `SamanTools/ui/path_manager_panel.py` (+ 5 test files + tasks.md). No other
  production file touched (per `verify-report` Coherence, `git diff --stat`).
- **Guard tests byte-identical and green**: `test_path_manager.py:459`/`:477`,
  `test_path_manager_panel.py:501-522`/`:537-540`, `test_rutas_engine.py` env
  guards — all unmodified and passing.
- **Archive**: change folder moved to
  `openspec/changes/archive/2026-09-03-espacios-extra/` preserving proposal,
  exploration, design, tasks, verify-report and all 3 delta specs; the active
  changes directory now contains only `archive/`.
- **Specs**: 3 EXISTING domains merged with the deltas (§2) — MODIFIED and
  ADDED requirements only; zero REMOVED/RENAMED, no destructive merge occurred.
  The `config.yaml` archive rule ("Warn before merging destructive deltas")
  required no warning.
- **Git state note**: the planning artifacts (proposal, exploration, design,
  3 delta specs, verify-report) were UNTRACKED before this archive; `tasks.md`
  was already tracked (marked complete per-phase in the docs commits). This
  archive commit adds the untracked artifacts and records the folder move.

## 2. Specs Synced — Main Specs (source of truth)

All 3 delta specs target EXISTING main specs. Merged per the OpenSpec
convention: MODIFIED requirements replaced in place (full updated requirement
blocks, existing scenarios preserved), ADDED requirements appended at the end
of the Requirements section. Everything else in each main spec was PRESERVED.

| Domain | Action | Delta (from verify matrix) | Main spec after merge |
|--------|--------|----------------------------|-----------------------|
| `openspec/specs/core-rutas-engine/spec.md` | Modified | 3 ADDED + 1 MODIFIED (12 scenarios) | 11 requirements / 28 scenarios |
| `openspec/specs/panel-path-manager-helper/spec.md` | Modified | 4 ADDED + 1 MODIFIED (14 scenarios) | 11 requirements / 25 scenarios |
| `openspec/specs/panel-path-manager-widget/spec.md` | Modified | 2 ADDED + 0 MODIFIED (6 scenarios) | 8 requirements / 15 scenarios |
| **Total** | 3 domains | **11 requirements / 32 scenarios** | **30 requirements / 68 scenarios** |

Merge details:

- **core-rutas-engine**: MODIFIED "Environment variables exposure (TCL
  contract)" replaced in place — cut markers stay canonical-only (R6), extras
  emit `PYTHON_<extra>` via `_clave_env_para_espacio`, canonical first + sorted
  extras, missing extra root → key OMITTED (never `""`, no sibling fallback);
  prior scenario preserved, 3 new scenarios added. ADDED: sanitizer
  (`_clave_env_para_espacio`, 4 scenarios), lock-guarded removal
  (`eliminar_espacio_store`, 3 scenarios), canonical agreement test (1
  scenario).
- **panel-path-manager-helper**: MODIFIED "Change-base prepares merged roots
  and env delta" replaced in place — accept-list widened to canonical OR
  profile-known before the TODOS branch (R4); prior scenario preserved, 2 new
  scenarios added. ADDED: `sanitizar_espacio_extra` (7 scenarios), extra roots
  in `raices_para_so` (1 scenario), add/remove helpers (2 scenarios), extras-only
  store data-loss warning R3 (1 scenario).
- **panel-path-manager-widget**: ADDED extras subtree (3 scenarios) and
  add/remove flows (3 scenarios). No MODIFIED requirements.

Counts cross-checked against the verify-report compliance matrix (#2334) and
the actual merged spec files; both agree (delta: 11 requirements / 32
scenarios).

`config.yaml` archive rule ("Warn before merging destructive deltas"): NO
destructive merge occurred (MODIFIED + ADDED only; zero REMOVED/RENAMED). No
warning required.

## 3. Verification Summary (at close)

Per `verify-report` #2334 (written at verification time; the terminal commit
`3c91aee` closed tasks 5.1-5.3 and no later commit changed code, tests or
specs, so the snapshot is also the final state — corroborated by the launch
brief's final-state facts):

| Metric | Value |
|--------|-------|
| Tests | **461 passed / 0 failed / 0 skipped** (`python3 -m pytest`, exit 0; PySide6 6.10.2 + pytest-qt 4.5.0; offscreen run also 461) |
| py_compile | 3/3 touched production modules OK, exit 0 (`rutas_engine.py`, `path_manager.py`, `path_manager_panel.py`) |
| Requirements | 11/11 COMPLIANT (delta) |
| Scenarios | 32/32 COMPLIANT (delta) |
| Coverage (informational, threshold 0) | `rutas_engine.py` 84% ⚠ · `path_manager.py` 96% ✅ · `path_manager_panel.py` 90% ✅ — all changed files ≥ 80% |
| Verdict | PASS WITH WARNINGS — 0 CRITICAL, 0 blockers, 1 WARNING (informational), 3 SUGGESTION |
| Evidence revision | `sha256:a9fb1cf5058adbe960b575ab8793a10c608d42f430a9e8a1bbdf32d7c68917dd` |
| Test output hash | `sha256:224aa1ff2d2e20701b6d8f9c9fad4eac2ea026922a6fc701b54ce9c50d5aa909` |
| Build output hash | `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty output) |
| TDD compliance | 6/6 checks passed (RED/GREEN confirmed across 5 test files; suite baseline 457 per slice, final 461) |
| Test layer distribution | ~420 unit + ~41 widget integration (qtbot) = 461 across 15 test files |

Design conformance: ADR D1–D8 all followed (per verify-report Coherence —
canonical removal guard D1, per-row OS selector defaults to `self.so` D2,
lexicographic `sorted()` extras D3, unsanitizable key omitted D4, `_copia_con_slot`
iterates all keys D5, separate `grupo_extras` subtree D6, `eliminar_espacio_extra`
gain `so` param D7, existing-row name as fixed QLabel D8).

## 4. Residual Findings (classified → follow-ups)

**CRITICAL**: None.

**WARNING — 1, informational, does NOT block archive:**

1. **W (coverage / informational)** — no WARNING-grade functional findings;
   coverage of all changed files meets the ≥ 80% threshold (engine 84%,
   helper 96%, widget 90%). Reported honestly per strict-TDD module and
   `coverage_threshold: 0`.

**SUGGESTION — 3:**

1. `core-rutas-engine` / R3 — the "hand-edited extras-only entry is flagged,
   not written" scenario is verified via mechanism-equivalent tests
   (`detectar_forma_perfil` canonical-only classification, `estado_panel`
   legacy flag, regen-on-write) using `hosts`/`default` fixtures; a direct
   test with an extras-only fixture (`{"ana": {"3D": {...}}}` no canonical
   key) would pin the scenario's exact shape.
2. Engram hygiene — the espacios-extra SDD artifacts (incl. apply-progress
   #2333) were persisted under project `saman-nuke-tools` while the code repo
   is `saman-workflow-v2` (same git remote backing; discovery only via
   `all_projects` search). The archive report follows the same attribution per
   the launch brief.
3. `variables_entorno` unchanged-yet-documented `_LockFcntl`/`_LockMsvcrt`
   classes are unreachable on darwin (factory always returns `_LockDir`);
   harmless dead-weight from D6-v2, out of this change's scope.

## 5. Residual Risks Carried Forward

1. Real-Nuke behavior of the widget's extra rows (OS selector switching,
   `nuke.message` for invalid names) is pinned by pytest-qt + fakes, not a live
   Nuke session — consistent with the repo's established widget testing
   convention.
2. Engine lock classes `_LockFcntl`/`_LockMsvcrt` remain untestable on darwin
   (Windows-only branches, pre-existing).
3. Hand-edited extras-only stores are classified legacy and regenerated
   wholesale (extras lost) — documented behavior (R3), prevented by
   construction in the helper add flow; a genuine store-edit hazard for manual
   JSON edits.

## 6. Review Gate

No native review artifacts exist for this change (`reviewLedger`,
`reviewReceipt`, `reviewState` all missing in `gentle-ai sdd-status`; no
`reviews/` directory in the change folder before or after the move —
consistent with all prior changes). Delivery is treated as
`disabled/unmanaged` (kill switch off, modo auto, no review governs this
change) — the only relaxation the native gate permits, and it does not
manufacture `allow`. Archive proceeded under the standard gates: Task
Completion Gate passed (22/22 `[x]`, zero stale unchecked), no CRITICAL
verification findings (verdict `pass_with_warnings`, blockers 0,
`critical_findings` 0), config archive rule satisfied (no destructive delta).
`actionContext.mode` is `repo-local` (not `workspace-planning`) and all
archive operations stayed inside `allowedEditRoots`.

## 7. Commit Traceability

15 commits on `main` (all merged before archive; HEAD `3c91aee`), 5 stacked PRs:

| PR | Commits | Content |
|----|---------|---------|
| PR 1 (engine env core) | `5b341a7` · `4bd7c05` · `b918a29` | RED sanitizer + extras env tests; `feat(core): all-key env injection + sanitizer`; docs tasks 1.1-1.5 |
| PR 2 (engine removal + race) | `2ac5eb8` · `9af35c2` · `6a94825` | RED `eliminar_espacio_store` + race; `feat(core): lock-guarded eliminar_espacio_store`; docs tasks 2.1-2.3 |
| PR 3 (helper) | `11ad3d9` · `10f0b9e` · `a1e96d0` | RED helper extras; `feat(ui): extra-space validation + add/remove helpers`; docs tasks 3.1-3.8 |
| PR 4 (widget) | `5963448` · `9fbdf5b` · `210fedf` | RED extras widget subtree/OS/add/remove; `feat(ui): extra-space rows in Path Manager widget`; docs tasks 4.1-4.3 |
| PR 5 (agreement + injector) | `e478121` · `f566392` · `3c91aee` | `test(core): _ESPACIOS agreement`; `test(ui): extras through armar_estado_env`; docs tasks 5.1-5.3 — **terminal commit** |

Suite progression per slice: baseline 457 → 461 (green at each commit; guards
byte-identical throughout).

## 8. Engram Traceability

| Artifact | Observation ID | Topic |
|----------|----------------|-------|
| explore | #2328 | `sdd/espacios-extra/explore` |
| proposal | #2329 | `sdd/espacios-extra/proposal` |
| spec (3 delta specs) | #2330 | `sdd/espacios-extra/spec` |
| design | #2331 | `sdd/espacios-extra/design` |
| tasks | #2332 | `sdd/espacios-extra/tasks` |
| apply-progress (PR 5 final) | #2333 | `sdd/espacios-extra/apply-progress` |
| verify-report | #2334 | `sdd/espacios-extra/verify-report` |
| archive-report | (this change) | `sdd/espacios-extra/archive-report` |

All observation IDs validated via `mem_search` at archive time (2026-09-03).
Project: `saman-nuke-tools` (per prior-change attribution and the launch
brief), scope: `project`.

## 9. Archive Compliance

- Tasks artifact: 22/22 `[x]`, zero stale unchecked implementation tasks — no
  reconciliation needed; archive is NOT intentional-with-warnings.
- All artifacts present in the archived folder: proposal ✅, exploration ✅,
  3 delta specs ✅, design ✅, tasks ✅ (22/22), verify-report ✅,
  archive-report ✅ (this file).
- The archive is an AUDIT TRAIL: source artifacts were moved, not modified
  (the only write inside it is this archive-report).
- Source code was NOT modified by this phase. `tasks.md`/`verify-report.md`
  contents untouched — only relocated.
- Main specs synced BEFORE the archive move (execution order respected);
  merged content re-verified AFTER the move (requirement/scenario counts in §2).
- Commit of the archive move and the 3 main-spec merges: performed by this
  phase (`docs(openspec): archive espacios-extra and merge 3 main specs`); not
  pushed — orchestrator handles delivery.

## 10. Next Steps (beyond this change)

- **Next change recommended: `export-manager` (Export Manager, Ctrl+Alt+E)** —
  the next panel of the UI matrix per `openspec/config.yaml` context. It
  absorbs the MASS Read/Write relativization explicitly deferred by prior
  proposals (same `PROJECT_ROOT` relativization machinery this change
  broadened to arbitrary spaces gets extended to file-level Read/Write
  scripts), reusing the pure helper + thin widget + extras-subtree patterns
  proven here.
- Alternative ordering: remaining `core-*` domains or `vfxflow/` + `render/`
  per the repo plan; nothing depends on espacios-extra before the other panels
  ship.