# Archive Report: path-manager-panel — Path Manager (Ctrl+Alt+R)

**Change**: path-manager-panel
**Archived at**: `openspec/changes/archive/2026-09-03-path-manager-panel/`
**Archive date**: 2026-09-03 (ISO 8601)
**Artifact store mode**: openspec (filesystem) + Engram traceability (hybrid per `openspec/config.yaml` and prior change convention)
**Phase**: sdd-archive
**Final status**: implementation complete, verified with warnings, archived

This is the terminal record of the SDD cycle at CLOSE time. It supersedes the
intermediate snapshots (`apply-progress` #2312, `verify-report` #2314) for any
claim about the current state of the change. Per the Final-State Authority
hierarchy, the persisted tasks artifact and `verify-report` are the source of
truth for completion and verification facts; the launch brief is the most
recent account and outranks intermediate snapshots where it differs.

---

## 1. Final State

- **Implementation**: COMPLETE — 3 slices P1–P3 shipped as 3 conventional
  commits: `f7451a4` (P1 `feat(ui): add path manager pure helper`), `e3eb8af`
  (P2 `feat(ui): add Path Manager dialog`), `4adf76d` (P3
  `feat(ui): register Path Manager in menu`). Final code commit: `4adf76d`.
- **First visible V2 panel**: the Path Manager modal dialog (Ctrl+Alt+R) is the
  FIRST user-visible V2 panel — onboarding form, active resolved profile
  (user/hostname + per-OS base), change-base with immediate env propagation via
  the injector, and unit status (`entorno.estado_unidad`).
- **Tasks**: 13/13 implementation tasks checked `[x]` in the persisted
  `tasks.md` (groups P1–P3; verified by `rg '^\s*- \[ \]'` → zero matches at
  archive time). No stale unchecked tasks; no reconciliation needed.
- **Verification**: PASS WITH WARNINGS (launch brief wording:
  "verified_with_warnings") — 292/292 tests green (`python3 -m pytest`, exit 0,
  output sha256 `d199eb8a…`), py_compile of all 6 touched `.py` files exit 0,
  13/13 requirements and 17/17 spec scenarios compliant, zero CRITICAL, 1
  WARNING (informational, non-blocking, see §4), 3 SUGGESTION. Evidence
  revision sha256 `d199eb8a95c73b2346f3240faa76a932f77254d1ff05b5ca4a609f8af00033b9`.
- **Core untouched**: `git diff f7451a4~1..HEAD --name-only` → **0** paths under
  `SamanTools/core/` (re-verified at archive time). The panel consumes core
  public API: `guardar_perfiles`/`leer_perfiles`/`asegurar_perfil` (write/read
  slices) + `resolver_perfil` (parity pinned in tests; detection itself NEVER
  calls it — D2) and the injector (`armar_estado_env`, `cachear_env`,
  `aplicar_entorno`).
- **Archive**: change folder moved to
  `openspec/changes/archive/2026-09-03-path-manager-panel/` preserving
  proposal, design, tasks, verify-report and all 3 delta specs; the active
  changes directory now contains only `archive/`.
- **Specs**: 3 NEW domains synced 1:1 into `openspec/specs/` (§2). None of the
  three domains existed before — no destructive merge occurred. The
  `config.yaml` archive rule ("Warn before merging destructive deltas")
  required no warning.

### Brief-vs-artifact count note (recorded explicitly)

The launch brief stated "13 reqs / 17 escenarios" and "1 WARNING coverage 70%
rutas defensivas". The persisted `verify-report` (#2314) and the delta spec
files agree exactly: **13 requirements / 17 scenarios** (helper 5/7, widget
5/5, menu 3/5). The single WARNING is the widget coverage gap (see §4): the
brief's "rutas defensivas" maps to the defensive submit guards (`ValueError`,
empty-base) plus the PySide2 dual-import branch, `_identidad_ambiental`
fallbacks and the full `abrir_dialogo` open path — all non-blocking per D6 and
`coverage_threshold: 0`. No contradiction; wording-only difference recorded
for traceability.

## 2. Specs Synced — Main Specs (source of truth)

All 3 delta specs are FULL specs for NEW capabilities. None of the three
domains existed under `openspec/specs/` (only `core-*` and `load-*` from the
previous changes). Copied 1:1 per the OpenSpec convention with `cp`,
byte-identical verified with `diff`; no merge, nothing deleted or renamed.

| Domain | Action | Requirements | Scenarios |
|--------|--------|--------------|-----------|
| `openspec/specs/panel-path-manager-helper/spec.md` | Created (1:1) | 5 | 7 |
| `openspec/specs/panel-path-manager-widget/spec.md` | Created (1:1) | 5 | 5 |
| `openspec/specs/panel-path-manager-menu/spec.md` | Created (1:1) | 3 | 5 |
| **Total** | 3 domains | **13** (RFC 2119) | **17** |

