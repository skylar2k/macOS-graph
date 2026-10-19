# graph-macos

Interact with Microsoft Graph easily on MacOS using delegated apps: a small shared library (auth, client with retry and batching, pipe helpers) and pipe-friendly commands built on it.

## Install

```bash
uv tool install git+https://github.com/skylar2k/macOS-graph.git   # commands land on your PATH
# or, in a clone:
uv sync && uv run gmac devices list
```

## Configuration

| Variable                                         | Purpose                                                                              |
| ------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `GRAPH_MACOS_CLIENT_ID`, `GRAPH_MACOS_TENANT_ID` | Entra app registration (public client, delegated permissions)                        |
| `GRAPH_MACOS_UPN`                                | Optional login hint, e.g. `you@example.com`                                          |
| `GRAPH_MACOS_ALLOW_PLAINTEXT_CACHE=1`            | Allow a plain-file token cache if the encrypted one is unavailable (default: refuse) |

## Commands

One command, `gmac <noun> <verb>`. Every command requests only the Graph scopes it needs:
reads ask for `.Read` scopes, and only commands that change something ask for `.ReadWrite`.
Run `gmac --help`, `gmac devices --help` and so on to explore.

<!-- commands:start -->
| Command | Scopes | Does |
| --- | --- | --- |
| `gmac ade devices get` | `DeviceManagementServiceConfig.Read.All` | Fetch ade devices by id (arguments or stdin) as NDJSON. |
| `gmac ade devices list` | `DeviceManagementServiceConfig.Read.All` | List ade devices as NDJSON, one record per line. Token ids come from arguments or stdin. |
| `gmac ade profiles assign` | `DeviceManagementServiceConfig.ReadWrite.All` | Assign an enrollment profile to devices by serial number. **Dry run unless `--yes`.** |
| `gmac ade profiles get` | `DeviceManagementServiceConfig.Read.All` | Fetch ade profiles by id (arguments or stdin) as NDJSON. |
| `gmac ade profiles list` | `DeviceManagementServiceConfig.Read.All` | List ade profiles as NDJSON, one record per line. Token ids come from arguments or stdin. |
| `gmac ade profiles update` | `DeviceManagementServiceConfig.ReadWrite.All` | Apply the same property changes to ade profiles by id (arguments or stdin). **Dry run unless `--yes`.** |
| `gmac ade tokens get` | `DeviceManagementServiceConfig.Read.All` | Fetch ade tokens by id (arguments or stdin) as NDJSON. |
| `gmac ade tokens list` | `DeviceManagementServiceConfig.Read.All` | List ade tokens as NDJSON, one record per line. |
| `gmac apps delete` | `DeviceManagementApps.ReadWrite.All` | Delete apps by id (arguments or stdin). **Dry run unless `--yes`.** |
| `gmac apps get` | `DeviceManagementApps.Read.All` | Fetch apps by id (arguments or stdin) as NDJSON. |
| `gmac apps list` | `DeviceManagementApps.Read.All` | List apps as NDJSON, one record per line. |
| `gmac compliance-policies delete` | `DeviceManagementConfiguration.ReadWrite.All` | Delete compliance-policies by id (arguments or stdin). **Dry run unless `--yes`.** |
| `gmac compliance-policies get` | `DeviceManagementConfiguration.Read.All` | Fetch compliance-policies by id (arguments or stdin) as NDJSON. |
| `gmac compliance-policies list` | `DeviceManagementConfiguration.Read.All` | List compliance-policies as NDJSON, one record per line. |
| `gmac configuration-profiles delete` | `DeviceManagementConfiguration.ReadWrite.All` | Delete configuration-profiles by id (arguments or stdin). **Dry run unless `--yes`.** |
| `gmac configuration-profiles get` | `DeviceManagementConfiguration.Read.All` | Fetch configuration-profiles by id (arguments or stdin) as NDJSON. |
| `gmac configuration-profiles list` | `DeviceManagementConfiguration.Read.All` | List configuration-profiles as NDJSON, one record per line. |
| `gmac devices delete` | `DeviceManagementManagedDevices.ReadWrite.All` | Delete devices by id (arguments or stdin). **Dry run unless `--yes`.** |
| `gmac devices get` | `DeviceManagementManagedDevices.Read.All` | Fetch devices by id (arguments or stdin) as NDJSON. |
| `gmac devices list` | `DeviceManagementManagedDevices.Read.All` | List devices as NDJSON, one record per line. |
| `gmac groups get` | `Group.Read.All` | Fetch groups by id (arguments or stdin) as NDJSON. |
| `gmac groups list` | `Group.Read.All` | List groups as NDJSON, one record per line. |
| `gmac users get` | `User.Read.All` | Fetch users by id (arguments or stdin) as NDJSON. |
| `gmac users list` | `User.Read.All` | List users as NDJSON, one record per line. |
<!-- commands:end -->

