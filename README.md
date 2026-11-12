
# Datagaps DataOps Suite Trigger

Triggers DataOps Suite objects for JSON files changed in a push, and waits for the result.

## Usage

```yaml
name: DataOps Trigger
on:
  push:
    branches: [main]
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: Sumathi429/dataops-suite-action@v1.0.0.
        with:
          client-id: ${{ secrets.DATAOPS_CLIENT_ID }}
          client-secret: ${{ secrets.DATAOPS_CLIENT_SECRET }}
          username: ${{ secrets.DATAOPS_USERNAME }}
          password: ${{ secrets.DATAOPS_PASSWORD }}
```

## Inputs

| Input | Required | Description |
|---|---|---|
| client-id | Yes | DataOps OAuth client ID |
| client-secret | Yes | DataOps OAuth client secret |
| username | Yes | DataOps username |
| password | Yes | DataOps password |
