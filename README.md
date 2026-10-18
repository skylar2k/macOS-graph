# kd-graph

Interact with Microsoft Graph easily on MacOS using delegated apps: a small shared library (auth, client with retry and batching, pipe helpers) and pipe-friendly commands built on it.

## Install

```bash
uv tool install git+ssh://<repo-url>   # commands land on your PATH
# or, in a clone:
uv sync && uv run kd-get-devices
```

## Configuration

| Variable                                   | Purpose                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| `KD_GRAPH_CLIENT_ID`, `KD_GRAPH_TENANT_ID` | App registration (legacy `CLIENT_ID`/`TENANT_ID` also work)                          |
| `KD_GRAPH_UPN`                             | Optional login hint, e.g. `you@example.com`                                          |
| `KD_GRAPH_ALLOW_PLAINTEXT_CACHE=1`         | Allow a plain-file token cache if the encrypted one is unavailable (default: refuse) |

## Commands

Each command requests only the Graph scopes it needs (declared as `SCOPES` in its module).

| Command                      | Scope                                     | Does                                       |
| ---------------------------- | ----------------------------------------- | ------------------------------------------ |
| `kd-get-devices`             | `DeviceManagementManagedDevices.Read.All` | List managed devices (macOS by default)    |
| `kd-delete-devices`          | `…ManagedDevices.ReadWrite.All`           | Delete devices, **dry run unless `--yes`** |
| `kd-get-ade-tokens`          | `DeviceManagementServiceConfig.Read.All`  | List ADE tokens                            |
| `kd-get-enrollment-profiles` | `DeviceManagementServiceConfig.Read.All`  | List enrollment profiles per token         |
| `kd-disabled-users`          | `User.Read.All`                           | Disabled users as CSV                      |

## Pipe conventions

- Records are NDJSON on stdout; logs and errors go to stderr.
- Commands that take ids accept them as arguments, or on stdin as objects with an `id` field
  (`--key` to change it) or as bare lines (`jq -r .id`).
- Destructive commands are dry runs unless `--yes`, and refuse more than `--max-items` (50) records.

```bash
kd-get-devices \
  | jq -c 'select(.complianceState=="noncompliant" and .lastSyncDateTime < "2026-06-01")' \
  | kd-delete-devices            # dry run; add --yes to delete

kd-get-ade-tokens | jq -c 'select(.tokenName=="Prod")' | kd-get-enrollment-profiles
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Adding a command: create `src/kd_graph/cli/<name>.py` with a module-level `SCOPES` and an
`@entrypoint`-decorated `main()`, register it under `[project.scripts]`, and use
`safety.add_args`/`safety.proceed` if it changes anything.
