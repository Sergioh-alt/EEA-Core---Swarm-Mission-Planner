# Documentation Structure Audit

**Date:** 2026-06-29
**Scope:** Complete `docs/` tree (94 documentation files)
**Type:** Documentation-only audit and migration proposal — **no code, architecture, or contract changes**
**Status:** Review deliverable. Migration is **proposed, not executed** (see §8).

---

## 1. Executive Summary

The `docs/` tree has grown organically across Phases 0–10C.3 and now contains
**94 files** spread over 6 subdirectories plus 2 loose root files. The content is
substantively complete and historically valuable, but suffers from four
structural problems:

1. **Category leakage** — `docs/architecture/` mixes true architecture (contracts,
   boundary specs) with *validation reports* (`phase_9_7_architecture_isolation_report.md`,
   `phase_9_7_cross_layer_leak_scan.md`) that belong under validation.
2. **ADRs live under a non-standard folder** — `docs/decisions/` holds 20 ADRs; the
   conventional and requested location is `docs/adr/`.
3. **Inconsistent naming** — mixed casing, spaces, accents, and language in
   filenames (e.g. `PHASE 9 = HARDWARE ABSTRACTION LAYER (HAL).md`,
   `EEA Swarm Mission Planner_Roadmap_Ejecution.md`), and validation reports that
   omit a phase prefix (`decision_boundary_compliance_report.md`).
4. **No navigational index** — there is no `docs/README.md` or per-directory index,
   making discovery difficult.

**No documents need to be deleted.** All historical information is preserved; the
plan is reorganization + additive indexing only.

---

## 2. Current Structure Analysis

| Directory | Files | Purpose (as used today) | Issues |
|-----------|-------|-------------------------|--------|
| `docs/` (root) | 2 | `system_overview.md`, `simulation_vs_reality.md` | Loose files, no index |
| `docs/architecture/` | 19 | Architecture, contracts, boundary specs, design proposals, **plus 2 validation reports** | Category leakage; naming inconsistency; versioned architecture docs mixed with current |
| `docs/architecture/ui/` | 7 | Phase 10C.1 UI architecture blueprint | OK — cohesive; naming consistent |
| `docs/decisions/` | 20 | ADR-001 … ADR-020 | Should be `docs/adr/` (convention + task requirement) |
| `docs/audit/` | 1 | `phase6_architecture_audit.md` | Single file, no index; plural `audits/` requested |
| `docs/roadmap/` | 5 | Phase protocols + 2 master roadmaps | Naming inconsistency (spaces, accents, `=`); 2 overlapping roadmaps |
| `docs/research/` | 1 | `.gitkeep` only | Empty placeholder |
| `docs/validation_testing/` | 43 | All phase validation/testing reports + 2 `.txt` logs | Rename to `validation/`; inconsistent naming; raw `.txt` outputs alongside reports |

### 2.1 Content classification of `docs/architecture/` (19 files)

**True architecture (keep in `architecture/`):**
- `SYSTEM BOUNDARY SPEC — ORIÓN PHASE 10.md`
- `PHASE-9.7-SEPARATION.md`
- `Hardware Abstraction Layer (HAL).md`
- `hal_boundary_lock_spec_phase9.md`
- `decision_boundary_map_phase8.md`, `decision_boundary_map_phase9.md`
- `phase7_design_proposal.md`, `phase8_design.md`, `phase9_design.md`
- `phase_9_7_simulation_contract.md`, `phase_9_7_iov_contract.md`, `phase_9_7_digital_twin_contract.md` (contracts)
- `architecture.md`, `001_architecture_v1.md`, `002_architecture_v0.5.md`, `v1_hardware_ready_architecture.md` (versioned/historical architecture)

**Misfiled — actually validation reports (should move to `validation/`):**
- `phase_9_7_architecture_isolation_report.md` → `validation/phase_9_7_architecture_isolation_report.md`
- `phase_9_7_cross_layer_leak_scan.md` → `validation/phase_9_7_cross_layer_leak_scan.md`

---

## 3. Findings

### 3.1 Duplicated / Overlapping documents
| Files | Assessment | Recommendation |
|-------|-----------|----------------|
| `architecture/001_architecture_v1.md`, `002_architecture_v0.5.md`, `architecture.md`, `v1_hardware_ready_architecture.md` | Four architecture snapshots at different versions. **Not exact duplicates** — they capture history. | Keep all; move historical ones into `architecture/history/` and keep the current canonical one at top level. Do **not** delete. |
| `roadmap/EEA Swarm Mission Planner_Roadmap_Ejecution.md`, `roadmap/roadmap_v2_final_clean.md` | Two master roadmaps; the "Execution Truth Log" is the SSOT, `v2_final_clean` is an earlier clean plan. | Keep both; designate the Truth Log as canonical in the roadmap index; rename for consistency. |

**No true (byte-identical or redundant) duplicates found.** No deletions proposed.

### 3.2 Obsolete documents
None are truly obsolete — all represent a historical phase or version. Items that
are *superseded* (older architecture versions) are retained under a `history/`
subfolder rather than deleted, per the "do not delete historical information" rule.

