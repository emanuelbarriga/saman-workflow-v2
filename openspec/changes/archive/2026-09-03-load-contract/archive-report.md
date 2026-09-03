# Archive Report: load-contract — V2 bootstrap, shim, injector, menu

**Change**: load-contract
**Archived at**: `openspec/changes/archive/2026-09-03-load-contract/`
**Archive date**: 2026-09-03 (ISO 8601)
**Artifact store mode**: openspec (filesystem) + Engram traceability (hybrid per `openspec/config.yaml` and prior change convention)
**Phase**: sdd-archive
**Final status**: implementation complete, verified with warnings, archived

This is the terminal record of the SDD cycle at CLOSE time. It supersedes the
intermediate snapshots (`apply-progress` #2305, `verify-report` #2306) for any
claim about the current state of the change. Per the Final-State Authority
hierarchy, the persisted tasks artifact and `verify-report` are the source of
truth for completion and verification facts; the launch brief is the most
recent account and outranks intermediate snapshots where it differs.

---

## 1. Final State

- **Implementation**: COMPLETE — 5 slices H1–H5 shipped as 5 conventional
  commits, `8cb4849..f6298f5`. Final code commit: `f6298f5`
  (`docs(load-contract): add V1/V2 coexistence guide and H5 gate tests (H5)`).
- **Tasks**: 19/19 implementation tasks checked `[x]` in the persisted
  `tasks.md` (groups H1–H5; verified by `rg '^\s*- \[ \]'` → zero matches at
  archive time). No stale unchecked tasks; no reconciliation needed.
- **Verification**: PASS WITH WARNINGS — 244/244 tests green
  (`python3 -m pytest`, exit 0, output sha256 `c6d1e7df…`), py_compile of all
  10 touched `.py` files exit 0, 27/27 requirements and 36/36 spec scenarios
  compliant, zero CRITICAL, 2 WARNING (both by-design, see §4), 1 SUGGESTION.
  Evidence revision sha256 `d04a4703…`.
- **Archive**: change folder moved to
  `openspec/changes/archive/2026-09-03-load-contract/` preserving proposal,
  exploration, design, tasks, verify-report and all 4 delta specs; the active
  changes directory now contains only `archive/`.
- **Specs**: 4 NEW domains synced 1:1 into `openspec/specs/` (§2). These main
  specs did NOT exist before — no destructive merge occurred. The `config.yaml`
  archive rule ("Warn before merging destructive deltas") required no warning.

### Brief-vs-artifact count note (recorded explicitly)

The launch brief stated "load-bootstrap-contract 13 reqs, load-shim 5,
load-injector 10, load-ui-menu 4 = 32 reqs / 36 escenarios". The persisted
`verify-report` (#2306) and the delta spec files themselves report
**load-injector 5 requirements / 10 scenarios** (the brief used load-injector's
scenario count as its requirement count). Per the brief's own instruction to
use the verify-report counts, the authoritative figures are **27 requirements /
36 scenarios** (5+5+13+4 reqs; 10+8+14+4 scenarios). The launch-prompt figure
undercounts requirements by 5; nothing was pending either way.

## 2. Specs Synced — Main Specs (source of truth)

All 4 delta specs are FULL specs for NEW capabilities. None of the four domains
existed under `openspec/specs/` (only `core-*` from the previous change).
Copied 1:1 per the OpenSpec convention with `cp`, byte-identical verified with
`diff`; no merge, nothing deleted or renamed.

| Domain | Action | Requirements | Scenarios |
|--------|--------|--------------|-----------|
| `openspec/specs/load-bootstrap-contract/spec.md` | Created (1:1) | 13 | 14 |
| `openspec/specs/load-shim/spec.md` | Created (1:1) | 5 | 8 |
| `openspec/specs/load-injector/spec.md` | Created (1:1) | 5 | 10 |
| `openspec/specs/load-ui-menu/spec.md` | Created (1:1) | 4 | 4 |
| **Total** | 4 domains | **27** (RFC 2119) | **36** |

Counts cross-checked against the verify-report compliance matrix (#2306) and
the actual spec files; both agree.

`config.yaml` archive rule ("Warn before merging destructive deltas"): NO
destructive merge occurred (new domains only). No warning required.

## 3. Verification Summary (at close)

Per `verify-report` #2306 (written at verification time; no later commit
changed any test, code or spec — H5 `f6298f5` was the terminal slice, so the
snapshot is also the final state):

| Metric | Value |
|--------|-------|
| Tests | **244 passed / 0 failed / 0 skipped** (`python3 -m pytest`, exit 0) |
| py_compile | 10/10 touched `.py` OK, exit 0 (`injector.py`, `menu.py`, `rutas.py`, `bootstrap/menu.py`, `config_local.py`, 5 test files); `compileall -q SamanTools bootstrap tests` OK |
| Requirements | 27/27 COMPLIANT |
| Scenarios | 36/36 COMPLIANT |
| Coverage (informational, threshold 0) | `injector.py` 90% ✅ · `rutas.py` 75% ⚠ (warning, by-design) · `ui/menu.py` 0% by design · `bootstrap/menu.py` n/a |
| Verdict | PASS WITH WARNINGS — 0 CRITICAL, 2 WARNING, 1 SUGGESTION |
| Evidence revision | `sha256:d04a4703e7fb78f1e7e263348e306da13653223394b5f85c1631a376f42218c3` |
| Test output hash | `sha256:c6d1e7df130a4c6935f5bcbc4f5b6f299fbde1ee3eb7a123d2f726d0ae08fcd8` |
| TDD compliance | 6/6 checks passed (RED/GREEN confirmed 5/5 test files; 244/244 green; safety net 240/240 per apply-progress #2305) |

Design conformance: ADR-1..ADR-10 all followed (per verify-report Coherence
section); ADR-7 carries the only interface-location deviation, documented (W2).

## 4. Residual Findings (classified → follow-ups)

**CRITICAL**: None.

**WARNING — 2, both by-design, none blocks archive:**

1. **W (load-shim / coverage)** — `SamanTools/rutas.py` at 75% < 80%
   strict-TDD threshold. Uncovered lines are nuke-bound legacy knob reads and
   defensive branches explicitly excluded from unit coverage by the load-shim
   spec ("Reading legacy knobs stays nuke-bound and is not unit-covered").
   Not blocking; reported honestly.
2. **W (load-injector / design coherence)** — `registrar_callbacks()` is
   implemented in `SamanTools/ui/menu.py:63` while `design.md` Interfaces lists
   it under `SamanTools/ui/injector.py`. Documented deviation (tasks.md H1
   note, injector.py:33-37, ADR-7 flag location); behavior, idempotency flag
   (`injector._callbacks_registrados`) and all spec scenarios comply.

**SUGGESTION — 1:**
1. `SamanTools/__init__.py:3` docstring stale ("la capa de interfaz grafica se
   anade en cambios posteriores" — `ui/menu.py` now exists). Update wording in
   a future touch of that file.

**Tracked open questions (from design.md, carried forward) — 3:**
1. Validate `project_directory` knob metadata (name/value semantics) on real
   Nuke 13/14/15 at apply on a real station; adjust
   `_override_proyecto_desde_root` if the knob auto-derives from `name()`.
2. Confirm actual knobChanged-vs-addOnScriptLoad ordering in a real V1 comp;
   contract is order-independent by design (ADR-3), but log empirically.
3. `PYTHON_*` rescan of `{PYTHON_COMP}/Scripts` (V1 `proyecto.py:90`) has no V2
   home — deferred to the future `vfxflow/` change; legacy `[python ...]` Read
   scripts keep working because `PYTHON_*` land in `__main__`.

## 5. Residual Risks Carried Forward (mission brief)

1. **ADR-5 knob `project_directory`** — unvalidated on real Nuke; must be
   validated on Nuke 13/14/15 in a real station (open question 1 above).
2. **knobChanged vs addOnScriptLoad ordering** — order-independent by design
   (ADR-3, injector cache wins); empirical log still pending (open question 2).
3. **`PYTHON_COMP` rescan deferred** to `vfxflow/` (open question 3).
4. **`REPO_URL` placeholder in `bootstrap/menu.py`** — generic value by design
   (public repo convention: no real studio paths); the studio installer/future
   change must inject the real URL at setup.

## 6. Review Gate

No native review artifacts exist for this change (no `reviews/` directory in
the change folder before or after the move; no ledger/receipt/gate-context
found). Delivery is treated as `disabled/unmanaged` (kill switch off, no
review governs this change) — the only relaxation the native gate permits, and
it does not manufacture `allow`. Archive proceeded under the standard gates:
Task Completion Gate passed (19/19 `[x]`, zero stale unchecked), no CRITICAL
verification findings (gate: pass_with_warnings, blockers 0), stage-blocking
global gates (SDD init, skills loading, status retrieval) all satisfied.

## 7. Commit Traceability

| Slice | Commit | Content |
|-------|--------|---------|
| init | `834b101`, `457aa99` | repo init; SDD context init (previous change) |
| foundation | `38a6568` | archive core-rutas-engine + sync 5 main specs (previous change) |
| H1 | `8cb4849` | `feat(ui): add injector pure env assembly` |
| H2 | `4994314` | `feat(rutas): add V1 compat shim` |
| H3 | `46d8632` | `feat(bootstrap): add V2 artist bootstrap` |
| H4 | `fb5120e` | `feat(ui): add menu entry, callbacks and TCL injector` |
| H5 | `f6298f5` | `docs(load-contract): add V1/V2 coexistence guide and H5 gate tests` — **terminal commit** |

## 8. Engram Traceability

| Artifact | Observation ID | Topic |
|----------|----------------|-------|
| design | #2298 | `sdd/load-contract/design` |
| tasks | #2303 | `sdd/load-contract/tasks` |
| apply-progress (H1–H5, 5 revisions) | #2305 | `sdd/load-contract/apply-progress` |
| verify-report | #2306 | `sdd/load-contract/verify-report` |
| archive-report | (this change) | `sdd/load-contract/archive-report` |

`proposal.md`, `exploration.md` and the 4 delta specs were NOT persisted as
separate Engram observations — filesystem-only within the archived change
folder (openspec store). Observation IDs validated via `mem_search` at archive
time (2026-09-03). Project: `saman-workflow-v2`, scope: `project`.

## 9. Archive Compliance

- Tasks artifact: 19/19 `[x]`, zero stale unchecked implementation tasks — no
  reconciliation needed; archive is NOT intentional-with-warnings.
- All artifacts present in the archived folder: proposal ✅, exploration ✅,
  4 delta specs ✅, design ✅, tasks ✅ (19/19), verify-report ✅,
  archive-report ✅ (this file).
- The archive is an AUDIT TRAIL: source artifacts were moved, not modified
  (the only write inside it is this archive-report).
- Source code was NOT modified by this phase. `tasks.md`/`verify-report.md`
  contents untouched — only relocated.
- Main specs synced BEFORE the archive move (execution order respected).
- Commit of the archive move and the 4 new main specs is PENDING — the
  orchestrator performs it (explicit note in the launch brief).

## 10. Next Steps (beyond this change)

- **Next change: `vfxflow/`** — SamanTools/vfxflow = core + `panel_comentarios`
  (Ctrl+Alt+C) per the repo plan. It is the natural successor because the
  load-contract design explicitly defers the `PYTHON_*` rescan of
  `{PYTHON_COMP}/Scripts` to vfxflow (open question 3), and vfxflow is the only
  remaining layer that both consumes the now-shipped load/visibility layer and
  follows core purity rules. `render/` (distributed orchestrator) and the `ui/`
  panels remain later per config.yaml context and the previous archive §10.