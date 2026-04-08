---
name: iri-api
description: Use this skill to work with IRI API deployments at NERSC (https://api.iri.nersc.gov) and ALCF (https://api.alcf.anl.gov) via reproducible scripts, including Globus token lifecycle management (status, refresh, interactive login) and OpenAPI-driven endpoint execution for facility/status/account/compute/filesystem/task workflows. Trigger this skill when the task mentions IRI API, openapi.json-driven calls, authenticated endpoint access, job submission/status/cancel, file operations, task polling/cleanup, or running jobs on Perlmutter or Polaris.
---

# IRI API

Use scripted workflows. Prefer the bundled scripts over hand-written `curl` commands.

## Deployments

| Site | Base URL | Auth script | Reference |
|---|---|---|---|
| NERSC (Perlmutter) | `https://api.iri.nersc.gov` (default) | `scripts/token_manager.py` | `references/NERSC.md` |
| ALCF (Polaris) | `https://api.alcf.anl.gov` | `scripts/alcf_token_manager.py` | `references/ALCF.md` |

**Before doing any work**, read the reference file for the relevant site. Do not proceed from memory.

All `iri_api_call.py` commands accept `--base-url` to select the deployment.

## Shared Parameter Rules

- Prefer `--operation-id` over manual `--method/--path`.
- Provide required path params via repeated `--path-param key=value`.
- Provide query params via repeated `--query key=value`.
- Use one of:
  - `--json-file /path/to/body.json`
  - `--json-body '{"key":"value"}'`
  - `--upload-file /path/to/local.file` for multipart endpoints
- For binary or large outputs, use `--output-file /path/to/out.bin`.

## Useful Endpoint Groups

- Facility + status (public): infrastructure metadata and incident visibility.
- Account (auth): user projects and allocation hierarchy.
- Compute (auth): submit/update/status/cancel jobs.
- Filesystem (auth): list/read/write/upload/download and file operations.
- Task (auth): check asynchronous task progress and cleanup.