### 3.3 Inconsistent naming
| Current | Problem | Proposed |
|---------|---------|----------|
| `roadmap/PHASE 9 = HARDWARE ABSTRACTION LAYER (HAL).md` | spaces, `=`, caps | `roadmap/phase_9_hal_protocol.md` |
| `roadmap/PHASE 8 = HIVE SYSTEM (MULTI-MISSION ORCHESTRATION).md` | spaces, `=`, caps | `roadmap/phase_8_hive_protocol.md` |
| `roadmap/PHASE 10 — MASTER PROTOCOL.md` | spaces, em-dash | `roadmap/phase_10_master_protocol.md` |
| `roadmap/EEA Swarm Mission Planner_Roadmap_Ejecution.md` | spaces, mixed language | `roadmap/master_roadmap_execution_log.md` |
| `roadmap/roadmap_v2_final_clean.md` | ok-ish | `roadmap/roadmap_v2.md` |
| `architecture/SYSTEM BOUNDARY SPEC — ORIÓN PHASE 10.md` | spaces, accent, em-dash | `architecture/system_boundary_spec_phase10.md` |
| `architecture/PHASE-9.7-SEPARATION.md` | caps, hyphen style | `architecture/phase_9_7_separation_spec.md` |
| `architecture/Hardware Abstraction Layer (HAL).md` | spaces, parens | `architecture/hal_overview.md` |
| `validation_testing/decision_boundary_compliance_report.md` | missing phase prefix (it is Phase 8) | `validation/phase_8_decision_boundary_compliance_report.md` |

> **Note:** roadmap/spec files are referenced verbatim by name in prior task
> instructions and possibly in code/tests. Renames must be verified against
> references first (see §8, migration safety). This is why the migration is
> proposed, not auto-executed.

### 3.4 Raw output logs mixed with reports
- `validation_testing/phase_10a_e2e_validation_output.txt`
- `validation_testing/phase_10b_e2e_validation_output.txt`

**Recommendation:** move to `validation/logs/` to separate raw captures from
human-authored reports.

---

## 4. Recommended Target Structure

```
docs/
  README.md                      # NEW — top-level documentation index (navigational)
  system_overview.md
  simulation_vs_reality.md

  architecture/
    README.md                    # NEW — architecture index
    architecture.md              # canonical current architecture
    system_boundary_spec_phase10.md
    hal_overview.md
    hal_boundary_lock_spec_phase9.md
    phase_9_7_separation_spec.md
    decision_boundary_map_phase8.md
    decision_boundary_map_phase9.md
    phase7_design_proposal.md
    phase8_design.md
    phase9_design.md
    contracts/                   # NEW — grouping for formal contracts
      phase_9_7_simulation_contract.md
      phase_9_7_iov_contract.md
      phase_9_7_digital_twin_contract.md
    ui/                          # unchanged (Phase 10C.1 blueprint)
      phase_10c1_*.md
    history/                     # NEW — superseded architecture versions (preserved)
      001_architecture_v1.md
      002_architecture_v0.5.md
      v1_hardware_ready_architecture.md

  adr/                           # RENAMED from decisions/
    README.md                    # NEW — ADR index
    ADR-001-…  …  ADR-020-…

  audits/                        # RENAMED from audit/ (plural)
    README.md                    # NEW — audit index
    phase6_architecture_audit.md

  roadmap/
    README.md                    # NEW — roadmap index (marks canonical SSOT)
    master_roadmap_execution_log.md
    roadmap_v2.md
    phase_8_hive_protocol.md
    phase_9_hal_protocol.md
    phase_10_master_protocol.md

  validation/                    # RENAMED from validation_testing/
    README.md                    # NEW — validation index (per-phase matrix)
    phase_1_validation.md … phase_10c3_*.md   (consistent naming, see §6)
    logs/                        # NEW — raw captured outputs
      phase_10a_e2e_validation_output.txt
      phase_10b_e2e_validation_output.txt

  research/                      # unchanged (empty placeholder retained)
    .gitkeep
```

### Mapping to the requested target structure
| Requested | This proposal | Notes |
|-----------|---------------|-------|
| `architecture/` (boundaries, contracts, technical) | `architecture/` + `architecture/contracts/` | contracts grouped explicitly |
| `adr/` | `adr/` (from `decisions/`) | 20 ADRs migrated |
| `audits/` | `audits/` (from `audit/`) | pluralized + index |
| `roadmap/` | `roadmap/` | phase protocols, renamed |
| `validation/` | `validation/` (from `validation_testing/`) | reports + `logs/` |
| `research/` | `research/` | unchanged |

---

## 5. ADR Migration Plan (`docs/decisions/` → `docs/adr/`)

All 20 files in `docs/decisions/` are genuine Architecture Decision Records —
each is named `ADR-NNN-*.md` and follows ADR conventions. **All 20 should migrate.**