Counts cross-checked against the verify-report compliance matrix (#2314) and
the actual spec files; both agree.

`config.yaml` archive rule ("Warn before merging destructive deltas"): NO
destructive merge occurred (new domains only). No warning required.

## 3. Verification Summary (at close)

Per `verify-report` #2314 (written at verification time; P3 `4adf76d` was the
terminal slice and no later commit changed any test, code or spec, so the
snapshot is also the final state):

| Metric | Value |
|--------|-------|
| Tests | **292 passed / 0 failed / 0 skipped** (`python3 -m pytest`, exit 0; PySide6 6.10.2 + pytest-qt 4.5.0 active) |
| py_compile | 6/6 touched `.py` OK, exit 0 (`path_manager.py`, `path_manager_panel.py`, `menu.py`, 3 test files) |
| Requirements | 13/13 COMPLIANT |
| Scenarios | 17/17 COMPLIANT |
| Coverage (informational, threshold 0) | `path_manager.py` 96% ✅ · `path_manager_panel.py` 70% ⚠ (1 warning, non-blocking) · `ui/menu.py` 0% by design (ADR-7) |
| Verdict | PASS WITH WARNINGS — 0 CRITICAL, 1 WARNING, 3 SUGGESTION |
| Evidence revision | `sha256:d199eb8a95c73b2346f3240faa76a932f77254d1ff05b5ca4a609f8af00033b9` |
| Test output hash | `sha256:d199eb8a95c73b2346f3240faa76a932f77254d1ff05b5ca4a609f8af00033b9` |
| TDD compliance | 6/6 checks passed (RED/GREEN confirmed 3/3 test files; suite baseline 258 → 286 → 292 across slices) |
| Test layer distribution (this change) | 34 tests: 27 unit (2 files) + 7 widget integration (1 file, pytest-qt) |

Design conformance: ADR D1–D8 all followed (per verify-report Coherence
section). D1 (deferred PySide via function-local import, regex guard green),
D2 (detection without write, `_emparejar_con_fuente` mirrors the D2 ladder over
public `leer_perfiles`, resolver parity pinned), D3 (focused pure helper API),
D4 (thin dialog, PySide2→PySide6 dual import, env ONLY via injector, headless
degrade), D5 (flat item, constants `Ctrl+Alt+R`/fallback `Ctrl+Alt+O`,
injectable `_atajo_ocupado` + pure `seleccionar_atajo`), D6 (testability:
Qt-free helper, pytest-qt widget, menu fakes), D7 (change-base matched-entry
write shapes on all three kinds), D8 (green per commit, 3 commits).

## 4. Residual Findings (classified → follow-ups)

**CRITICAL**: None.

**WARNING — 1, informational, does NOT block archive:**

1. **W (panel-path-manager-widget / coverage)** —
   `SamanTools/ui/path_manager_panel.py` at 70% < 80% strict-TDD threshold
   (evidence: coverage run, 125 stmts / 37 miss). Uncovered lines are the
   PySide2 dual-import branch (by design, D4), defensive submit guards (empty
   base, `ValueError` from helper), `_identidad_ambiental` fallbacks and the
   full `abrir_dialogo` open path (which uses live
   `injector.obtener_ruta_store`/`entorno.detectar_so`). D6 explicitly allows
   0% for the widget if Qt is absent; with Qt present, error-path coverage is
   missing. Informational per strict-TDD module and `coverage_threshold: 0`;
   reported honestly.

**SUGGESTION — 3:**

1. `panel-path-manager-helper` / drift — module docstring inventory lists
   `estado_panel`, `detectar_desconocido`, `_emparejar_con_fuente`,
   `preparar_cambio_base`, `preparar_onboarding` but not the private
   `_primera_candidata` and `_normalizar_base` (path_manager.py:82-97). No
   functional drift (all underscore-private, pure, covered indirectly), but the
   header's function list is incomplete.
2. `panel-path-manager-menu` / labeling — the registered item is
   "Path Manager..." (with ellipsis, V1 tool-line convention, pinned by tests)
   while the spec literal says "Path Manager". Cosmetic; behavior and shortcut
   comply.
3. Design open question (D5) remains open: whether Nuke warns instead of
   raising on in-use shortcuts — only verifiable in a Nuke session;
   `_atajo_ocupado` is optimistic (try/except, never raises) by design.

**Tracked open questions (from design.md / verify-report, carried forward) — 2:**

1. Real Nuke shortcut collision for `Ctrl+Alt+R` (D5): Nuke warns, not raises,
   when `addCommand` claims an in-use shortcut — verify in a Nuke session
   (non-blocking; the fallback key `Ctrl+Alt+O` is ready and tested).
