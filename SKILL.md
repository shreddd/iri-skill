---
name: iri-api
description: Use this skill to work with https://api.iri.nersc.gov via reproducible scripts, including Globus token lifecycle management (status, refresh, interactive login) and OpenAPI-driven endpoint execution for facility/status/account/compute/filesystem/task workflows. Trigger this skill when the task mentions IRI API, openapi.json-driven calls, authenticated endpoint access, job submission/status/cancel, file operations, or task polling/cleanup.
---

# IRI API

Use scripted workflows. Prefer the bundled scripts over hand-written `curl` commands.

## Quick Start

1. Check token state:
```bash
python3 scripts/token_manager.py status --json
```

2. Ensure a usable token for authenticated endpoints:
```bash
python3 scripts/token_manager.py ensure --min-ttl 300
```

If the IRI API still returns `401`, force a fresh identity-provider login:
```bash
python3 scripts/token_manager.py ensure --force-login --prompt-login --validate-iri
```

3. List available operations from OpenAPI:
```bash
python3 scripts/iri_api_call.py list-operations
```

4. Call an endpoint by `operationId`:
```bash
python3 scripts/iri_api_call.py call --operation-id getResources
```

## Token Management

Use `scripts/token_manager.py` for all token lifecycle actions.

- Inspect existing token:
```bash
python3 scripts/token_manager.py status
```

- Refresh or login only when needed:
```bash
python3 scripts/token_manager.py ensure --min-ttl 300
```

- Force new interactive consent flow:
```bash
python3 scripts/token_manager.py ensure --force-login
```

- Force a fresh IdP login prompt when server-side session state is bad:
```bash
python3 scripts/token_manager.py ensure --force-login --prompt-login
```

- Refresh saved tokens only, without opening a browser:
```bash
python3 scripts/token_manager.py ensure --refresh-only
```

- Validate the IRI bearer token against the API:
```bash
python3 scripts/token_manager.py ensure --validate-iri
```

- Emit machine-readable token metadata:
```bash
python3 scripts/token_manager.py ensure --json
```

Notes:
- Default token file: `~/.globus/auth_tokens.json`
- The saved file preserves the full Globus token response, including `other_tokens`.
- The usable IRI API bearer token is extracted from `other_tokens`, not the top-level Globus Auth token.
- Required scopes are enforced by script validation.
- `globus-sdk` is required for refresh/login operations.
- If validation reports empty `session_info.authentications`, re-run with `--force-login --prompt-login` and complete the flow in a Chrome incognito window.

## Endpoint Execution

Use `scripts/iri_api_call.py` for all API calls.

### Operation Discovery

- List all operations:
```bash
python3 scripts/iri_api_call.py list-operations
```

- See generated static reference:
`references/operations.md`

### Public Endpoints (No Token Required)

Examples:
```bash
python3 scripts/iri_api_call.py call --operation-id getFacility
python3 scripts/iri_api_call.py call --operation-id getIncidents
python3 scripts/iri_api_call.py call --operation-id getResource --path-param resource_id=perlmutter
```

### Authenticated Endpoints (Token Required)

Use `--ensure-token` so calls auto-refresh/login if needed.

- Account / project context:
```bash
python3 scripts/iri_api_call.py call --operation-id getProjects --ensure-token
```

- Submit compute job (request body from file):
```bash
python3 scripts/iri_api_call.py call \
  --operation-id launchJob \
  --path-param resource_id=perlmutter \
  --json-file /path/to/job.json \
  --ensure-token
```

- Query one job:
```bash
python3 scripts/iri_api_call.py call \
  --operation-id getJob \
  --path-param resource_id=perlmutter \
  --path-param job_id=12345 \
  --ensure-token
```

- Cancel job:
```bash
python3 scripts/iri_api_call.py call \
  --operation-id cancelJob \
  --path-param resource_id=perlmutter \
  --path-param job_id=12345 \
  --ensure-token
```

