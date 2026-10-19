# graph-macos

Interact with Microsoft Graph easily on MacOS using delegated apps: a small shared library (auth, client with retry and batching, pipe helpers) and pipe-friendly commands built on it.

## Install

```bash
uv tool install git+https://github.com/skylar2k/macOS-graph.git   # commands land on your PATH
# or, in a clone:
uv sync && uv run gmac-get-devices
```

## Configuration

| Variable                                         | Purpose                                                                              |
| ------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `GRAPH_MACOS_CLIENT_ID`, `GRAPH_MACOS_TENANT_ID` | Entra app registration (public client, delegated permissions)                        |
| `GRAPH_MACOS_UPN`                                | Optional login hint, e.g. `you@example.com`                                          |
| `GRAPH_MACOS_ALLOW_PLAINTEXT_CACHE=1`            | Allow a plain-file token cache if the encrypted one is unavailable (default: refuse) |

## Commands

Each command requests only the Graph scopes it needs (declared as `SCOPES` in its module).

| Command                          | Scope                                          | Does                                                                     |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------ |
| `gmac-get-devices`               | `DeviceManagementManagedDevices.Read.All`      | List managed devices (macOS by default)                                  |
| `gmac-delete-devices`            | `DeviceManagementManagedDevices.ReadWrite.All` | Delete devices, **dry run unless `--yes`**                               |
| `gmac-get-ade-tokens`            | `DeviceManagementServiceConfig.Read.All`       | List ADE tokens                                                          |
| `gmac-get-ade-devices`           | `DeviceManagementServiceConfig.Read.All`       | List imported ADE devices                                                |
| `gmac-get-enrollment-profiles`   | `DeviceManagementServiceConfig.Read.All`       | List enrollment profiles per token                                       |
| `gmac-assign-enrollment-profile` | `DeviceManagementServiceConfig.ReadWrite.All`  | Assign a profile to devices by serial number, **dry run unless `--yes`** |
| `gmac-disabled-users`            | `User.Read.All`                                | List disabled users                                                      |

## Pipe conventions

- Records are NDJSON on stdout; logs and errors go to stderr.
- Commands that take ids (or serial numbers) accept them as arguments, or on stdin as objects with an `id` field
  (`--key` to change the field; assign uses `serialNumber`) or as bare lines (`jq -r .id`).
- Destructive commands are dry runs unless `--yes`, and refuse more than `--max-items` (50) records.

```bash
gmac-get-devices \
  | jq -c 'select(.complianceState=="noncompliant" and .lastSyncDateTime < "2026-06-01")' \
  | gmac-delete-devices            # dry run; add --yes to delete

gmac-get-ade-tokens | jq -c 'select(.tokenName=="Prod")' | gmac-get-enrollment-profiles

# assign a profile to devices (devices on stdin, token and profile as flags)
gmac-get-devices | jq -c 'select(.serialNumber | startswith("C02"))' \
  | gmac-assign-enrollment-profile --token "$TOKEN_ID" --profile "$PROFILE_ID"   # dry run
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Layout: `graph_macos/graph/` is the library (auth, client), `graph_macos/cli/` holds one module per
command, and `graph_macos/cli/utils/` the pipe and safety helpers.

Adding a command: create `src/graph_macos/cli/<name>.py` with a module-level `SCOPES` and an
`@entrypoint`-decorated `main()`, register it under `[project.scripts]`, and use
`safety.add_args`/`safety.proceed` if it changes anything.
