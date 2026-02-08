import os
import sys
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.cloud import storage

BUCKET = os.environ.get("BUCKET_NAME", "ecreatemodels-cloud-run-data")

# GCS object -> local path (relative to /opt/ComfyUI)
OBJECTS = [
    ("diffusion_models/z_image_turbo_bf16.safetensors", "models/diffusion_models/z_image_turbo_bf16.safetensors"),
    ("text_encoders/qwen_3_4b.safetensors",             "models/text_encoders/qwen_3_4b.safetensors"),
    ("vae/ae.safetensors",                              "models/vae/ae.safetensors"),
]

# Bigger chunk size reduces HTTP calls for big files
CHUNK_SIZE = int(os.environ.get("GCS_CHUNK_SIZE", str(64 * 1024 * 1024)))  # 64MB
WORKERS = int(os.environ.get("GCS_WORKERS", "3"))

BASE_DIR = pathlib.Path("/opt/ComfyUI")


def download_one(client: storage.Client, bucket_name: str, obj: str, dest_rel: str) -> str:
    dest = BASE_DIR / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(obj)
    blob.chunk_size = CHUNK_SIZE

    # Skip if already downloaded and size matches
    if dest.exists():
        try:
            blob.reload()  # fetch metadata (size)
            if blob.size is not None and dest.stat().st_size == blob.size:
                return f"SKIP {obj} (already present)"
        except Exception:
            # If metadata fetch fails, just re-download
            pass

    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        blob.download_to_filename(str(tmp))
        tmp.replace(dest)
        return f"OK   {obj} -> {dest_rel}"
    except Exception as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise RuntimeError(f"FAIL {obj}: {e}") from e


def main():
    print(f"[models] bucket={BUCKET} workers={WORKERS} chunk={CHUNK_SIZE}", flush=True)
    client = storage.Client()

    with ThreadPoolExecutor(max_workers=min(WORKERS, len(OBJECTS))) as ex:
        futures = [ex.submit(download_one, client, BUCKET, obj, dest) for obj, dest in OBJECTS]
        for fut in as_completed(futures):
            print("[models]", fut.result(), flush=True)

    print("[models] done", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr, flush=True)
        sys.exit(1)