## Pipe conventions

- Records are NDJSON on stdout; logs and errors go to stderr.
- Commands that take ids (or serial numbers) accept them as arguments, or on stdin as objects with an `id` field
  (`--key` to change the field) or as bare lines (`jq -r .id`). `jq` output with quotes (`jq .id`) works too.
- Anything that changes something is a dry run unless `--yes`, and refuses more than `--max-items` (50) records.
- Output is stripped of known secrets (e.g. `adminAccountPassword` on enrollment profiles).
- ADE device records carry a `tokenId` field (Graph doesn't include it), so output from several
  tokens can be merged and still tell you which token each device belongs to.

```bash
gmac devices list \
  | jq -c 'select(.complianceState=="noncompliant" and .lastSyncDateTime < "2026-06-01")' \
  | gmac devices delete            # dry run; add --yes to delete

gmac ade tokens list | jq -c 'select(.tokenName=="Prod")' | gmac ade profiles list

# assign a profile to devices (devices on stdin; a full ECV2_ profile id carries its token)
gmac devices list | jq -c 'select(.serialNumber | startswith("C02"))' \
  | gmac ade profiles assign --profile "$PROFILE_ID"                      # dry run

# update profile settings (profiles on stdin, properties as --set or --patch-file)
gmac ade profiles list "$TOKEN_ID" | jq -c 'select(.displayName=="Standard")' \
  | gmac ade profiles update --set deviceNameTemplate='Mac-{{SERIAL}}' --set autoAdvanceSetupEnabled=true

# disabled users
gmac users list --filter "accountEnabled eq false" | jq -r .userPrincipalName
```

### Searching users and groups

Entra directory objects have `$search`, which gmac exposes as `--search` (users and groups only).
Graph requires `ConsistencyLevel: eventual` and `$count=true` for it; gmac sends both for you,
including on every page. Results can lag very recent changes.

```bash
gmac groups list --filter "startswith(displayName,'Mac')"      # starts with: a plain filter
gmac groups list --search '"displayName:lab"'                  # word match; keep the quotes
gmac groups list | jq -c 'select(.displayName | ascii_downcase | contains("lab"))'   # any substring
```

gmac does not expose Graph's other advanced-query features (`ne`/`not`/`endsWith` filters,
`$orderby` with `$filter`, `$count`): filter and sort client-side with `jq` instead.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyrefly check
```

## Design

```
graph_macos/
  graph/       transport: auth, client (retry, batching, paging), id helpers
  resources/   what Graph has: `Resource` specs + generic list/get/create/update/delete
  cli/         `gmac`: the factory turns specs into commands; commands/ holds custom verbs
```

Resources know nothing about the CLI, and the CLI knows nothing about specific endpoints, so
everything under `resources/` is usable as a library. `gmac --help` doesn't import `msal` or
`requests`; they load only when a command actually talks to Graph.

### Adding an endpoint

Most Graph collections are plain OData, so add a spec (see `resources/devices.py`):

```python
WIDGETS = Resource(
    path=("widgets",),  # becomes `gmac widgets <verb>`
    collection="/deviceManagement/widgets",
    help="Intune widgets.",
    read_scopes=("DeviceManagementWidgets.Read.All",),
    write_scopes=("DeviceManagementWidgets.ReadWrite.All",),
    verbs=frozenset({"list", "get", "delete"}),  # only what the endpoint supports
)
```

then add it to that module's `RESOURCES`. Options on `Resource` cover the usual quirks:
`parent` (sub-collections such as `{parent}/enrollmentProfiles`), `default_filter`,
`default_select`, `odata_type`, `redact` and `enrich`. Verbs that don't fit the CRUD shape
(like `ade profiles assign`) are plain functions in `resources/`, wired up in
`cli/commands/` and listed in `CUSTOM`. Write verbs get `--yes`/`--max-items` automatically.

After adding a command, refresh the table above and run the checks:

```bash
uv run python -m graph_macos.cli.docs --write
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run pyrefly check
```
