"""Datagaps DataOps Suite trigger - Version 1 (manual, by ID)."""
import base64
import json
import os
import sys
import time

import requests

BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")

DATAFLOW_ID = os.getenv("DATAFLOW_ID", "NA")
DBFLOW_ID = os.getenv("DBFLOW_ID", "NA")
PIPELINE_ID = os.getenv("PIPELINE_ID", "NA")
DATAMODEL_ID = os.getenv("DATAMODEL_ID", "NA")

GROUP_ID = os.getenv("GROUP_ID", "NA")
DATASOURCE_ID = os.getenv("DATASOURCE_ID", "NA")
WORK_SCHEMA_ID = os.getenv("WORK_SCHEMA_ID", "NA")
PARALLEL_RULES = os.getenv("PARALLEL_RULES", "NA")
SAMPLE_RESULT_COUNT = os.getenv("SAMPLE_RESULT_COUNT", "NA")
FAILURE_FILE_LOCATION = os.getenv("FAILURE_FILE_LOCATION", "NA")
MAX_FAILURE_RECORDS = os.getenv("MAX_FAILURE_RECORDS", "NA")

API_TIMEOUT = 60
POLL_INTERVAL = 60
MAX_WAIT_TIME = 3600

SUCCESS_STATUSES = {"COMPLETED"}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ERROR"}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "DataOps-Automation/1.0",
    "Accept": "application/json",
})


def is_provided(value):
    return value is not None and str(value).strip().upper() not in (
        "", "NA", "N/A", "NONE"
    )


def to_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def get_access_token():
    required = [
        "DATAOPS_CLIENT_ID",
        "DATAOPS_CLIENT_SECRET",
        "DATAOPS_USERNAME",
        "DATAOPS_PASSWORD",
    ]
    credentials = {name: os.getenv(name) for name in required}
    missing = [n for n, v in credentials.items() if not v or not v.strip()]
    if missing:
        raise Exception(
            "Missing GitHub Repository Secrets: " + ", ".join(missing)
        )

    auth_url = f"{BASE_URL}/dataopssecurity/oauth2/token"
    basic = base64.b64encode(
        f"{credentials['DATAOPS_CLIENT_ID']}:{credentials['DATAOPS_CLIENT_SECRET']}".encode()
    ).decode()

    response = SESSION.post(
        auth_url,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "username": credentials["DATAOPS_USERNAME"],
            "password": credentials["DATAOPS_PASSWORD"],
            "grant_type": "password",
        },
        timeout=API_TIMEOUT,
    )
    if response.status_code != 200:
        raise Exception(
            f"Authentication failed: HTTP {response.status_code}, "
            f"{response.text[:500]}"
        )
    token = response.json().get("access_token")
    if not token:
        raise Exception("Access token not found")
    print("Authentication successful")
    return token


def call_api(method, url, token, params=None, payload=None):
    response = SESSION.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params=params,
        json=payload,
        timeout=API_TIMEOUT,
    )
    if response.status_code not in (200, 201, 202):
        raise Exception(
            f"API failed: HTTP {response.status_code}, "
            f"{response.text[:1000]}"
        )
    try:
        return response.json()
    except ValueError:
        return response.text.strip()


def find_value(data, keys):
    if isinstance(data, dict):
        for key in keys:
            if data.get(key) is not None:
                return data[key]
        for value in data.values():
            found = find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_value(item, keys)
            if found is not None:
                return found
    return None


def get_run_id(response, keys):
    if isinstance(response, (int, str)) and response != "":
        return response
    return find_value(response, keys)


def poll_status(label, token, status_url, params=None,
                status_keys=("status",)):
    """Returns (status, last_response)."""
    start = time.time()
    print(f"Checking {label} status every {POLL_INTERVAL} seconds...")
    while True:
        if time.time() - start > MAX_WAIT_TIME:
            raise Exception(f"{label}: maximum wait time exceeded")

        data = call_api("GET", status_url, token, params=params)
        status = find_value(data, status_keys)
        if status is None:
            raise Exception(
                f"{label}: could not find status in response: {data}"
            )
        status = str(status).upper()
        print(f"{label} Status: {status}")

        if status in TERMINAL_STATUSES:
            print(f"{label} finished with status: {status}")
            print(f"{label} final response: {json.dumps(data)[:1500]}")
            return status, data
        time.sleep(POLL_INTERVAL)


def run_pipeline(token):
    print("\n--- Pipeline ---")
    response = call_api(
        "POST", f"{BASE_URL}/piper/jobs", token,
        payload={"pipelineId": PIPELINE_ID,
                 "runName": "Trigger Pipeline using Github Actions"},
    )
    run_id = get_run_id(response, ["id", "jobId"])
    if not run_id:
        raise Exception(f"Pipeline run ID not found: {response}")
    print(f"Pipeline triggered, Run ID: {run_id}")
    status, data = poll_status(
        "Pipeline", token, f"{BASE_URL}/piper/jobs/{run_id}/status")
    return PIPELINE_ID, run_id, status, data


def run_dataflow(token):
    print("\n--- Dataflow ---")
    response = call_api(
        "POST",
        f"{BASE_URL}/DataFlowService/api/v1.0/dataFlows/executeDataFlow",
        token, params={"dataflowId": DATAFLOW_ID},
    )
    run_id = get_run_id(response, ["dataFlowRunId", "runId", "id"])
    if not run_id:
        raise Exception(f"Dataflow run ID not found: {response}")
    print(f"Dataflow triggered, Run ID: {run_id}")
    status, data = poll_status(
        "Dataflow", token,
        f"{BASE_URL}/DataFlowService/api/v1.0/dataFlows/dataflow-status",
        params={"dataFlowRunId": run_id},
    )
    return DATAFLOW_ID, run_id, status, data


