import requests
import base64
import time
import json
import sys
import os
import subprocess


# Use dataops_config.json from the user's repo if present,
# otherwise fall back to the one bundled with this action.
_bundled = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "dataops_config.json"
)

CONFIG_FILE = (
    "dataops_config.json"
    if os.path.isfile("dataops_config.json")
    else _bundled
)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    APP_CONFIG = json.load(f)

BASE_URL = APP_CONFIG.get("base_url", "").rstrip("/")

if not BASE_URL:
    raise ValueError(
        "DataOps base_url is missing in dataops_config.json"
    )

API_TIMEOUT = APP_CONFIG.get("api_timeout", 60)
POLL_INTERVAL = APP_CONFIG.get("poll_interval", 60)
MAX_WAIT_TIME = APP_CONFIG.get("max_wait_time", 3600)


def get_access_token():

    # Credentials come from GitHub secrets via environment variables
    client_id = os.environ["DATAOPS_CLIENT_ID"]
    client_secret = os.environ["DATAOPS_CLIENT_SECRET"]
    username = os.environ["DATAOPS_USERNAME"]
    password = os.environ["DATAOPS_PASSWORD"]

    # Authentication URL uses the configured environment domain
    auth_url = (
        f"{BASE_URL}/dataopssecurity/oauth2/token"
    )

    basic_auth_str = f"{client_id}:{client_secret}"

    base64_auth_str = base64.b64encode(
        basic_auth_str.encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {base64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "username": username,
        "password": password,
        "grant_type": "password"
    }

    response = requests.post(
        auth_url,
        headers=headers,
        data=payload,
        timeout=API_TIMEOUT
    )

    response.raise_for_status()

    access_token = response.json().get("access_token")

    if not access_token:
        raise Exception(
            "Access token not found in authentication response"
        )

    print("Authentication successful")

    return access_token


def get_json_value(data, field_path):

    value = data

    for field in field_path.split("."):

        if isinstance(value, dict):
            value = value.get(field)

        elif isinstance(value, list):
            try:
                value = value[int(field)]
            except (ValueError, IndexError):
                return None

        else:
            return None

        if value is None:
            return None

    return value


def resolve_value(value, json_data, context):

    if isinstance(value, dict):
        return {
            key: resolve_value(val, json_data, context)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            resolve_value(item, json_data, context)
            for item in value
        ]

    if isinstance(value, str):

        if value.startswith("json:"):
            return get_json_value(
                json_data,
                value[5:]
            )

        return value.format(**context)

    return value


def build_url(url_template, context):

    return url_template.format(**context)


def call_api(method, url, token, params=None, payload=None):

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        json=payload,
        timeout=API_TIMEOUT
    )

    if response.status_code not in [200, 201, 202]:
        raise Exception(
            f"API failed: {response.status_code}, {response.text}"
        )

    try:
        return response.json()

    except ValueError:
        return {}


def extract_response_value(response_data, field_paths):

    for field_path in field_paths:

        value = get_json_value(
            response_data,
            field_path
        )

        if value is not None:
            return value

    return None


def poll_status(
    token,
    status_config,
    context,
    json_data
):

    start_time = time.time()

    status_url = build_url(
        status_config["url"],
        context
    )

    params = resolve_value(
        status_config.get("params", {}),
        json_data,
        context
    )

    print("Checking execution status...")

    while True:

        if time.time() - start_time > MAX_WAIT_TIME:
            raise Exception(
                "Maximum execution wait time exceeded"
            )

        response_data = call_api(
            method=status_config.get("method", "GET"),
            url=status_url,
            token=token,
            params=params
        )

        status = extract_response_value(
            response_data,
            status_config["status_fields"]
        )

        if status is None:
            raise Exception(
                f"Could not identify status from response: "
                f"{response_data}"
            )

        status = str(status).upper()

        print(f"Execution Status: {status}")

        terminal_statuses = [
            value.upper()
            for value in status_config["terminal_statuses"]
        ]

        if status in terminal_statuses:
            print(f"Execution finished: {status}")
            return status

        time.sleep(POLL_INTERVAL)


