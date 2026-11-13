
# Datagaps DataOps Suite Trigger

A GitHub Action that triggers Datagaps DataOps Suite objects (Pipelines, Dataflows, DB Flows and Data Models) and waits for them to finish. The workflow fails if any triggered object does not complete successfully.

## Features

- Trigger a Pipeline, Dataflow, DB Flow or Data Model, or any combination in one run
- Polls the run status every 60 seconds (up to 60 minutes)
- Fails the workflow if an object ends with `FAILED` or `ERROR`
- Skips any object whose ID is left as `NA`

## Setup

### 1. Add repository secrets

In your repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Description |
|---|---|
| `DATAOPS_CLIENT_ID` | OAuth client ID |
| `DATAOPS_CLIENT_SECRET` | OAuth client secret |
| `DATAOPS_USERNAME` | DataOps username |
| `DATAOPS_PASSWORD` | DataOps password |

### 2. Add a workflow

Create `.github/workflows/dataops.yml` in your repository:

```yaml
name: Run DataOps Suite

on:
  workflow_dispatch:
    inputs:
      base_url:
        description: "Enter Base URL"
        required: true
        type: string
      pipeline_id:
        description: "Pipeline ID (NA if not required)"
        required: false
        default: "NA"
        type: string
      dataflow_id:
        description: "Dataflow ID (NA if not required)"
        required: false
        default: "NA"
        type: string
      dbflow_id:
        description: "DB Flow ID (NA if not required)"
        required: false
        default: "NA"
        type: string
      datamodel_id:
        description: "Data Model ID (NA if not required)"
        required: false
        default: "NA"
        type: string
      group_id:
        description: "Data Model Group ID"
        required: false
        default: "NA"
        type: string
      datasource_id:
        description: "Data Source ID"
        required: false
        default: "NA"
        type: string
      work_schema_id:
        description: "Work Schema ID"
        required: false
        default: "NA"
        type: string
      parallel_rules:
        description: "Parallel Rules"
        required: false
        default: "NA"
        type: string
      sample_result_count:
        description: "Sample Result Count"
        required: false
        default: "NA"
        type: string
      failure_file_location:
        description: "Failure File Location"
        required: false
        default: "NA"
        type: string
      max_failure_records:
        description: "Maximum Failure Records"
        required: false
        default: "NA"
        type: string

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: Sumathi429/dataops-suite-action@v1.0.1
        with:
          base_url: ${{ inputs.base_url }}
          client_id: ${{ secrets.DATAOPS_CLIENT_ID }}
          client_secret: ${{ secrets.DATAOPS_CLIENT_SECRET }}
          username: ${{ secrets.DATAOPS_USERNAME }}
          password: ${{ secrets.DATAOPS_PASSWORD }}
          pipeline_id: ${{ inputs.pipeline_id }}
          dataflow_id: ${{ inputs.dataflow_id }}
          dbflow_id: ${{ inputs.dbflow_id }}
          datamodel_id: ${{ inputs.datamodel_id }}
          group_id: ${{ inputs.group_id }}
          datasource_id: ${{ inputs.datasource_id }}
          work_schema_id: ${{ inputs.work_schema_id }}
          parallel_rules: ${{ inputs.parallel_rules }}
          sample_result_count: ${{ inputs.sample_result_count }}
          failure_file_location: ${{ inputs.failure_file_location }}
          max_failure_records: ${{ inputs.max_failure_records }}
```

### 3. Run it

Open the **Actions** tab, select **Run DataOps Suite**, click **Run workflow**, enter the base URL and the IDs you want to trigger, and run.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `base_url` | Yes | | DataOps base URL, for example `https://your-server.com` |
| `client_id` | Yes | | OAuth client ID |
| `client_secret` | Yes | | OAuth client secret |
| `username` | Yes | | DataOps username |
| `password` | Yes | | DataOps password |
| `pipeline_id` | No | `NA` | Pipeline ID to run |
| `dataflow_id` | No | `NA` | Dataflow ID to run |
| `dbflow_id` | No | `NA` | DB Flow ID to run |
| `datamodel_id` | No | `NA` | Data Model ID to run |
| `group_id` | Data Model only | `NA` | Data Model group ID |
| `datasource_id` | Data Model only | `NA` | Data source ID |
| `work_schema_id` | Data Model only | `NA` | Work schema ID |
| `parallel_rules` | Data Model only | `NA` | Number of rules to run in parallel |
| `sample_result_count` | Data Model only | `NA` | Number of sample results to keep |
| `failure_file_location` | No | `NA` | Location for failure files |
| `max_failure_records` | Data Model only | `NA` | Maximum failure records to store |

Leave an ID as `NA` to skip that object. At least one of `pipeline_id`, `dataflow_id`, `dbflow_id` or `datamodel_id` must be provided.

## Execution order

When several IDs are given, objects run one after another in this order: Pipeline, Dataflow, DB Flow, Data Model. A failure in one object does not stop the others, and all failures are listed at the end of the run.

## Requirements

- The DataOps server must be reachable from GitHub-hosted runners. If it is on a private network, use a self-hosted runner.
- The user account must have permission to run the selected objects.

## Troubleshooting

| Message | Cause |
|---|---|
| `BASE_URL must start with http:// or https://` | The base URL is empty or missing the protocol |
| `Missing GitHub Repository Secrets` | One or more of the four secrets is not set |
| `Authentication failed: HTTP 401` | Wrong credentials or client ID/secret |
| `API failed: HTTP 404` | The object ID or API path is not available on that server |
| `maximum wait time exceeded` | The run took longer than 60 minutes |

## License

Add your license here.