| Action | Detail |
|--------|--------|
| Move | `docs/decisions/ADR-001..020-*.md` → `docs/adr/` (filenames unchanged) |
| Add | `docs/adr/README.md` — index table (number, title, status, phase) |
| Verify | grep repo for references to `docs/decisions/` and update to `docs/adr/` |
| Preserve | Git history preserved via `git mv` |

No content changes to any ADR. No ADRs are obsolete (superseded ADRs, if any, keep
their record and are marked "Superseded by ADR-NNN" in the index only).

---

## 6. Validation Migration & Naming Plan (`validation_testing/` → `validation/`)

Target naming convention (consistent, lowercase, phase-prefixed):
- `phase_<X>_validation_report.md`
- `phase_<X>_boundary_report.md`
- `phase_<X>_replay_report.md`
- `phase_<X>_regression_report.md`
- raw logs → `validation/logs/phase_<X>_*.txt`

Representative renames:
| Current | Proposed |
|---------|----------|
| `decision_boundary_compliance_report.md` | `phase_8_decision_boundary_compliance_report.md` |
| `phase_10b_e2e_pipeline_validation_report.md` | `phase_10b_e2e_validation_report.md` |
| `phase_10b_boundary_compliance_report.md` | `phase_10b_boundary_report.md` |
| `phase_9_5_boundary_compliance_report.md` | `phase_9_5_boundary_report.md` |
| `phase_10a_e2e_validation_output.txt` | `logs/phase_10a_e2e_validation_output.txt` |
| `phase_10b_e2e_validation_output.txt` | `logs/phase_10b_e2e_validation_output.txt` |

The remaining `phase_N_validation.md` files are already consistent and require no
rename beyond moving into `validation/`.

---

## 7. Audit Review (`docs/audit/`)

- Only **one** real audit exists: `phase6_architecture_audit.md` (a genuine
  post-Phase 6 architecture consistency audit dated 2026-06-21).
- **No historical audits will be fabricated.**
- Proposal: rename directory to `audits/` and add `audits/README.md` indexing the
  single existing audit, leaving room for future entries.

---

## 8. Phase Documentation Completeness (Task 7)

Reports that **already exist** (information present) vs **gaps**:

| Phase | Validation docs present | Gap? |
|-------|-------------------------|------|
| 1–6 | `phase_1..6_validation.md`; Phase 6 also has architecture audit | Complete |
| 7 (7.1–7.4) | `phase_7_1..7_4_validation.md` | Complete |
| 8 (8.1–8.5 + final) | `phase_8_1..8_5_validation.md`, `phase_8_final_validation.md`, decision-boundary report | Complete |
| 9.1–9.4 | `phase_9_1_2_validation.md`, `phase_9_3_4_validation.md` | Complete |
| 9.5 | 5 reports (arch, boundary, enforcement, regression, impact) | Complete |
| 9.6 | `phase_9_final_certification_report.md`, `phase_9_system_freeze_report.md`, `phase_9_decision_boundary_compliance_final.md`, `phase_9_regression_summary_final.md`, `phase_9_architecture_stability_report.md` | Complete |
| 9.7 | contracts + isolation + leak-scan reports (currently under `architecture/`) | Present but **misfiled** — move reports to `validation/` |
| 10A | `phase_10a_validation_report.md` + e2e output | Complete |
| 10B | validation, boundary, replay, state-sync, e2e reports | Complete |
| 10C.1 | 7 architecture docs under `architecture/ui/` (design-only phase — no validation expected) | Complete (N/A validation) |
| 10C.2 | validation, architecture-compliance, regression reports | Complete |
| 10C.3 | validation, ui-interaction, clean-clone-fix reports | Complete |

**Conclusion:** No phase is missing its substantive documentation. The only true
"gaps" are **organizational** (9.7 reports misfiled) and **navigational** (no
indexes). No fabricated reports are required or created.

Optional additive documents worth generating (from existing information only):
- `validation/README.md` — a per-phase validation matrix (consolidates the table above).
- `docs/README.md` — master documentation index.

---

## 9. Migration Proposal & Safety (execution plan)

This audit **proposes** the migration; it does not execute file moves, because
several roadmap/spec filenames are referenced verbatim in task instructions and
may be referenced by code, tests, or other docs. Safe execution sequence:

1. `grep -r` the repo for every path/filename being moved or renamed; record references.
2. Use `git mv` for every move/rename (preserves history).
3. Update all discovered references (docs cross-links, any code/test string refs).
4. Add the new `README.md` index files.
5. Run the full test suite + a docs link-check to confirm nothing broke.
6. Single PR, reviewed before merge.

**Estimated churn:** ~30 renames/moves + 6 new index files, 0 deletions.

---

## 10. Deliverables Checklist

- [x] Documentation inventory (§2) — 94 files classified
- [x] Duplicates / obsolete / naming findings (§3)
- [x] Recommended future structure (§4)
- [x] ADR migration plan (§5)
- [x] Validation migration & naming plan (§6)
- [x] Audit review + index proposal (§7)
- [x] Phase documentation completeness / missing list (§8)
- [x] Migration proposal + safety plan (§9)

**No application code, architecture, or contracts were modified. No files were
deleted. Migration is awaiting approval before execution.**
