import hashlib
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE = Path("cache/gcs_npz_alexnet_fold2015")
MISSING_LIST = Path("results/metrics/aia_resnet18_physics_safe_fold2015_fullnatural_missing_gcs_paths.txt")
FAIL_LOG = Path("results/metrics/aia_resnet18_fullnatural_prefetch_failures_retry.txt")

WORKERS = 4
MAX_RETRIES = 3
MIN_FREE_GB = 30.0

CACHE.mkdir(parents=True, exist_ok=True)

def free_gb():
    return shutil.disk_usage(".").free / (1024 ** 3)

def local_path(src):
    return CACHE / (hashlib.md5(src.encode("utf-8")).hexdigest() + "_" + Path(src).name)

def copy_one(src):
    dst = local_path(src)

    if dst.exists() and dst.stat().st_size > 0:
        return ("cached", src, "")

    if free_gb() < MIN_FREE_GB:
        return ("low_disk", src, f"free_gb={free_gb():.2f}")

    last_err = ""

    for attempt in range(1, MAX_RETRIES + 1):
        tmp = Path(str(dst) + ".tmp")

        if tmp.exists():
            tmp.unlink()

        cmd = ["gcloud", "storage", "cp", src, str(tmp)]
        r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.rename(dst)
            return ("downloaded", src, "")

        last_err = r.stderr[-800:]

        if tmp.exists():
            tmp.unlink()

        time.sleep(3 * attempt)

    return ("failed", src, last_err)

def main():
    paths = [p.strip() for p in MISSING_LIST.read_text().splitlines() if p.strip()]
    todo = [p for p in paths if not local_path(p).exists()]

    print(f"missing_list_paths: {len(paths)}", flush=True)
    print(f"todo_start: {len(todo)}", flush=True)
    print(f"workers: {WORKERS}", flush=True)
    print(f"max_retries: {MAX_RETRIES}", flush=True)
    print(f"free_gb_start: {free_gb():.2f}", flush=True)

    counts = {"downloaded": 0, "cached": 0, "failed": 0, "low_disk": 0}
    failures = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(copy_one, src) for src in todo]

        for i, fut in enumerate(as_completed(futures), 1):
            status, src, err = fut.result()
            counts[status] += 1

            if status in ("failed", "low_disk"):
                failures.append((status, src, err))

            if i % 100 == 0 or status in ("failed", "low_disk"):
                elapsed = (time.time() - start) / 60
                print(
                    f"done={i}/{len(todo)} "
                    f"downloaded={counts['downloaded']} "
                    f"cached={counts['cached']} "
                    f"failed={counts['failed']} "
                    f"low_disk={counts['low_disk']} "
                    f"free_gb={free_gb():.2f} "
                    f"elapsed_min={elapsed:.1f}",
                    flush=True,
                )

            if counts["low_disk"] > 0:
                print("STOPPING: free disk is below safety limit.", flush=True)
                break

    print("FINAL:", counts, flush=True)

    if failures:
        with FAIL_LOG.open("w") as f:
            for item in failures:
                f.write(repr(item) + "\n")
        print(f"failures_written: {FAIL_LOG}", flush=True)

if __name__ == "__main__":
    main()