def trigger_object(token, object_type, json_file):

    print("\n-----------------------------------")
    print(f"Processing {object_type}: {json_file}")
    print("-----------------------------------")

    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    object_config = APP_CONFIG["objects"][object_type]

    object_id = get_json_value(
        json_data,
        object_config["id_field"]
    )

    if not object_id:
        raise Exception(
            f"Object ID field '{object_config['id_field']}' "
            f"not found in {json_file}"
        )

    context = {
        "object_id": object_id,
        "file_name": os.path.basename(json_file),
        "file_path": json_file,
        "base_url": BASE_URL
    }

    if object_config.get("status_object_id_field"):

        status_object_id = get_json_value(
            json_data,
            object_config["status_object_id_field"]
        )

        if not status_object_id:
            raise Exception(
                "Status object ID not found in JSON"
            )

        context["status_object_id"] = status_object_id

    # Build trigger API request
    trigger_config = object_config["trigger"]

    trigger_url = build_url(
        trigger_config["url"],
        context
    )

    params = resolve_value(
        trigger_config.get("params", {}),
        json_data,
        context
    )

    payload = resolve_value(
        trigger_config.get("payload"),
        json_data,
        context
    )

    print(f"Object ID: {object_id}")
    print(f"Environment: {BASE_URL}")
    print(f"Triggering {object_type}...")

    trigger_response = call_api(
        method=trigger_config["method"],
        url=trigger_url,
        token=token,
        params=params,
        payload=payload
    )

    # Extract execution/run ID
    run_id = extract_response_value(
        trigger_response,
        trigger_config["run_id_fields"]
    )

    if not run_id:
        raise Exception(
            f"Run ID not found in trigger response: "
            f"{trigger_response}"
        )

    print(f"Execution started. Run ID: {run_id}")

    context["run_id"] = run_id

    # Poll execution status
    final_status = poll_status(
        token,
        object_config["status"],
        context,
        json_data
    )

    success_statuses = [
        value.upper()
        for value in object_config["status"]["success_statuses"]
    ]

    if final_status not in success_statuses:
        raise Exception(
            f"{object_type} execution failed: {final_status}"
        )

    print(f"{object_type} completed successfully")

    return run_id, final_status


def get_changed_files():

    before = os.environ.get("BEFORE_SHA")
    after = os.environ.get("AFTER_SHA")

    if not before or not after:
        raise Exception(
            "BEFORE_SHA or AFTER_SHA is missing"
        )

    # Initial commit: compare against empty tree
    if before == "0000000000000000000000000000000000000000":

        changed = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                after
            ],
            text=True
        )

        return [
            path for path in changed.splitlines()
            if path.lower().endswith(".json")
        ]

    output = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            before,
            after
        ],
        text=True
    )

    return [
        path for path in output.splitlines()
        if path.lower().endswith(".json")
    ]


def main():

    changed_files = get_changed_files()

    if not changed_files:
        print("No JSON changes found")
        return

    print("\nChanged JSON files:")

    for file_path in changed_files:
        print(file_path)

    token = get_access_token()

    folder_mapping = APP_CONFIG["folder_mapping"]

    failures = []

    for file_path in changed_files:

        if not os.path.isfile(file_path):
            print(
                f"File no longer exists, skipping: {file_path}"
            )
            continue

        parts = file_path.replace("\\", "/").split("/")

        object_type = None

        for folder in parts[:-1]:

            if folder in folder_mapping:
                object_type = folder_mapping[folder]
                break

        if not object_type:
            print(
                f"Unmapped folder, skipping: {file_path}"
            )
            continue

        try:
            trigger_object(
                token,
                object_type,
                file_path
            )

        except Exception as error:
            print(
                f"Failed: {file_path}: {error}"
            )
            failures.append(file_path)

    if failures:

        print("\nFailed objects:")

        for item in failures:
            print(item)

        sys.exit(1)

    print(
        "\nAll changed DataOps objects processed successfully"
    )


main()
