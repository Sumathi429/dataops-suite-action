"""Datagaps DataOps Suite trigger - Version 1 (manual, by ID)."""
import os
import sys
import time

import requests

BASE_URL = os.environ.get("DG_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("DG_TOKEN", "")
POLL_SECONDS = 10
TIMEOUT_SECONDS = 1800
TERMINAL = {"PASSED", "FAILED", "ERROR", "CANCELLED", "ABORTED"}


def parse_ids(value):
    return [v.strip() for v in value.split(",") if v.strip()]
def headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def start_run(obj_type, obj_id):
    r = requests.post(f"{BASE_URL}/api/{obj_type}/{obj_id}/run",
                      headers=headers(), timeout=60)
    r.raise_for_status()
    return r.json()["runId"]


def get_run(run_id):
    r = requests.get(f"{BASE_URL}/api/runs/{run_id}",
                     headers=headers(), timeout=60)
    r.raise_for_status()
    d = r.json()
    return {
        "status": str(d["status"]).upper(),
        "passed": d.get("checksPassed", 0),
        "total": d.get("checksTotal", 0),
    }
# ---------------------------------------------------------------------------


def run_object(obj_type, obj_id):
    began = time.time()
    run_id = start_run(obj_type, obj_id)
    print(f"{obj_type} {obj_id} -> {run_id}", flush=True)

    last, res = None, {"status": "QUEUED", "passed": 0, "total": 0}
    while time.time() - began < TIMEOUT_SECONDS:
        res = get_run(run_id)
        if res["status"] != last:
            print(f"{obj_type} {obj_id} {run_id}: {res['status']}", flush=True)
            last = res["status"]
        if res["status"] in TERMINAL:
            break
        time.sleep(POLL_SECONDS)
    else:
        res["status"] = "TIMEOUT"

    pct = round(100 * res["passed"] / res["total"]) if res["total"] else 0
    return {
        "type": obj_type, "id": obj_id, "run": run_id,
        "status": res["status"],
        "checks": f"{res['passed']}/{res['total']} ({pct}%)",
        "duration": f"{time.time() - began:.1f}s",
    }


def write_table(rows, ok):
    lines = [
        "datagaps-validate summary", "",
        f"## Datagaps validation: {'✅ PASSED' if ok else '❌ FAILED'}", "",
        "| Type | ID | Run | Status | Checks passed | Duration |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['type']} | {r['id']} | {r['run']} | {r['status']} "
                     f"| {r['checks']} | {r['duration']} |")
    text = "\n".join(lines) + "\n"
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)


def main():
    if not BASE_URL or not TOKEN:
        sys.exit("URL and token are required.")

    jobs = []
    for obj_type, env in (("dataflow", "DG_DATAFLOW_IDS"),
                          ("pipeline", "DG_PIPELINE_IDS"),
                          ("dbflow", "DG_DBFLOW_IDS")):
        jobs += [(obj_type, i) for i in parse_ids(os.environ.get(env, ""))]
    if not jobs:
        sys.exit("Enter at least one ID.")

    rows = []
    for obj_type, obj_id in jobs:
        try:
            rows.append(run_object(obj_type, obj_id))
        except Exception as exc:
            print(f"{obj_type} {obj_id} could not run: {exc}")
            rows.append({"type": obj_type, "id": obj_id, "run": "-",
                         "status": "ERROR", "checks": "0/0 (0%)",
                         "duration": "0.0s"})

    ok = all(r["status"] == "PASSED" for r in rows)
    write_table(rows, ok)
    if not ok:
        sys.exit(1)

main()