2. The PySide2 dual-import branch (path_manager_panel.py:25) never executed in
   the dev environment (PySide6 6.10.2 only) — both the branch and its widget
   behavior are pinned by tests, but a real PySide2/Nuke 13 run remains
   unexercised.

## 5. Residual Risks Carried Forward (mission brief)

1. **Shortcut collision in real Nuke (D5)** — `_atajo_ocupado` is optimistic;
   collision policy (warn vs raise) unverified in a Nuke session. Fallback key
   tested; risk is cosmetic only.
2. **PySide2 branch unexecuted in dev** — dual-import compat rests on the V1
   pattern and static tests, not a live PySide2 run.
3. **Menu coverage 0% by design** — `ui/menu.py` imports `nuke` at module
   level (ADR-7); coverage cannot attach. Behavior is pinned by `_MenuFake`
   tests.

## 6. Review Gate

No native review artifacts exist for this change (no `reviews/` directory in
the change folder before or after the move; no ledger/receipt/gate-context
found; `gentle-ai sdd-status` reports `reviewGate: null` — same as the two
prior changes). Delivery is treated as `disabled/unmanaged` (kill switch off,
modo auto per launch brief, no review governs this change) — the only
relaxation the native gate permits, and it does not manufacture `allow`.
Archive proceeded under the standard gates: Task Completion Gate passed
(13/13 `[x]`, zero stale unchecked), no CRITICAL verification findings (gate:
pass_with_warnings, blockers 0, critical_findings 0), config archive rule
satisfied (new domains only — no destructive delta).

## 7. Commit Traceability

| Slice | Commit | Content |
|-------|--------|---------|
| P1 | `f7451a4` | `feat(ui): add path manager pure helper` — helper + Qt-free tests |
| P2 | `e3eb8af` | `feat(ui): add Path Manager dialog` — widget + pytest-qt tests |
| P3 | `4adf76d` | `feat(ui): register Path Manager in menu` — **terminal commit** |

Baseline suite progression per slice: 258 → 286 → 292 (green at each commit).

## 8. Engram Traceability

| Artifact | Observation ID | Topic |
|----------|----------------|-------|
| spec (3 domain specs) | #2309 | `sdd/path-manager-panel/spec` |
| design | #2310 | `sdd/path-manager-panel/design` |
| apply-progress (P3 final revision) | #2312 | `sdd/path-manager-panel/apply-progress` |
| verify-report | #2314 | `sdd/path-manager-panel/verify-report` |
| archive-report | (this change) | `sdd/path-manager-panel/archive-report` |

`proposal.md`, `tasks.md` and the 3 delta specs are NOT persisted as separate
Engram observations — filesystem-only within the archived change folder
(openspec store; note: no `sdd/path-manager-panel/tasks` observation exists
for this change, unlike load-contract). Observation IDs validated via
`mem_search` at archive time (2026-09-03). Project: `saman-workflow-v2`,
scope: `project`.

## 9. Archive Compliance

- Tasks artifact: 13/13 `[x]`, zero stale unchecked implementation tasks — no
  reconciliation needed; archive is NOT intentional-with-warnings.
- All artifacts present in the archived folder: proposal ✅, 3 delta specs ✅,
  design ✅, tasks ✅ (13/13), verify-report ✅, archive-report ✅ (this file).
- The archive is an AUDIT TRAIL: source artifacts were moved, not modified
  (the only write inside it is this archive-report).
- Source code was NOT modified by this phase. `tasks.md`/`verify-report.md`
  contents untouched — only relocated.
- Main specs synced BEFORE the archive move (execution order respected);
  byte-identity of the 3 copies re-verified AFTER the move.
- Commit of the archive move and the 3 new main specs is PENDING — the
  orchestrator performs it (project convention; same as the previous two
  changes).

## 10. Next Steps (beyond this change)

- **Next change recommended: `Export Manager` (Ctrl+Alt+E)** — the next panel
  of the UI matrix per `openspec/config.yaml` context. It is the natural
  successor because it absorbs the MASS Read/Write relativization explicitly
  deferred by this change's proposal (Out of Scope: "Mass Read/Write
  relativization (Export Manager, Ctrl+Alt+E)") — the same
  `PROJECT_ROOT` relativization machinery the Path Manager now exercises
  singly (change-base) gets broadened to file-level Read/Write scripts, reusing
  the pure helper + thin widget + lazy menu patterns proven here (D1/D3/D4/D8).
- Alternative ordering: remaining `core-*` domains or `vfxflow/` + `render/`
  per the repo plan; nothing depends on Export Manager before the other panels
  ship.