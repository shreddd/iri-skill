#!/usr/bin/env python3
"""Manage Globus tokens for authenticated IRI API calls."""

import argparse
import json
import os
import stat
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

CLIENT_ID = "fae5c579-490a-4d76-b6eb-d78f65caeb63"
RESOURCE_SERVER = "auth.globus.org"
REQUIRED_SCOPES = {
    "openid",
    "profile",
    "email",
    "urn:globus:auth:scope:auth.globus.org:view_identities",
}


def default_token_file() -> Path:
    return Path.home() / ".globus" / "auth_tokens.json"


def parse_scope_string(scope_string: str) -> Set[str]:
    return set(scope_string.split()) if scope_string else set()


def ensure_private_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)


def load_tokens(token_file: Path) -> Optional[Dict[str, Any]]:
    if not token_file.exists():
        return None
    with token_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(token_file: Path, tokens: Dict[str, Any]) -> None:
    ensure_private_parent_dir(token_file)
    tmp = token_file.with_suffix(".tmp")
    with os.fdopen(
        os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(tokens, f, indent=2)
    os.replace(tmp, token_file)
    os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)


def token_status(tokens: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    expires_at = int(tokens.get("expires_at_seconds", 0) or 0)
    granted = parse_scope_string(tokens.get("scope", ""))
    missing = sorted(REQUIRED_SCOPES - granted)
    return {
        "has_access_token": bool(tokens.get("access_token")),
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "expires_at_seconds": expires_at or None,
        "ttl_seconds": (expires_at - now) if expires_at else None,
        "granted_scopes": sorted(granted),
        "missing_required_scopes": missing,
        "valid_for_required_scopes": not missing,
    }


def print_status_human(token_file: Path, status: Dict[str, Any]) -> None:
    print(f"token_file: {token_file}")
    for key in [
        "has_access_token",
        "has_refresh_token",
        "expires_at_seconds",
        "ttl_seconds",
        "valid_for_required_scopes",
    ]:
        print(f"{key}: {status[key]}")
    print("granted_scopes:", " ".join(status["granted_scopes"]))
    if status["missing_required_scopes"]:
        print("missing_required_scopes:", " ".join(status["missing_required_scopes"]))


def interactive_login() -> Dict[str, Any]:
    try:
        import globus_sdk
    except ModuleNotFoundError as exc:
        raise RuntimeError("globus-sdk is required for login: pip install globus-sdk") from exc

    client = globus_sdk.NativeAppAuthClient(CLIENT_ID)
    client.oauth2_start_flow(
        requested_scopes=" ".join(sorted(REQUIRED_SCOPES)),
        refresh_tokens=True,
    )
    print("Open this URL, login, and consent:")
    print(client.oauth2_get_authorize_url())
    code = input("\nEnter authorization code: ").strip()
    token_response = client.oauth2_exchange_code_for_tokens(code)
    return token_response.by_resource_server[RESOURCE_SERVER]


def refresh_tokens(refresh_token: str) -> Optional[Dict[str, Any]]:
    try:
        import globus_sdk
        from globus_sdk.exc import GlobusAPIError
    except ModuleNotFoundError as exc:
        raise RuntimeError("globus-sdk is required for refresh: pip install globus-sdk") from exc

    client = globus_sdk.NativeAppAuthClient(CLIENT_ID)
    try:
        token_response = client.oauth2_refresh_token(refresh_token)
        return token_response.by_resource_server[RESOURCE_SERVER]
    except GlobusAPIError as exc:
        print(f"Refresh failed ({exc.http_status}); interactive login required.")
        return None


def cmd_status(args: argparse.Namespace) -> int:
    tokens = load_tokens(args.token_file)
    if tokens is None:
        if args.json:
            print(
                json.dumps(
                    {
                        "token_file": str(args.token_file),
                        "exists": False,
                        "status": None,
                    },
                    indent=2,
                )
            )
        else:
            print(f"token_file: {args.token_file}")
            print("exists: false")
        return 1

    status = token_status(tokens)
    if args.json:
        print(
            json.dumps(
                {
                    "token_file": str(args.token_file),
                    "exists": True,
                    "status": status,
                },
                indent=2,
            )
        )
    else:
        print_status_human(args.token_file, status)
    return 0


def cmd_ensure(args: argparse.Namespace) -> int:
    tokens = None if args.force_login else load_tokens(args.token_file)
    selected = None

    if tokens:
        status = token_status(tokens)
        ttl = status["ttl_seconds"]
        if (
            status["has_access_token"]
            and status["valid_for_required_scopes"]
            and ttl is not None
            and ttl >= args.min_ttl
        ):
            selected = tokens
        elif status["has_refresh_token"]:
            selected = refresh_tokens(tokens["refresh_token"])

    if selected is None:
        selected = interactive_login()

    status = token_status(selected)
    if not status["valid_for_required_scopes"]:
        raise RuntimeError(
            f"Missing required scopes: {status['missing_required_scopes']}"
        )

    save_tokens(args.token_file, selected)

    if args.json:
        output = {
            "token_file": str(args.token_file),
            "status": status,
            "access_token": selected.get("access_token") if args.print_token else None,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Saved token data to {args.token_file}")
        print_status_human(args.token_file, status)
        if args.print_token:
            print("\naccess_token:")
            print(selected["access_token"])

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, refresh, or obtain Globus tokens for IRI API."
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=default_token_file(),
        help="Path to token JSON (default: ~/.globus/auth_tokens.json)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Inspect token file state")
    status_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    status_parser.set_defaults(func=cmd_status)

    ensure_parser = subparsers.add_parser(
        "ensure",
        help="Ensure a usable token exists (reuse, refresh, or interactive login)",
    )
    ensure_parser.add_argument(
        "--min-ttl",
        type=int,
        default=300,
        help="Minimum TTL in seconds for reusing an existing access token",
    )
    ensure_parser.add_argument(
        "--force-login",
        action="store_true",
        help="Skip reuse/refresh and force interactive login",
    )
    ensure_parser.add_argument(
        "--print-token",
        action="store_true",
        help="Include the access token in output",
    )
    ensure_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    ensure_parser.set_defaults(func=cmd_ensure)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
