# ALCF IRI API (Polaris)

**Base URL:** `https://api.alcf.anl.gov`

ALCF uses a separate Globus auth flow and UUID-based resource IDs. Aurora compute is not yet implemented in the ALCF IRI API — use **Polaris** for job submission.

## Authentication

ALCF uses a different Globus client and scope than NERSC. Use `scripts/alcf_token_manager.py`:

```bash
# First-time login (interactive — must run in a real terminal):
python3 scripts/alcf_token_manager.py authenticate

# Get current access token (reuses/refreshes stored tokens):
python3 scripts/alcf_token_manager.py get_access_token

# Check time remaining:
python3 scripts/alcf_token_manager.py get_time_until_token_expiration --units minutes
```

Token file: `~/.globus/app/8b84fc2d-49e9-49ea-b54d-b3a29a70cf31/alcf_facility_api_app/tokens.json`

Pass the token to `iri_api_call.py` via `--bearer-token` (ALCF token format is incompatible with `--token-file`):

```bash
TOKEN=$(python3 scripts/alcf_token_manager.py get_access_token)
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id <operationId> \
  --bearer-token "$TOKEN"
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
  "directory": "/home/shreyas",
  "stdout_path": "/home/shreyas/out.txt",
  "stderr_path": "/home/shreyas/err.txt",
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
TOKEN=$(python3 scripts/alcf_token_manager.py get_access_token)

python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id launchJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --json-file polaris-job.json \
  --bearer-token "$TOKEN"
```

Check a job:

```bash
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id getJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --path-param job_id=<job_id> \
  --bearer-token "$TOKEN"
```

List your jobs:

```bash
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id getJobs \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --json-body '{}' \
  --bearer-token "$TOKEN"
```

Cancel a job:

```bash
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id cancelJob \
  --path-param resource_id=55c1c993-1124-47f9-b823-514ba3849a9a \
  --path-param job_id=<job_id> \
  --bearer-token "$TOKEN"
```

## Filesystem Operations

Filesystem operations return a `task_id` — poll with `getTask` until `status` is `completed`.

```bash
TOKEN=$(python3 scripts/alcf_token_manager.py get_access_token)

# List directory:
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id ls \
  --path-param resource_id=6115bd2c-957a-4543-abff-5fae52992ff2 \
  --query path=/home/shreyas/ \
  --bearer-token "$TOKEN"

# Poll task result:
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id getTask \
  --path-param task_id=<task_id> \
  --bearer-token "$TOKEN"

# View file:
python3 scripts/iri_api_call.py call \
  --base-url https://api.alcf.anl.gov \
  --operation-id view \
  --path-param resource_id=6115bd2c-957a-4543-abff-5fae52992ff2 \
  --query path=/home/shreyas/file.txt \
  --bearer-token "$TOKEN"
```
