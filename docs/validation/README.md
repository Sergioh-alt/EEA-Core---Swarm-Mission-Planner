# Validation & Testing Reports

Phase validation, boundary-compliance, replay, and regression reports, plus raw
captured logs. Migrated from `docs/validation_testing/` (Git history preserved).
The two Phase 9.7 reports here were moved from `docs/architecture/`.

Raw captured test output lives in [`logs/`](logs/).

## Per-Phase Validation Matrix

| Phase | Reports |
|-------|---------|
| 1 | [`phase_1_validation.md`](phase_1_validation.md) |
| 2 | [`phase_2_validation.md`](phase_2_validation.md) |
| 3 | [`phase_3_validation.md`](phase_3_validation.md) |
| 4 | [`phase_4_validation.md`](phase_4_validation.md) |
| 5 | [`phase_5_validation.md`](phase_5_validation.md) |
| 6 | [`phase_6_validation.md`](phase_6_validation.md) |
| 7.1–7.4 | [`phase_7_1_validation.md`](phase_7_1_validation.md), [`phase_7_2_validation.md`](phase_7_2_validation.md), [`phase_7_3_validation.md`](phase_7_3_validation.md), [`phase_7_4_validation.md`](phase_7_4_validation.md) |
| 8.1–8.5 | [`phase_8_1_validation.md`](phase_8_1_validation.md), [`phase_8_2_validation.md`](phase_8_2_validation.md), [`phase_8_3_validation.md`](phase_8_3_validation.md), [`phase_8_4_validation.md`](phase_8_4_validation.md), [`phase_8_5_validation.md`](phase_8_5_validation.md) |
| 8 (final) | [`phase_8_final_validation.md`](phase_8_final_validation.md), [`decision_boundary_compliance_report.md`](decision_boundary_compliance_report.md) _(Phase 8 decision-boundary audit)_ |
| 9.1–9.4 | [`phase_9_1_2_validation.md`](phase_9_1_2_validation.md), [`phase_9_3_4_validation.md`](phase_9_3_4_validation.md) |
| 9.5 | [`phase_9_5_architecture_validation_report.md`](phase_9_5_architecture_validation_report.md), [`phase_9_5_boundary_compliance_report.md`](phase_9_5_boundary_compliance_report.md), [`phase_9_5_hal_enforcement_report.md`](phase_9_5_hal_enforcement_report.md), [`phase_9_5_regression_summary.md`](phase_9_5_regression_summary.md), [`phase_9_5_architecture_impact_summary.md`](phase_9_5_architecture_impact_summary.md) |
| 9.6 (certification & freeze) | [`phase_9_final_certification_report.md`](phase_9_final_certification_report.md), [`phase_9_system_freeze_report.md`](phase_9_system_freeze_report.md), [`phase_9_decision_boundary_compliance_final.md`](phase_9_decision_boundary_compliance_final.md), [`phase_9_regression_summary_final.md`](phase_9_regression_summary_final.md), [`phase_9_architecture_stability_report.md`](phase_9_architecture_stability_report.md) |
| 9.7 (separation) | [`phase_9_7_architecture_isolation_report.md`](phase_9_7_architecture_isolation_report.md), [`phase_9_7_cross_layer_leak_scan.md`](phase_9_7_cross_layer_leak_scan.md) |
| 10A | [`phase_10a_validation_report.md`](phase_10a_validation_report.md), [`logs/phase_10a_e2e_validation_output.txt`](logs/phase_10a_e2e_validation_output.txt) |
| 10B | [`phase_10b_validation_report.md`](phase_10b_validation_report.md), [`phase_10b_boundary_compliance_report.md`](phase_10b_boundary_compliance_report.md), [`phase_10b_replay_validation_report.md`](phase_10b_replay_validation_report.md), [`phase_10b_state_sync_report.md`](phase_10b_state_sync_report.md), [`phase_10b_e2e_pipeline_validation_report.md`](phase_10b_e2e_pipeline_validation_report.md), [`logs/phase_10b_e2e_validation_output.txt`](logs/phase_10b_e2e_validation_output.txt) |
| 10C.2 | [`phase_10c2_validation_report.md`](phase_10c2_validation_report.md), [`phase_10c2_architecture_compliance_report.md`](phase_10c2_architecture_compliance_report.md), [`phase_10c2_regression_report.md`](phase_10c2_regression_report.md) |
| 10C.3 | [`phase_10c3_validation_report.md`](phase_10c3_validation_report.md), [`phase_10c3_ui_interaction_report.md`](phase_10c3_ui_interaction_report.md), [`phase_10c3_clean_clone_fix_report.md`](phase_10c3_clean_clone_fix_report.md) |

> Phase 10C.1 was a design-only phase; its documentation lives under
> [`../architecture/ui/`](../architecture/ui/) and has no validation report by design.

## Known follow-up (code, out of scope for this docs-only migration)

`validation_e2e_phase10b.py` hardcodes the old output path
`docs/validation_testing/phase_10b_e2e_validation_output.txt`. It should be
updated to `docs/validation/logs/phase_10b_e2e_validation_output.txt` in a
separate **code** PR (this migration does not modify source code).
