#!/usr/bin/env python3
"""17C engineering integration: saved real AIA sequences + exact lagged SHARP rows.

This is a bounded CPU model-interface/gradient test, NOT a forecasting benchmark.
It performs ten disposable weight updates on the two designated TRAIN examples.
Validation examples are forward-only; no test/calibration targets are loaded.
No network, cloud, Git, relabeling, inventory scan, or training-release operation.

Default inputs are the existing September 16 canary and frozen Stage-1 source lock.
Neither unknown contributing-time bounds nor label-follow-up flags are waived.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time
import zipfile

import numpy as np

VERSION = "17c-aia-sharp-model-integration-v1"
CHANNELS = [94, 131, 171, 193, 211, 335]
FEATURES = ["MEANGBZ", "MEANGAM", "MEANGBT", "MEANGBH", "MEANJZD",
            "TOTUSJZ", "MEANALP", "MEANJZH", "ABSNJZH", "SAVNCPP",
            "MEANSHR", "SHRGT45", "R_VALUE", "USFLUX", "TOTPOT"]
LAGS = [288, 192, 96]
STATUS = "MULTIMODAL_ENGINEERING_CHECK_PASSED_NOT_A_FORECAST_BENCHMARK"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path, limit: int = 8 * 1024**2) -> dict:
    require(path.is_file(), f"Missing local file: {path}. Do not redownload the archive.")
    require(path.stat().st_size <= limit, f"Unexpectedly large JSON: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"Expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_file(path: Path, expected_hash: str, max_bytes: int) -> str:
    require(path.is_file(), f"Required cached file is missing: {path}")
    require(re.fullmatch(r"[0-9a-f]{64}", expected_hash or "") is not None,
            f"Missing/invalid recorded SHA256 for {path.name}")
    require(0 < path.stat().st_size <= max_bytes, f"Size guard failed for {path}")
    got = digest(path)
    require(got == expected_hash, f"Checksum mismatch for {path}; nothing repaired.")
    return got


def tai_clock(value: str) -> datetime:
    """Parse clock fields only; both sides of every join are explicitly TAI.

    This does not reinterpret a TAI value as UTC. All canary dates are 2011/12/14,
    and no leap-second field is accepted by this exact-slot join.
    """
    require(isinstance(value, str) and value.endswith("_TAI"),
            f"Expected explicit raw TAI timestamp, received {value!r}")
    return datetime.strptime(value, "%Y.%m.%d_%H:%M:%S_TAI")


def integral(value: str) -> int:
    x = float(value)
    require(math.isfinite(x) and x.is_integer(), f"Invalid integer identifier: {value!r}")
    return int(x)


def checked_plan(plan: dict, report: dict) -> list[dict]:
    selected = plan.get("selected_targets", [])
    require(len(selected) == 4, "Expected exactly four existing canary targets.")
    roles = Counter(s.get("canary_role") for s in selected)
    require(roles == {"train": 2, "model_validation": 2},
            "Only two train and two model_validation examples are permitted.")
    require(len({s["target_sample_id"] for s in selected}) == 4, "Duplicate target IDs.")
    require(len({s["region_component_id"] for s in selected}) == 4,
            "The four canary targets must belong to different region components.")
    require(report.get("test_samples_loaded") == 0, "Source canary loaded test targets.")
    require(report.get("recorded_time_screens_pass") is True, "Source recorded-time screen did not pass.")
    require(report.get("batch_shape") == [4, 3, 6, 512, 512], "Unexpected source batch shape.")
    require(report.get("training_authorised") is False, "Expected the unapproved engineering batch.")
    result_ids = [s["target_sample_id"] for s in report.get("sequence_results", [])]
    require(result_ids == [s["target_sample_id"] for s in selected], "Report/plan target order mismatch.")
    for s in selected:
        require(s["stored_year"] < 2020, "Cycle-25 observations cannot enter this integration test.")
        require(s["original_label_48h_final"] in (0, 1), "Invalid manifest label.")
        frames = s.get("frames", [])
        require([f["lag_minutes"] for f in frames] == LAGS, "Unexpected lag order.")
        t = tai_clock(s["issue_raw_TAI"])
        for f in frames:
            ft = tai_clock(f["raw_T_REC_TAI"])
            require((t - ft).total_seconds() == f["lag_minutes"] * 60,
                    "Historical TAI slot does not match requested lag.")
            require(f["object_status"] == "EXACT_NONEMPTY_OBJECT", "Unverified inventory status.")
            m = re.fullmatch(r"\d{8}_\d{4}_HARP(\d+)_NOAA(\d+)", f["history_sample_id"])
            require(m is not None and int(m[1]) == s["HARPNUM"] and int(m[2]) == s["NOAA_AR_clean"],
                    "Historical image belongs to a different HARP/NOAA region.")
    require(report["manifest_targets"] == [s["original_label_48h_final"] for s in selected],
            "Report labels do not match plan labels.")
    return selected


def select_sharp(csv_path: Path, selected: list[dict]) -> tuple[np.ndarray, dict]:
    """Stream cached raw SHARP once; retain exactly the requested twelve records.

    No forward filling, approximate matching, target-time row, labels as features,
    or substitution of TOTUSJZ for the absent TOTUSJH is permitted.
    """
    keys = {}
    for i, s in enumerate(selected):
        for j, frame in enumerate(s["frames"]):
            key = (int(s["HARPNUM"]), tai_clock(frame["raw_T_REC_TAI"]))
            require(key not in keys, "Duplicate requested SHARP key.")
            keys[key] = (i, j, frame, s)
    x = np.full((4, 3, len(FEATURES)), np.nan, dtype=np.float64)
    matches, evidence = {}, []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        require(len(columns) == len(set(columns)), "Duplicate SHARP CSV column names.")
        missing = sorted(set(["HARPNUM", "T_REC"] + FEATURES) - set(columns))
        require(not missing, f"Required SHARP columns absent: {missing}; no features invented.")
        for row_number, row in enumerate(reader, 1):
            if row_number % 200000 == 0:
                print(f"  Local SHARP scan: {row_number:,} records; retaining only twelve requested keys.", flush=True)
            try:
                harp = integral(row["HARPNUM"])
            except (ValueError, TypeError):
                continue
            if harp not in {k[0] for k in keys}:
                continue
            # Explicit TAI is required on records for the selected HARPs.
            key = (harp, tai_clock(row["T_REC"]))
            if key not in keys:
                continue
            require(key not in matches, f"More than one SHARP row for {key}; no duplicate chosen.")
            matches[key] = row_number
            i, j, frame, target = keys[key]
            noaa_fields = {k: row.get(k, "") for k in ("NOAA_AR_clean", "NOAA_AR", "NOAA_ARS") if k in columns}
            expected = int(target["NOAA_AR_clean"])
            explicit = noaa_fields.get("NOAA_AR_clean", "").strip()
            if explicit and explicit.lower() not in {"nan", "none"}:
                require(integral(explicit) == expected, f"SHARP NOAA_AR_clean mismatch for {key}")
            # NOAA_ARS is retained as provenance; HARP+explicit TAI is the join key.
            for f_idx, feature in enumerate(FEATURES):
                try:
                    value = float(row[feature])
                    x[i, j, f_idx] = value if math.isfinite(value) else np.nan
                except (ValueError, TypeError):
                    pass
            evidence.append({"target_sample_id": target["target_sample_id"],
                             "history_sample_id": frame["history_sample_id"],
                             "source_csv_record_number": row_number, "HARPNUM": harp,
                             "T_REC": row["T_REC"], "lag_minutes": frame["lag_minutes"],
                             "noaa_fields": noaa_fields, "QUALITY_raw": row.get("QUALITY"),
                             "finite_feature_count": int(np.isfinite(x[i, j]).sum()),
                             "missing_feature_names": [f for f,v in zip(FEATURES,x[i,j]) if not np.isfinite(v)],
                             "maximum_contributing_time_verified": False,
                             "historical_product_availability_verified": False})
    absent = [f"HARP{k[0]} {k[1].isoformat()}" for k in keys if k not in matches]
    require(not absent, f"Exact historical SHARP records absent: {absent}; no replacement made.")
    return x, {"feature_order": FEATURES, "preferred_TOTUSJH_present_in_source": "TOTUSJH" in columns,
               "TOTUSJH_used": False, "quality_filter_applied": False,
               "quality_note": "QUALITY retained for review; this engineering join does not authorise a science quality policy.",
               "join_key": ["HARPNUM", "explicit_TAI_T_REC"], "matched_record_count": len(matches),
               "records": sorted(evidence, key=lambda r:(r["target_sample_id"],-r["lag_minutes"])),
               "nominal_cutoff": "latest record is issue TAI minus 96 minutes",
               "is_24hour_aggregate_branch": False}


def train_only_preprocess(raw: np.ndarray, train_indices: list[int]) -> tuple[np.ndarray, dict]:
    require(raw.ndim == 3 and raw.shape[2] == len(FEATURES), "Invalid SHARP feature tensor.")
    fit = raw[train_indices].reshape(-1, raw.shape[-1])
    all_missing = ~np.isfinite(fit).any(axis=0)
    require(not all_missing.any(), f"Features wholly missing in training examples: {[f for f,m in zip(FEATURES,all_missing) if m]}")
    med = np.nanmedian(fit, axis=0)
    filled_fit = np.where(np.isfinite(fit), fit, med)
    mean = filled_fit.mean(axis=0)
    scale = filled_fit.std(axis=0)
    constant = scale < 1e-12
    scale[constant] = 1.0
    normalized = (np.where(np.isfinite(raw), raw, med) - mean) / scale
    require(np.isfinite(normalized).all() and np.max(np.abs(normalized)) < np.finfo(np.float32).max,
            "Nonfinite/overflowed transformed SHARP values.")
    return normalized.astype(np.float32), {"fit_indices": train_indices,
           "fit_historical_rows": len(filled_fit), "feature_order": FEATURES,
           "median": med.tolist(), "mean": mean.tolist(), "scale": scale.tolist(),
           "constant_training_features": [f for f,c in zip(FEATURES,constant) if c],
           "missing_values_by_sequence": np.sum(~np.isfinite(raw), axis=(1,2)).tolist(),
           "purpose": "two-target engineering scaling only; NEVER reuse for a full experiment"}


def make_model(n_features: int):
    import torch
    from torch import nn

    class TemporalAiaSharpNet(nn.Module):
        """Small CPU integration network, not the selected final paper architecture."""
        def __init__(self):
            super().__init__()
            self.aia_encoder = nn.Sequential(
                nn.Conv2d(6, 16, 3, stride=2, padding=1), nn.GroupNorm(4,16), nn.SiLU(),
                nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.GroupNorm(4,32), nn.SiLU(),
                nn.AdaptiveAvgPool2d((2,2)), nn.Flatten(), nn.Linear(128,32), nn.SiLU())
            self.aia_temporal = nn.LSTM(32, 24, batch_first=True)
            self.sharp_temporal = nn.LSTM(n_features, 16, batch_first=True)
            self.fusion = nn.Sequential(nn.Linear(40,16), nn.SiLU(), nn.Linear(16,1))

        def forward(self, images, sharp):
            require(images.ndim == 5 and images.shape[1:3] == (3,6), "Expected B,T=3,C=6,H,W.")
            require(sharp.shape == (images.shape[0],3,n_features), "SHARP/AIA batch mismatch.")
            b,t,c,h,w = images.shape
            z = self.aia_encoder(images.reshape(b*t,c,h,w)).reshape(b,t,-1)
            _, (a,_) = self.aia_temporal(z)
            _, (m,_) = self.sharp_temporal(sharp)
            return self.fusion(torch.cat([a[-1],m[-1]],dim=-1)).squeeze(-1)
    return TemporalAiaSharpNet()


def smoke_test(images: np.ndarray, sharp: np.ndarray, labels: np.ndarray,
               roles: list[str], steps: int = 10) -> dict:
    import torch
    import torch.nn.functional as F
    require(1 <= steps <= 10, "Engineering updates are bounded to 1..10.")
    require(Counter(roles) == {"train":2, "model_validation":2}, "Role counts changed.")
    train_indices = [i for i,r in enumerate(roles) if r == "train"]
    require(sorted(labels[train_indices].tolist()) == [0,1], "Training canary must contain one of each label.")
    torch.set_num_threads(2)
    torch.manual_seed(17092026)
    torch.use_deterministic_algorithms(True)
    # Strictly CPU: no .cuda(), pretrained downloads or torchvision imports.
    x = torch.from_numpy(np.asarray(images).copy()).float()
    n,t,c,h,w = x.shape
    x = F.interpolate(x.reshape(n*t,c,h,w), size=(64,64), mode="area").reshape(n,t,c,64,64)
    # Fixed geometric resize only; no fitted image normalization or augmentation.
    s = torch.from_numpy(sharp.copy())
    y_train = torch.from_numpy(labels[train_indices].astype(np.float32))
    model = make_model(sharp.shape[-1]).cpu()
    before = {k:v.detach().clone() for k,v in model.named_parameters()}
    optimizer = torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4)
    loss_function = torch.nn.BCEWithLogitsLoss()
    losses, grad_rows = [], []
    started = time.monotonic()
    for step in range(steps):
        require(time.monotonic() - started < 180, "CPU engineering time budget exceeded.")
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x[train_indices],s[train_indices])
        loss = loss_function(logits,y_train)
        require(bool(torch.isfinite(loss)), "Nonfinite engineering loss.")
        loss.backward()
        gradient = {}
        for prefix in ("aia_encoder", "aia_temporal", "sharp_temporal", "fusion"):
            values = [p.grad for name,p in model.named_parameters() if name.startswith(prefix) and p.grad is not None]
            require(values and all(bool(torch.isfinite(g).all()) for g in values), f"Missing/nonfinite {prefix} gradient.")
            norm = math.sqrt(sum(float(torch.sum(g.double()**2)) for g in values))
            require(norm > 0, f"Zero aggregate gradient in {prefix}.")
            gradient[prefix] = norm
        torch.nn.utils.clip_grad_norm_(model.parameters(),max_norm=5.0,error_if_nonfinite=True)
        optimizer.step()
        losses.append(float(loss.detach()))
        grad_rows.append(gradient)
    changed = {prefix:any(not torch.equal(before[k],p.detach()) for k,p in model.named_parameters() if k.startswith(prefix))
               for prefix in ("aia_encoder", "aia_temporal", "sharp_temporal", "fusion")}
    require(all(changed.values()), "A branch's parameters did not update.")
    model.eval()
    with torch.inference_mode():
        # Both validation cases are FORWARD ONLY. Their labels do not enter a loss.
        output = model(x,s)
    require(output.shape == (4,) and bool(torch.isfinite(output).all()), "Invalid logits from forward pass.")
    state_hash = hashlib.sha256()
    for name,p in model.state_dict().items():
        state_hash.update(name.encode()); state_hash.update(p.cpu().numpy().tobytes())
    return {"device":"cpu", "steps":steps, "train_indices":train_indices,
            "validation_weight_updates":0, "test_samples_loaded":0,
            "input_model_aia_shape":list(x.shape), "input_sharp_shape":list(s.shape),
            "output_shape":list(output.shape), "all_logits_finite":True,
            "finite_nonzero_branch_gradients":True, "branch_parameters_changed":changed,
            "debug_training_losses_not_metrics":losses, "branch_gradient_norms":grad_rows,
            "parameter_count":sum(p.numel() for p in model.parameters()),
            "final_parameter_digest_for_regression_only":state_hash.hexdigest(),
            "model_weights_saved":False, "model_weights_reused_for_research":False,
            "validation_labels_used_for_loss_or_selection":False,
            "forecasting_performance_metrics_calculated":False,
            "architecture":"small shared CNN + AIA LSTM + SHARP LSTM + fusion MLP",
            "checkpoint_note":"Disposable debug weights are discarded; no model selected."}


def run(canary_dir: Path, lock_path: Path, output_root: Path) -> dict:
    import torch
    require(torch.__version__.split('+')[0] == '2.10.0',
            f"Expected pinned PyTorch 2.10.0, found {torch.__version__}.")
    print("===== 17C AIA + SHARP MODEL INTEGRATION =====",flush=True)
    print("Existing four-sequence batch only. CPU debug updates; no forecast scores or test data.",flush=True)
    complete = load_json(canary_dir/'COMPLETE.json')
    hashes = complete['output_sha256']
    inputs = {str(canary_dir/'COMPLETE.json'):digest(canary_dir/'COMPLETE.json')}
    for filename in ('canary_plan.json','real_sequence_canary_report.json','engineering_batch.npy','manifest_targets.npy'):
        inputs[str(canary_dir/filename)] = verify_file(canary_dir/filename,hashes.get(filename,''),100*1024**2)
    plan = load_json(canary_dir/'canary_plan.json')
    source_report = load_json(canary_dir/'real_sequence_canary_report.json')
    selected = checked_plan(plan,source_report)
    images = np.load(canary_dir/'engineering_batch.npy',mmap_mode='r',allow_pickle=False)
    labels = np.load(canary_dir/'manifest_targets.npy',allow_pickle=False)
    require(images.shape == (4,3,6,512,512) and images.dtype == np.float32, "Unexpected stored image batch.")
    require(np.isfinite(images).all(), "Nonfinite saved image batch.")
    require(labels.shape == (4,) and labels.tolist() == source_report['manifest_targets'], "Saved target mismatch.")
    lock = load_json(lock_path)
    inputs[str(lock_path)] = digest(lock_path)
    entries = [e for e in lock.get('sources',[]) if e.get('id') == 'sharp96']
    require(len(entries) == 1, "Expected one sharp96 source in recorded lock.")
    entry = entries[0]
    path = Path(entry['local_path']).expanduser()
    print("Verifying and reading the already-cached raw SHARP CSV; no download.",flush=True)
    inputs[str(path)] = verify_file(path,entry.get('sha256',''),350*1024**2)
    require(path.stat().st_size == entry['size_bytes'], "SHARP source-size mismatch.")
    raw, sharp_info = select_sharp(path,selected)
    roles = [s['canary_role'] for s in selected]
    train_idx = [i for i,r in enumerate(roles) if r=='train']
    normalized, scaler = train_only_preprocess(raw,train_idx)
    print(f"Exact SHARP rows matched: {sharp_info['matched_record_count']}; shape {list(raw.shape)}.",flush=True)
    print("Running ten CPU debug updates on the two train examples only...",flush=True)
    model_result = smoke_test(images,normalized,labels,roles)
    output_root.mkdir(parents=True,exist_ok=True)
    require(shutil.disk_usage(output_root).free > 128*1024**2, "Insufficient output disk reserve.")
    now = datetime.now(timezone.utc)
    out = output_root/now.strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(exist_ok=False)
    report = {"version":VERSION,"status":STATUS,"created_utc":now.isoformat(),
        "inputs_sha256":inputs,"script_sha256":digest(Path(__file__).resolve()),
        "canary_sequence_count":4,"original_batch_shape":list(images.shape),
        "target_sample_ids":[s['target_sample_id'] for s in selected],"roles":roles,
        "targets_from_manifest":labels.tolist(),"sharp":sharp_info,"preprocessing":scaler,
        "model_engineering":model_result,
        "scientific_clearance":{"official_training_authorised":False,
            "prior_contributing_time_clearance":source_report['strict_contributing_time_clearance'],
            "label_validity_and_followup_certified":source_report['label_validity_and_followup_certified'],
            "SHARP_contributing_time_and_historical_availability_verified":False,
            "GOES_input_branch_included":False,"UQ_or_calibration_experiment_completed":False,
            "no_claim_of_model_skill":True},
        "protocol":{"scope":"ENGINEERING_ONLY","split_dates_changed":False,"split_dates_frozen":False,
            "full_fit_design":"Broader eligible Cycle-24 fitting including 2015-2017 still to be implemented; provisional canary roles are not the final-fit specification.",
            "primary_test":"2021-2025 held out","additional_test":"eligible covered portion of 2026 held out",
            "PINN_PIML":"separate track, not included","final_SHARP_history_window":"not selected by this three-slot interface test"},
        "operations":{"network_requests":0,"cloud_writes":0,"git_operations":0,
            "original_labels_changed":False,"image_downloads":0,"disposable_train_weight_updates":10},
        "versions":{"python":sys.version,"numpy":np.__version__,"torch":torch.__version__}}
    write_json(out/'model_integration_report.json',report)
    np.save(out/'sharp_three_slot_raw.npy',raw,allow_pickle=False)
    np.save(out/'sharp_three_slot_scaled_DEBUG_ONLY.npy',normalized,allow_pickle=False)
    write_json(out/'DEBUG_ONLY_scaler.json',scaler)
    note = ("# 17C AIA-SHARP engineering integration\n\n"
            "Four real canary targets were joined to twelve exact HARPNUM/raw-TAI SHARP records. "
            "No target-time SHARP row, embedded NPZ label, forward fill or guessed feature was used.\n\n"
            "A compact CNN/LSTM + SHARP-LSTM fusion network received ten disposable CPU updates on "
            "the TWO TRAIN examples. Validation was forward-only. This is not a forecasting benchmark; "
            "no performance, calibration or UQ metric and no reusable model weights were produced.\n\n"
            "The original image, source and label clearances are unchanged. The broader Cycle-24 final-fit "
            "allocation, including 2015-2017, is not implemented by this debug run. 2021-2025 and the "
            "available 2026 portion remain held-out evaluation targets. PINN/PIML stays separate.\n")
    (out/'research_log_model_integration.md').write_text(note,encoding='utf-8')
    output_hashes = {p.name:digest(p) for p in out.iterdir() if p.is_file()}
    write_json(out/'COMPLETE.json',{"status":STATUS,"output_sha256":output_hashes})
    with zipfile.ZipFile(out/'model_integration_summary.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for n in ('model_integration_report.json','DEBUG_ONLY_scaler.json','research_log_model_integration.md','COMPLETE.json'):
            z.write(out/n,n)
    print("\n===== MULTIMODAL ENGINEERING RESULTS =====")
    print("AIA original batch:",list(images.shape),"| SHARP batch:",list(raw.shape))
    print("CPU model input:",model_result['input_model_aia_shape'],"| logits:",model_result['output_shape'])
    print("Finite nonzero gradients in both temporal branches and fusion: PASS")
    print("Disposable train updates: 10 | validation updates: 0 | test examples: 0")
    print("No forecasting performance scores, calibration, UQ or final-fit selection.")
    print("STATUS:",STATUS)
    print("REPORT:",out/'model_integration_report.json')
    print("SUMMARY:",out/'model_integration_summary.zip')
    return report


def main(argv=None) -> int:
    h=Path.home()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--canary-run',type=Path,default=h/'aia17_metadata_stage1/real_sequence_canary_v1/reports/20260916T172352521004Z')
    p.add_argument('--source-lock',type=Path,default=h/'solar_flare_aia/docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json')
    p.add_argument('--output-root',type=Path,default=h/'aia17_metadata_stage1/model_integration_v1/reports')
    a=p.parse_args(argv)
    try:
        run(a.canary_run,a.source_lock,a.output_root)
        return 0
    except (Exception,KeyboardInterrupt) as exc:
        print(f"\nSTOP: {type(exc).__name__}: {exc}",file=sys.stderr)
        print("Originals and prior canary remain unchanged. No fallback labels, sources or clearance.",file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
