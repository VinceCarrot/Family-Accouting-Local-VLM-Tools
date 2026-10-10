import json
import os
from urllib.request import urlopen
from pathlib import Path
from werkzeug.utils import secure_filename

from scripts.src.tools.pdf_analyzer import analyze, save_filled_transactions_to_json


APP_ROOT = Path(__file__).resolve().parent
ESTATEMENTS_ROOT = APP_ROOT / "estatements"
CONFIG_PATH = APP_ROOT / "batch_input_config.json"
REMAINING_CONFIG_PATH = APP_ROOT / "batch_input_config_remaining.json"
OLLAMA_KEEP_ALIVE = -1
APPDATA_URL = os.environ.get(
    "SPENDLOG_APPDATA_URL",
    "http://192.168.1.33:5000/get_appdata",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def main() -> None:
    os.chdir(APP_ROOT)
    source_config = REMAINING_CONFIG_PATH if REMAINING_CONFIG_PATH.exists() else CONFIG_PATH
    jobs = load_json(source_config)

    with urlopen(APPDATA_URL, timeout=15) as response:
        app_data = json.load(response)

    local_data = APP_ROOT / "static" / "data"
    for filename in ("account_format.json", "pdf_pwd.json"):
        app_data[filename.removesuffix(".json")] = load_json(local_data / filename)

    print(f"Loaded {len(jobs)} jobs from {source_config}", flush=True)
    total_jobs = len(jobs)
    while jobs:
        index = total_jobs - len(jobs) + 1
        job = jobs[0]
        app_data["category_cache"] = load_json(local_data / "category_cache.json")
        year = int(job["year"])
        month = int(job["month"])
        account = job["account"]
        pdf_path = (
            ESTATEMENTS_ROOT
            / f"{year:04d}"
            / f"{month:02d}"
            / secure_filename(account)
            / job["source_pdf"]
        )

        print(f"[{index}/{total_jobs}] Processing {pdf_path}", flush=True)
        result = analyze(
            str(pdf_path), account, str(year), str(month), app_data,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
        if not result["success"]:
            raise RuntimeError(result["error"])

        output_path = save_filled_transactions_to_json(
            result["data"], account, year, month, str(ESTATEMENTS_ROOT)
        )
        print(f"Saved {len(result['data'])} transactions to {output_path}", flush=True)

        jobs.pop(0)
        save_json(REMAINING_CONFIG_PATH, jobs)
        print(f"Checkpoint saved: {len(jobs)} jobs remain in {REMAINING_CONFIG_PATH}", flush=True)


if __name__ == "__main__":
    main()