- Filesystem list/view:

  Use the storage resource name that matches the path prefix — **not** `perlmutter`:

  | Path prefix | `resource_id` to use |
  |---|---|
  | `/global/homes/` or `/global/u1/` | `homes` |
  | `/pscratch/` | `scratch` |
  | `/global/cfs/` | `cfs` |
  | `/global/common/` | `common` |

```bash
RESOURCE=<homes|scratch|cfs|common>   # pick based on path prefix above

python3 scripts/iri_api_call.py call \
  --operation-id ls \
  --path-param resource_id=$RESOURCE \
  --query path=/path/to/directory \
  --ensure-token

python3 scripts/iri_api_call.py call \
  --operation-id view \
  --path-param resource_id=$RESOURCE \
  --query path=/path/to/file.txt \
  --ensure-token
```

- Upload file:
```bash
RESOURCE=<homes|scratch|cfs|common>   # pick based on destination path prefix

python3 scripts/iri_api_call.py call \
  --operation-id upload \
  --path-param resource_id=$RESOURCE \
  --query path=/path/on/resource/target.dat \
  --upload-file /local/path/source.dat \
  --ensure-token
```

- Poll task state:
```bash
python3 scripts/iri_api_call.py call --operation-id getTasks --ensure-token
python3 scripts/iri_api_call.py call --operation-id getTask --path-param task_id=<task_id> --ensure-token
```

## Path Rules for Job and Filesystem Specs

**Never use shell variables (`$HOME`, `$SCRATCH`, `$USER`) in job or filesystem JSON bodies.** The IRI API passes these values as literal strings — they are not expanded by the shell or by Slurm. Use absolute paths instead.

Perlmutter home directories follow the pattern `/global/homes/<first-letter>/<username>` (e.g. `/global/homes/s/shreyas`). Scratch is at `/pscratch/sd/<first-letter>/<username>`.

Always substitute real paths before submitting. The example templates use `<first-letter>/<username>` placeholders — replace them with actual values.

## Parameter and Body Rules

- Prefer `--operation-id` over manual `--method/--path`.
- Provide required path params via repeated `--path-param key=value`.
- Provide query params via repeated `--query key=value`.
- Use one of:
  - `--json-file /path/to/body.json`
  - `--json-body '{"key":"value"}'`
  - `--upload-file /path/to/local.file` for multipart endpoints
- For binary or large outputs, use `--output-file /path/to/out.bin`.

## Reproducibility and Reference Refresh

Regenerate endpoint reference after OpenAPI updates:

```bash
python3 scripts/generate_operation_reference.py \
  --openapi references/openapi.json \
  --output references/operations.md
```

Regenerate request payload templates:

```bash
python3 scripts/generate_examples.py
```

Use templates from `references/examples/`:
- `compute-launch-job.json`
- `compute-status-filters.json`
- `filesystem-mkdir.json`
- `filesystem-mv.json`
- `filesystem-cp.json`
- `filesystem-compress.json`
- `filesystem-extract.json`
- `filesystem-chmod.json`
- `filesystem-chown.json`

Example calls using generated templates:

```bash
python3 scripts/iri_api_call.py call \
  --operation-id launchJob \
  --path-param resource_id=perlmutter \
  --json-file references/examples/compute-launch-job.json \
  --ensure-token

python3 scripts/iri_api_call.py call \
  --operation-id mkdir \
  --path-param resource_id=$RESOURCE \
  --json-file references/examples/filesystem-mkdir.json \
  --ensure-token
```

## Useful Endpoint Groups

Use these operation families most often:
- Facility + status (public): infrastructure metadata and incident visibility.
- Account (auth): user projects and allocation hierarchy.
- Compute (auth): submit/update/status/cancel jobs.
- Filesystem (auth): list/read/write/upload/download and file operations.
- Task (auth): check asynchronous task progress and cleanup.
