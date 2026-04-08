# ALCF IRI API (Polaris)

**Base URL:** `https://api.alcf.anl.gov`

ALCF uses a facility-specific Globus scope and UUID-based resource IDs. Aurora compute is not yet implemented in the ALCF IRI API, so use **Polaris** for job submission.

## Authentication

Use the unified token manager and scope it to ALCF:

```bash
# First-time login or refresh as needed:
python3 scripts/token_manager.py ensure --facilities alcf --min-ttl 300

# Validate the ALCF token against the ALCF API:
python3 scripts/token_manager.py \
  ensure \
  --facilities alcf \
  --validate-iri \
  --validate-facility alcf

# Print the current ALCF access token if you explicitly need it:
python3 scripts/token_manager.py ensure --facilities alcf --print-token
```

Default token file: `~/.globus/auth_tokens.json`

Use `iri_api_call.py --facility alcf` so the API server and the ALCF token stay aligned:

```bash
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id <operationId> \
  --ensure-token
```

## Resource IDs

Unlike NERSC (short names like `perlmutter`), ALCF uses UUIDs:

| Name | UUID | Type |
|---|---|---|
| Polaris | `55c1c993-1124-47f9-b823-514ba3849a9a` | compute |
| Aurora | `0325fc07-6fb7-4453-b772-3d5030b2df72` | compute (API not yet implemented) |
| Crux | `8b9b42f7-572a-4909-8472-a0453436304c` | compute |
| Sophia | `9674c7e1-aecc-4dbb-bf01-c9197e027cd6` | compute |
| Home | `6115bd2c-957a-4543-abff-5fae52992ff2` | storage |
| Eagle | `1c3ad9d4-2e91-42bc-becb-72b1fde1235c` | storage |

## Filesystem Paths

**Never use shell variables** (`$HOME`, `$USER`) in job or filesystem JSON — the API passes them as literal strings.

| Filesystem | Path pattern | `resource_id` |
|---|---|---|
| Home | `/home/<username>` | `6115bd2c-957a-4543-abff-5fae52992ff2` |
| Eagle (scratch/project) | `/eagle/<project>` | `1c3ad9d4-2e91-42bc-becb-72b1fde1235c` |

## Polaris Job Submission

Polaris uses PBS. Set `attributes.custom_attributes.filesystems` to declare which filesystems the job needs.

**Queues:**

| Queue | Nodes | Walltime |
|---|---|---|
| `debug` | 1–2 | 5 min – 1 hr |
| `debug-scaling` | 1–10 | 5 min – 1 hr |
| `prod` | 10–496 | 5 min – 24 hrs |
| `preemptable` | 1–10 | 5 min – 72 hrs |
| `capacity` | 1–4 | 5 min – 168 hrs |

**Example job spec** (`polaris-job.json`):

```json
{
  "name": "my-job",
  "executable": "/bin/bash",
  "arguments": ["-c", "echo hello from $(hostname)"],
  "directory": "/home/username",
  "stdout_path": "/home/username/out.txt",
  "stderr_path": "/home/username/err.txt",
  "resources": {
    "node_count": 1
  },
  "attributes": {
    "duration": 300,
    "queue_name": "debug",
    "account": "ModCon",
    "custom_attributes": {
      "filesystems": "home:eagle"
    }
  }
}
```

Submit a job:

```bash
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id launchJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --json-file polaris-job.json \
  --ensure-token
```

Check a job:

```bash
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id getJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --path-param job_id=<job_id> \
  --ensure-token
```

List your jobs:

```bash
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id getJobs \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --json-body '{}' \
  --ensure-token
```

Cancel a job:

```bash
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id cancelJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --path-param job_id=<job_id> \
  --ensure-token
```

If the user wants a multistep Polaris job, additional PBS behavior beyond the supported `attributes`, or affinity/binding control, put that logic in `pre_launch` or `post_launch` scripts. Do not include `#PBS` directives in those scripts, because the API server generates the batch script wrapper.

## Filesystem Operations

Filesystem operations return a `task_id`; poll with `getTask` until `status` is `completed`.

```bash
# List directory:
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id ls \
  --path-param resource_id=6115bd2c-957a-4543-abff-5fae52992ff2 \
  --query path=/home/username/ \
  --ensure-token

# Poll task result:
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id getTask \
  --path-param task_id=<task_id> \
  --ensure-token

# View file:
python3 scripts/iri_api_call.py call \
  --facility alcf \
  --operation-id view \
  --path-param resource_id=6115bd2c-957a-4543-abff-5fae52992ff2 \
  --query path=/home/username/file.txt \
  --ensure-token
```
