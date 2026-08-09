from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import pandas as pd
import time

ROOT = Path("/home/abmoses2000/solar_flare_aia")
CACHE_ROOT = ROOT / "training/aia_cache"
FOLD_PATH = ROOT / "training/fusion_manifests/aia_sharp_goes_fusion_fold_assignments_2013_2015.csv"
HISTORY_PATH = ROOT / "results/metrics/sharp_temporal_leakage_audit_temporal_window_per_sample.csv"
FAILED_PATH = ROOT / "logs/prefetch_fusion_allfold_failed.txt"

MAX_WORKERS = 16
RETRIES = 3

df = pd.read_csv(
    FOLD_PATH,
    usecols=["fusion_fold_id", "fusion_split", "sample_id", "gcp_path", "official_label_48h_final"]
)
df["sample_id"] = df["sample_id"].astype(str)

hist = pd.read_csv(HISTORY_PATH, usecols=["sample_id", "meets_min_history_24h"])
hist["sample_id"] = hist["sample_id"].astype(str)

df = df.merge(hist, on="sample_id", how="left")
df = df[df["meets_min_history_24h"].fillna(False)].copy()

u = df.drop_duplicates("gcp_path").copy()

def dest_for_gcs(gcs_path: str) -> Path:
    return CACHE_ROOT / gcs_path.replace("gs://", "").lstrip("/")

jobs = []
for g in u["gcp_path"].dropna().astype(str):
    dst = dest_for_gcs(g)
    if not dst.exists() or dst.stat().st_size == 0:
        jobs.append((g, dst))

print("Rows after 24h filter:", len(df), flush=True)
print("Unique GCS files:", len(u), flush=True)
print("Missing downloads:", len(jobs), flush=True)
print("Workers:", MAX_WORKERS, flush=True)

def download_one(item):
    src, dst = item
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and dst.stat().st_size > 0:
        return ("cached", src)

    for attempt in range(1, RETRIES + 1):
        cmd = ["gsutil", "-q", "cp", src, str(dst)]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return ("ok", src)
        time.sleep(2 * attempt)

    return ("failed", src)

failed = []
done = 0
start = time.time()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futures = [ex.submit(download_one, j) for j in jobs]
    for fut in as_completed(futures):
        status, src = fut.result()
        done += 1
        if status == "failed":
            failed.append(src)

        if done % 100 == 0 or done == len(jobs):
            elapsed = time.time() - start
            rate = done / max(elapsed, 1)
            print(
                f"Progress: {done}/{len(jobs)} | failed={len(failed)} | rate={rate:.2f} files/s",
                flush=True
            )

FAILED_PATH.write_text("\n".join(failed), encoding="utf-8")
print("DONE", flush=True)
print("Failed:", len(failed), flush=True)
print("Failed list:", FAILED_PATH, flush=True)
