import csv, hashlib, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE = Path("cache/gcs_npz_alexnet_fold2015")
CACHE.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    "results/metrics/aia_alexnet_fold2015_largecap_benchmark_largecap_train_samples.csv",
    "results/metrics/aia_alexnet_fold2015_largecap_benchmark_largecap_val_samples.csv",
    "results/metrics/aia_alexnet_fold2015_largecap_benchmark_largecap_test_samples.csv",
]

WORKERS = 8

def local_path(src):
    return CACHE / (hashlib.md5(src.encode()).hexdigest() + "_" + Path(src).name)

def required_paths():
    out = []
    for f in SAMPLES:
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                out.append(row["gcp_path"])
    return sorted(set(out))

def copy_one(src):
    dst = local_path(src)
    if dst.exists() and dst.stat().st_size > 0:
        return "cached", src

    tmp = Path(str(dst) + ".tmp")
    if tmp.exists():
        tmp.unlink()

    cmd = ["gcloud", "storage", "cp", src, str(tmp)]
    r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if r.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        return "failed", src, r.stderr[-500:]

    tmp.rename(dst)
    return "downloaded", src

def main():
    req = required_paths()
    missing = [p for p in req if not local_path(p).exists()]

    print(f"required={len(req)}", flush=True)
    print(f"missing_start={len(missing)}", flush=True)
    print(f"workers={WORKERS}", flush=True)

    counts = {"cached": 0, "downloaded": 0, "failed": 0}
    failures = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(copy_one, p) for p in missing]
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            status = res[0]
            counts[status] += 1

            if status == "failed":
                failures.append(res)

            if i % 25 == 0 or status == "failed":
                print(
                    f"done={i}/{len(missing)} "
                    f"downloaded={counts['downloaded']} "
                    f"cached={counts['cached']} "
                    f"failed={counts['failed']} "
                    f"elapsed_min={(time.time()-start)/60:.1f}",
                    flush=True,
                )

    print("FINAL", counts, flush=True)

    if failures:
        Path("results/metrics").mkdir(parents=True, exist_ok=True)
        with open("results/metrics/06b_prefetch_failures.txt", "w") as fh:
            for item in failures:
                fh.write(repr(item) + "\n")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