def run_dbflow(token):
    print("\n--- DB Flow ---")
    response = call_api(
        "POST",
        f"{BASE_URL}/DataFlowService/api/v1.0/dataFlows/executeDataFlow",
        token, params={"dataflowId": DBFLOW_ID},
    )
    run_id = get_run_id(
        response, ["testCaseRunId", "runId", "dataFlowRunId", "id"])
    if not run_id:
        raise Exception(f"DB Flow run ID not found: {response}")
    print(f"DB Flow triggered, Run ID: {run_id}")
    status, data = poll_status(
        "DB Flow", token,
        f"{BASE_URL}/DataFlowService/api/v1.0/testcase/{DBFLOW_ID}/component/status",
        params={"testCaseRunId": run_id},
    )
    return DBFLOW_ID, run_id, status, data


def run_datamodel(token):
    print("\n--- Data Model ---")
    required = {
        "GROUP_ID": GROUP_ID,
        "DATASOURCE_ID": DATASOURCE_ID,
        "WORK_SCHEMA_ID": WORK_SCHEMA_ID,
        "PARALLEL_RULES": PARALLEL_RULES,
        "SAMPLE_RESULT_COUNT": SAMPLE_RESULT_COUNT,
        "MAX_FAILURE_RECORDS": MAX_FAILURE_RECORDS,
    }
    missing = [n for n, v in required.items() if not is_provided(v)]
    if missing:
        raise Exception(
            "Data Model requires these parameters: " + ", ".join(missing))

    body = {
        "groupId": to_number(GROUP_ID),
        "dataSourceId": to_number(DATASOURCE_ID),
        "workSchemaId": to_number(WORK_SCHEMA_ID),
        "ParallelRules": to_number(PARALLEL_RULES),
        "sampleResultCount": to_number(SAMPLE_RESULT_COUNT),
        "failureFileLocation": (
            FAILURE_FILE_LOCATION if is_provided(FAILURE_FILE_LOCATION)
            else None
        ),
        "maxFailureRecords": to_number(MAX_FAILURE_RECORDS),
    }
    response = call_api(
        "POST",
        f"{BASE_URL}/dataops-dataquality/api/v1.0/data-model/{DATAMODEL_ID}/rules/run",
        token, payload=body,
    )
    run_id = get_run_id(response, ["runId", "id"])
    if not run_id:
        raise Exception(f"Data Model run ID not found: {response}")
    print(f"Data Model triggered, Run ID: {run_id}")
    status, data = poll_status(
        "Data Model", token,
        f"{BASE_URL}/dataops-dataquality/api/v1.0/data-model/{DATAMODEL_ID}/run/{run_id}/details",
    )
    return DATAMODEL_ID, run_id, status, data


def checks_text(data):
    """Best effort: show passed/total if the response has such fields."""
    passed = find_value(data, ["passedCount", "passCount", "passed",
                               "checksPassed", "passedRules"])
    total = find_value(data, ["totalCount", "total", "totalChecks",
                              "checksTotal", "totalRules"])
    try:
        passed, total = int(passed), int(total)
    except (TypeError, ValueError):
        return "-"
    pct = round(100 * passed / total) if total else 0
    return f"{passed}/{total} ({pct}%)"


def write_table(rows, ok):
    lines = [
        "datagaps-validate summary", "",
        f"## Datagaps validation: {'✅ PASSED' if ok else '❌ FAILED'}", "",
        "| Type | ID | Run | Status | Checks passed | Duration |",
    ]
    for r in rows:
        lines.append(f"| {r['type']} | {r['id']} | {r['run']} | {r['status']} "
                     f"| {r['checks']} | {r['duration']} |")
    text = "\n".join(lines) + "\n"
    print("\n" + text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)


def main():
    if not BASE_URL.lower().startswith(("http://", "https://")):
        print("BASE_URL must start with http:// or https:// "
              "(e.g. https://poc.datagaps.com)")
        sys.exit(1)

    jobs = []
    if is_provided(PIPELINE_ID):
        jobs.append(("pipeline", PIPELINE_ID, run_pipeline))
    if is_provided(DATAFLOW_ID):
        jobs.append(("dataflow", DATAFLOW_ID, run_dataflow))
    if is_provided(DBFLOW_ID):
        jobs.append(("dbflow", DBFLOW_ID, run_dbflow))
    if is_provided(DATAMODEL_ID):
        jobs.append(("datamodel", DATAMODEL_ID, run_datamodel))

    if not jobs:
        print("Please provide at least one execution ID.")
        sys.exit(1)

    print("Will trigger: " + ", ".join(name for name, _, _ in jobs))
    token = get_access_token()

    rows = []
    for name, obj_id, runner in jobs:
        began = time.time()
        try:
            obj_id, run_id, status, data = runner(token)
            rows.append({
                "type": name, "id": obj_id, "run": run_id,
                "status": status, "checks": checks_text(data),
                "duration": f"{time.time() - began:.1f}s",
                "ok": status in SUCCESS_STATUSES,
            })
        except Exception as error:
            print(f"{name} failed: {error}")
            rows.append({
                "type": name, "id": obj_id, "run": "-", "status": "ERROR",
                "checks": "-", "duration": f"{time.time() - began:.1f}s",
                "ok": False,
            })

    ok = all(r["ok"] for r in rows)
    write_table(rows, ok)
    if not ok:
        sys.exit(1)
    print("All triggered objects completed successfully")


main()
