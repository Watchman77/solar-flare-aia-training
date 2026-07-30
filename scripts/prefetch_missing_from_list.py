import hashlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CACHE = Path("cache/gcs_npz_alexnet_fold2015")
CACHE.mkdir(parents=True, exist_ok=True)

MISSING_LIST = Path("results/metrics/aia_resnet18_physics_safe_fold2015_fullnatural_missing_gcs_paths.txt")
WORKERS = 8

def local_path(src: str) -> Path:
    return CACHE / (hashlib.md5(src.encode()).hexdigest() + "_" + Path(src).name)

def copy_one(src: str):
    dst = local_path(src)
    if dst.exists() and dst.stat().st_size > 0:
        return "cached", src

    tmp = Path(str(dst) + ".tmp")
    if tmp.exists():
        tmp.unlink()

    r = subprocess.run(
        ["gcloud", "storage", "cp", src, str(tmp)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if r.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        return "failed", src, r.stderr[-700:]

    tmp.rename(dst)
    return "downloaded", src

def main():
    paths = [p.strip() for p in MISSING_LIST.read_text().splitlines() if p.strip()]
    todo = [p for p in paths if not local_path(p).exists()]

    print("missing_list_paths:", len(paths), flush=True)
    print("todo_start:", len(todo), flush=True)
    print("workers:", WORKERS, flush=True)

    counts = {"cached": 0, "downloaded": 0, "failed": 0}
    failures = []
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(copy_one, p) for p in todo]

        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            status = res[0]
            counts[status] += 1

            if status == "failed":
                failures.append(res)

            if i % 100 == 0 or status == "failed":
                print(
                    f"done={i}/{len(todo)} "
                    f"downloaded={counts['downloaded']} "
                    f"cached={counts['cached']} "
                    f"failed={counts['failed']} "
                    f"elapsed_min={(time.time()-t0)/60:.1f}",
                    flush=True,
                )

    print("FINAL", counts, flush=True)

    if failures:
        out = Path("results/metrics/aia_resnet18_fullnatural_prefetch_failures.txt")
        with out.open("w") as fh:
            for item in failures:
                fh.write(repr(item) + "\n")
        print("failures_written:", out, flush=True)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
