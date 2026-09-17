# AIA continuation — start here

**Single authoritative repository:** `Watchman77/solar-flare-aia-training`.

Read the [current status](AIA_RESEARCH_STATUS_2026-09-16.md) and [decision register](AIA_DECISION_REGISTER_2026-09-16.md). The internal combined proposal and correspondence are kept outside this public checkpoint; their publication has not been authorised. The [dated living-log addendum](RESEARCH_LOG_ADDENDUM_2026-09-16.md) is ready to reconcile with the existing narrative log; this package does not edit its original Word copy.

The 8 September plan, 15 September checkpoint and older results remain unchanged as history. The dated decision and status records explain updates without declaring proposed splits or scientific readiness frozen. The earlier image-only, magnetic-only and intermediate-fusion experiments constitute the completed baseline phase. The report-backed scope here is a new cross-cycle temporal extension, not a replacement of those baseline results. PINN/PIML remains a separately identified planned companion track; neither it nor a final cross-cycle model is claimed completed.

## Where each class of material belongs

| Location | Purpose |
|---|---|
| `reproducibility/continuation_20260916/` | Exact continuation source snapshot and original local-test sources/logs, preserving the earlier package layouts. Not a new Git repository. |
| `docs/research_audit/2026-09-16/` | Copied small report/summary/config/CSV bytes and completion markers; no image arrays or original bulk data. |
| `docs/research_audit/2026-09-16/checkpoint_copy_manifest.json` | Exact copied paths, hashes, original locations and deliberately excluded artifacts. |
| `~/solar_flare_aia/` | Current local clone of this repository. |
| `~/aia17_metadata_stage1/` | Existing generated arrays, original audit data, caches and detailed run outputs. Leave in place during consolidation. |
| Existing GCS bucket | Large scientific artifacts and externally verified backup destinations; a source citation is not a backup verification. |

Some continuation scripts still resolve dependencies/dated inputs from the original home layout. Copying their bytes does not refactor their paths or make every stage portable. Preserve that layout for current execution; a VM handover must explicitly configure/copy required artifacts and verify hashes. The snapshot is a reproducibility record, not an instruction to rerun every stage.

The original copy tool made local copies, added a pointer in README with a backup, and staged an explicit file list. A subsequent publication-selection step withheld the internal master proposal and its self-contained copying tool because that tool embeds the proposal. Both originals were preserved locally; the other scientific scripts and run evidence were not changed. The public checkpoint manifest records the revised selection. The copying tool is not included in this public source snapshot. The publication-selection procedure has not rerun any scientific computation. It does not commit, push, fetch, query storage, train, run original audits or delete originals. Staging is not publication. Review the staged diff and then commit/push this checkpoint once; do not upload the whole home directory, a virtual environment, `.config`, credentials, `.git`, or a blanket data directory.

Large artifacts listed as excluded remain outside this checkpoint. Their hashes may be copied from their original completion markers, but their contents are not rehashed or backed up by this tool. Original completion markers describe the complete original run, not the subset of files copied into Git.

Original test sources/logs are preserved with their package origins. These tests are not rerun by the copier and are not automatically a new integrated CI suite. Never add historical test counts together and describe them as independent scientific validations.

The task next in line is the first specified SHARP development baseline; no new archive extraction or split search is requested by this documentation update.
