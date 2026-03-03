#!/usr/bin/env python3
"""Generate reproducible JSON request templates for common IRI API operations."""

import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out = root / "references" / "examples"

    templates: dict[str, dict] = {
        "compute-launch-job.json": {
            "name": "iri-sample-job",
            "executable": "/bin/hostname",
            "arguments": [],
            "directory": "$HOME",
            "stdout_path": "$HOME/iri-job.out",
            "stderr_path": "$HOME/iri-job.err",
            "launcher": "srun",
            "resources": {
                "node_count": 1,
                "process_count": 1,
                "processes_per_node": 1,
                "cpu_cores_per_process": 1
            },
            "attributes": {
                "duration": 300,
                "queue_name": "debug",
                "account": "<replace-with-project-account>"
            },
            "environment": {
                "OMP_NUM_THREADS": "1"
            }
        },
        "compute-status-filters.json": {
            "ids": [
                "<job-id-1>",
                "<job-id-2>"
            ]
        },
        "filesystem-mkdir.json": {
            "path": "$HOME/iri-demo/newdir",
            "parent": True
        },
        "filesystem-mv.json": {
            "path": "$HOME/iri-demo/input.txt",
            "target_path": "$HOME/iri-demo/input.renamed.txt"
        },
        "filesystem-cp.json": {
            "path": "$HOME/iri-demo/input.txt",
            "target_path": "$HOME/iri-demo/input.copy.txt",
            "dereference": False
        },
        "filesystem-compress.json": {
            "path": "$HOME/iri-demo",
            "target_path": "$HOME/iri-demo.tar.gz",
            "match_pattern": ".*",
            "dereference": False,
            "compression": "gzip"
        },
        "filesystem-extract.json": {
            "path": "$HOME/iri-demo.tar.gz",
            "target_path": "$HOME/iri-demo-extracted",
            "compression": "gzip"
        },
        "filesystem-chmod.json": {
            "path": "$HOME/iri-demo/input.txt",
            "mode": "640"
        },
        "filesystem-chown.json": {
            "path": "$HOME/iri-demo/input.txt",
            "owner": "$USER",
            "group": "<replace-with-group>"
        }
    }

    for name, payload in templates.items():
        write_json(out / name, payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
