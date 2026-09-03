# Archive Report: core-rutas-engine — V2 Foundation

**Change**: core-rutas-engine
**Archived at**: `openspec/changes/archive/2026-09-02-core-rutas-engine/`
**Archive date**: 2026-09-02 (ISO 8601)
**Artifact store mode**: openspec (filesystem) + Engram traceability (hybrid per `openspec/config.yaml`)
**Phase**: sdd-archive
**Final status**: implementation complete, verified, archived

This is the terminal record of the SDD cycle at CLOSE time. It supersedes the
intermediate snapshots (`apply-progress` #2282/#2283, `verify-report` #2284) for any
claim about the current state of the change.

---

## 1. Final State

- **Implementation**: COMPLETE — 7 code slices G1–G7 shipped as 7 conventional
  commits; G8 was verification-only (no code, no commit). Final code commit:
  `caf4f0d` (`feat(core): add relativization, context and env contract (G7)`).
- **Tasks**: 28/28 implementation tasks checked `[x]` in the persisted
  `tasks.md` (native status `taskProgress`: total 28, completed 28,
  `allComplete: true`, `applyState: all_done`). Zero unchecked tasks.
- **Verification**: PASS — 139/139 tests green (`python3 -m pytest`, exit 0,
  machine without Nuke), 27/27 requirements and 60/60 spec scenarios compliant,
  zero CRITICAL, zero WARNING, 3 SUGGESTION (see §4).
- **Archive**: change folder moved to
  `openspec/changes/archive/2026-09-02-core-rutas-engine/` preserving proposal,
  design, tasks, verify-report and all 5 delta specs; active changes directory
  is now empty.
- **Specs**: 5 NEW domains synced 1:1 into `openspec/specs/` (this was the
  FIRST change populating main specs — skeleton empty at init).

### Task-count discrepancy (recorded explicitly)

The launch brief and the `apply-progress` #2283 header say "24/24" tasks. The
persisted `tasks.md` contains **28** `[x]` items (G1 6, G2 3, G3 3, G4 3, G5 3,
G6 3, G7 3, G8 4) and the native `gentle-ai sdd-status` computes `total: 28,
completed: 28`. Per the Final-State Authority ranking, the persisted tasks
artifact and native status (#2) outrank the brief (#3): the final state is
**28/28 complete**. The "24/24" figure undercounts; nothing was pending either
way. This was already flagged by `verify-report` at verification time.

## 2. Specs Synced — Main Specs (source of truth)

`openspec/specs/` was empty (init skeleton). Every delta spec is a FULL spec for
a new capability, so each was copied 1:1 per the OpenSpec convention (delta of a
new change → MAIN). Byte-identical copies verified with `diff`; no merge, no
REQUIREMENTS preserved from a prior main spec (none existed).

| Domain | Action | Requirements | Scenarios |
|--------|--------|--------------|-----------|
| `openspec/specs/core-rutas-engine/spec.md` | Created (1:1) | 8 | 16 |
| `openspec/specs/core-entorno/spec.md` | Created (1:1) | 6 | 14 |
| `openspec/specs/core-nombres/spec.md` | Created (1:1) | 6 | 10 |
| `openspec/specs/core-limpiar/spec.md` | Created (1:1) | 4 | 10 |
| `openspec/specs/core-purity-guard/spec.md` | Created (1:1) | 3 | 10 (9 unique + 1 duplicated heading, see §5) |
| **Total** | 5 domains | **27** (RFC 2119) | **60** |

`config.yaml` archive rule ("Warn before merging destructive deltas"): NO
destructive merge occurred — main specs were empty, so nothing was deleted,
modified or renamed. No warning required.

## 3. Verification Summary (at close)

Per `verify-report` #2284 (written at verification time) and corroborated by the
persisted suite state:

| Metric | Value |
|--------|-------|
| Tests | **139 passed / 0 failed / 0 skipped** (`python3 -m pytest`, exit 0, 2.45–2.69s, no Nuke installed) |
| py_compile | 12/12 touched `.py` OK, exit 0 |
| Requirements | 27/27 COMPLIANT |
| Scenarios | 60/60 COMPLIANT |
| Coverage | 89% package total; changed files all ≥80% (coverage informative, threshold 0) |
| Verdict | PASS — no CRITICAL, no WARNING |
| Evidence revision | `sha256:971d381a48b49b99ea29a25f64b9ccca94b620c7deed2727f65bdb5db8bc6066` |
| Test output hash | `sha256:217ebf37c17a33046a49784e0f331d17ae3c2b385b838c2dcfbc47b2d6360f17` |

Design conformance: all decisions D1–D9 followed (schema envelope, precedence
ladder, locked onboarding, injectable API/graph, two-track normalization,
sibling lock, single guard matcher, test matrix, extraction order).

## 4. Residual Findings (classified → follow-ups)

No CRITICAL and no WARNING findings. Three SUGGESTIONs remain open as follow-ups
of this change — none blocks archive, all are recorded for future work:

1. **SUGGESTION (core-rutas-engine) — determinism corner in `get_context` with
   `base=None`**: when the plate path matches NO injected profile root, the
   V1-copy ambient `proyecto_desde_ruta(ruta)` (which calls `detectar_so()`)
   can contribute a platform-dependent `proyecto` before the name-token
   fallback. Only observable when the plate directory coincides with a real
   local base whose project differs from the filename prefix; no spec scenario
   fails (scenarios use basenames or matched fictitious roots).
   **Recommendation**: bypass the ambient call in the `base is None` path —
   name-token fallback only — for full cross-machine determinism.
   **Follow-up**: address in a future change touching engine determinism
   (e.g. alongside the load contract); optional dedicated test.
2. **SUGGESTION (core-purity-guard) — evidence drift**: task 8.3 records
   "6 matches (lines 8/30/153/161/174)"; the independent audit found 5 matching
   lines, all in the self-exempt guard test, 0 in sources. Requirement met;
   evidence-count cosmetics only.
   **Follow-up**: none required; align evidence text if the guard test changes.
3. **SUGGESTION (core-entorno) — uncovered OS branches**: `detectar_so`
   Windows/Linux branches and the Windows `dir` branch are uncovered on the
   macOS dev machine. A unit test monkeypatching `platform.system` would close
   the gap (coverage informational, not blocking).
   **Follow-up**: optional test hardening; not required for the change.

## 5. Known Quirks Carried Into MAIN Specs

- **Duplicate scenario heading in `core-purity-guard`**: the spec lists the
  heading "guard fails on real import" twice (both target
  `test_detectar_import_nuke_estatico`). The 60/60 scenario count counts spec
  blocks (59 unique + 1 duplicate); a future dedup would change the count and
  MUST be accompanied by a verification re-run. Copied 1:1 to preserve the
  verification count traceability.
- **Sibling lock file `nuke_profiles.json.lock` persists by design** (D6);
  deleting it reintroduces races.
- **`carpeta_salida` convention** (`/{proyecto}/COMP/`) is a first definition;
  to be confirmed against the future load layer (design open question).

## 6. Review Gate

No native review artifacts exist for this change (no `reviews/` directory in the
change folder; `gentle-ai sdd-status` reports `reviewGate: null`,
`reviewPolicy/reviewLedger/reviewReceipt` empty). Delivery is treated as
`disabled/unmanaged` (kill switch off, no review governs this change) — the only
relaxation the native gate permits, and it does not manufacture `allow`. Status
at archive time: `nextRecommended: archive`, `blockedReasons: []`,
`actionContext: repo-local` with `allowedEditRoots` = repo root; archive
operations stayed inside that root. Archive proceeded under the standard gates:
Task Completion Gate passed (28/28), no CRITICAL verification findings.

## 7. Commit Traceability

| Slice | Commit | Content |
|-------|--------|---------|
| init | `834b101`, `457aa99` | repo init; SDD context init (openspec config/skeleton) |
| G1 | `b172da9` | scaffold + import-purity guard |
| G2 | `be79672` | extract `core/entorno.py` |
| G3 | `391fd2a` | extract `core/nombres.py` |
| G4 | `a793f37` | extract `core/limpiar.py` |
| G5 | `4b2099d` | profile store + sibling lock |
| G6 | `ebf61b8` | profile resolution + locked onboarding |
| G7 | `caf4f0d` | relativization, context, env contract — **final code commit** |
| G8 | none (verification only) | full suite 139 green, py_compile 12/12, token audit, temp sweep |

## 8. Engram Traceability

| Artifact | Observation ID | Topic |
|----------|----------------|-------|
| proposal | #2276 | `sdd/core-rutas-engine/proposal` |
| spec | #2277 | `sdd/core-rutas-engine/spec` |
| design | #2280 | `sdd/core-rutas-engine/design` |
| tasks | #2281 | `sdd/core-rutas-engine/tasks` |
| apply-progress (G1–G7) | #2282 | `sdd/core-rutas-engine/apply-progress` |
| apply-progress (G8) | #2283 | `sdd/core-rutas-engine/apply-progress` |
| verify-report | #2284 | `sdd/core-rutas-engine/verify-report` |
| archive-report | (this change) | `sdd/core-rutas-engine/archive-report` |

All observation IDs validated via `mem_search`/`mem_get_observation` at archive
time (2026-09-02). Scope: `project` (`saman-workflow-v2`).

## 9. Archive Compliance

- Tasks artifact: 28/28 `[x]`, zero stale unchecked implementation tasks — no
  reconciliation needed; archive is NOT intentional-with-warnings.
- All artifacts present in the archived folder: proposal ✅, 5 delta specs ✅,
  design ✅, tasks ✅ (28/28), verify-report ✅, archive-report ✅.
- The archive is an AUDIT TRAIL: source artifacts were moved, not modified
  (the only write inside it is this archive-report).
- Source code was NOT modified by this phase. `tasks.md`/`verify-report.md`
  contents untouched — only relocated.
- Main specs synced BEFORE the archive move (execution order respected).
- OpenSpec artifacts are committed per repo convention (untracked in git —
  openspec/ delta artifacts are intentionally not committed; the archive move
  preserves them on disk for the next cycle).

## 10. Next Steps (beyond this change)

- **Bootstrap load contract** (`bootstrap/menu.py` + the `SamanTools/rutas.py`
  re-export shim, which MUST land in the same change as the V2 load layer per
  proposal traceability) — unblocks UI panels and the `[getenv PROJECT_ROOT]`
  TCL injector using `variables_entorno`.
- Later: `vfxflow/` panel + `render/` orchestrator extraction; `ui/` panels.