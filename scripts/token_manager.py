#!/usr/bin/env python3
"""Manage Globus tokens for authenticated IRI API calls."""

import argparse
import json
import os
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

CLIENT_ID = "fae5c579-490a-4d76-b6eb-d78f65caeb63"
RESOURCE_SERVER = "auth.globus.org"
IRI_SCOPE = (
    "https://auth.globus.org/scopes/"
    "ed3e577d-f7f3-4639-b96e-ff5a8445d699/iri_api"
)
REQUIRED_SCOPES = {
    "openid",
    "profile",
    "email",
    "urn:globus:auth:scope:auth.globus.org:view_identities",
}
REQUESTED_SCOPES = REQUIRED_SCOPES | {IRI_SCOPE}
DEFAULT_IRI_VALIDATE_URL = "https://api.iri.nersc.gov/api/v1/account/projects"


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


def get_refresh_token(stored_tokens: Dict[str, Any]) -> Optional[str]:
    if "refresh_token" in stored_tokens:
        return stored_tokens.get("refresh_token")

    auth_tokens = stored_tokens.get(RESOURCE_SERVER)
    if isinstance(auth_tokens, dict):
        return auth_tokens.get("refresh_token")

    return None


def get_iri_token(token_response_data: Dict[str, Any]) -> Dict[str, Any]:
    for token_data in token_response_data.get("other_tokens", []):
        if IRI_SCOPE in parse_scope_string(token_data.get("scope", "")):
            return token_data
    raise RuntimeError(f"Missing token for required IRI scope: {IRI_SCOPE}")


def get_iri_refresh_token(stored_tokens: Dict[str, Any]) -> Optional[str]:
    try:
        return get_iri_token(stored_tokens).get("refresh_token")
    except RuntimeError:
        return None


def replace_iri_token(
    token_response_data: Dict[str, Any], iri_token_data: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(token_response_data)
    other_tokens = list(merged.get("other_tokens", []))
    for index, token_data in enumerate(other_tokens):
        if IRI_SCOPE in parse_scope_string(token_data.get("scope", "")):
            other_tokens[index] = iri_token_data
            break
    else:
        other_tokens.append(iri_token_data)
    merged["other_tokens"] = other_tokens
    return merged


def validate_auth_data(auth_data: Dict[str, Any]) -> Dict[str, Any]:
    if auth_data.get("resource_server") != RESOURCE_SERVER:
        raise RuntimeError(
            f"Missing token for required resource server: {RESOURCE_SERVER}"
        )

    granted = parse_scope_string(auth_data.get("scope", ""))
    missing = REQUIRED_SCOPES - granted
    if missing:
        raise RuntimeError(f"Missing required scopes: {sorted(missing)}")

    return get_iri_token(auth_data)


def validate_iri_token(iri_token_data: Dict[str, Any], validate_url: str) -> Any:
    request = urllib.request.Request(
        validate_url,
        headers={
            "accept": "application/json",
            "Authorization": f"Bearer {iri_token_data['access_token']}",
            "User-Agent": "iri-api-client/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        details = body.strip() or exc.reason
        raise RuntimeError(
            f"IRI validation failed with HTTP {exc.code} from {validate_url}: {details}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"IRI validation request failed for {validate_url}: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"IRI validation returned non-JSON data from {validate_url}"
        ) from exc

    if isinstance(data, dict):
        session_info = data.get("session_info")
        if isinstance(session_info, dict):
            authentications = session_info.get("authentications")
            if isinstance(authentications, dict) and not authentications:
                raise RuntimeError(
                    "IRI validation succeeded but session_info.authentications is empty. "
                    "Re-run with --force-login --prompt-login and use a Chrome incognito window."
                )

    return data


def token_status(tokens: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    auth_expires_at = int(tokens.get("expires_at_seconds", 0) or 0)
    auth_granted = parse_scope_string(tokens.get("scope", ""))
    auth_missing = sorted(REQUIRED_SCOPES - auth_granted)

    iri_token_data = None  # type: Optional[Dict[str, Any]]
    iri_missing = [IRI_SCOPE]  # type: List[str]
    iri_expires_at = None  # type: Optional[int]
    iri_granted = []  # type: List[str]
    iri_resource_server = None  # type: Optional[str]
    iri_has_access_token = False
    iri_has_refresh_token = False
    iri_ttl = None  # type: Optional[int]
    try:
        iri_token_data = get_iri_token(tokens)
        iri_granted_set = parse_scope_string(iri_token_data.get("scope", ""))
        iri_missing = sorted({IRI_SCOPE} - iri_granted_set)
        iri_expires_at = int(iri_token_data.get("expires_at_seconds", 0) or 0) or None
        iri_granted = sorted(iri_granted_set)
        iri_resource_server = iri_token_data.get("resource_server")
        iri_has_access_token = bool(iri_token_data.get("access_token"))
        iri_has_refresh_token = bool(iri_token_data.get("refresh_token"))
        iri_ttl = (iri_expires_at - now) if iri_expires_at else None
    except RuntimeError:
        iri_token_data = None

    return {
        "has_access_token": iri_has_access_token,
        "has_refresh_token": iri_has_refresh_token,
        "expires_at_seconds": iri_expires_at,
        "ttl_seconds": iri_ttl,
        "granted_scopes": iri_granted,
        "missing_required_scopes": iri_missing,
        "valid_for_required_scopes": not iri_missing,
        "auth_resource_server": tokens.get("resource_server"),
        "auth_has_access_token": bool(tokens.get("access_token")),
        "auth_has_refresh_token": bool(get_refresh_token(tokens)),
        "auth_expires_at_seconds": auth_expires_at or None,
        "auth_ttl_seconds": (auth_expires_at - now) if auth_expires_at else None,
        "auth_granted_scopes": sorted(auth_granted),
        "auth_missing_required_scopes": auth_missing,
        "auth_valid_for_required_scopes": not auth_missing,
        "iri_resource_server": iri_resource_server,
        "iri_token_found": iri_token_data is not None,
    }


def print_status_human(token_file: Path, status: Dict[str, Any]) -> None:
    print(f"token_file: {token_file}")
    for key in [
        "has_access_token",
        "has_refresh_token",
        "expires_at_seconds",
        "ttl_seconds",
        "valid_for_required_scopes",
        "iri_resource_server",
        "iri_token_found",
    ]:
        print(f"{key}: {status[key]}")
    print("granted_scopes:", " ".join(status["granted_scopes"]))
    if status["missing_required_scopes"]:
        print("missing_required_scopes:", " ".join(status["missing_required_scopes"]))
    print("auth_granted_scopes:", " ".join(status["auth_granted_scopes"]))
    if status["auth_missing_required_scopes"]:
        print(
            "auth_missing_required_scopes:",
            " ".join(status["auth_missing_required_scopes"]),
        )


def interactive_login(prompt_login: bool = False) -> Dict[str, Any]:
    try:
        import globus_sdk
        from globus_sdk.exc import GlobusAPIError
    except ModuleNotFoundError as exc:
        raise RuntimeError("globus-sdk is required for login: pip install globus-sdk") from exc

    client = globus_sdk.NativeAppAuthClient(CLIENT_ID)
    client.oauth2_start_flow(
        requested_scopes=" ".join(sorted(REQUESTED_SCOPES)),
        refresh_tokens=True,
    )
    print("Open this URL, login, and consent:")
    prompt = "login" if prompt_login else globus_sdk.MISSING
    print(client.oauth2_get_authorize_url(prompt=prompt))
    code = input("\nEnter authorization code: ").strip()
    if not code:
        raise RuntimeError(
            "No authorization code entered. Re-run the script and paste the code "
            "shown by Globus after login."
        )
    try:
        token_response = client.oauth2_exchange_code_for_tokens(code)
    except GlobusAPIError as exc:
        if exc.http_status == 400:
            raise RuntimeError(
                "Authorization code exchange failed. The code was empty, invalid, "
                "expired, or already used. Re-run the script and complete the "
                "Globus login flow again."
            ) from exc
        raise RuntimeError(
            f"Authorization code exchange failed with HTTP {exc.http_status}. "
            "Re-run the script and try again."
        ) from exc
    return token_response.data


def refresh_tokens(refresh_token: str) -> Optional[Dict[str, Any]]:
    try:
        import globus_sdk
        from globus_sdk.exc import GlobusAPIError
    except ModuleNotFoundError as exc:
        raise RuntimeError("globus-sdk is required for refresh: pip install globus-sdk") from exc

    client = globus_sdk.NativeAppAuthClient(CLIENT_ID)
    try:
        token_response = client.oauth2_refresh_token(refresh_token)
        return token_response.data
    except GlobusAPIError as exc:
        print(f"Refresh failed ({exc.http_status}); switching to interactive login.")
        return None


def refresh_stored_tokens(
    stored_tokens: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], bool]:
    iri_refresh_token = get_iri_refresh_token(stored_tokens)
    if iri_refresh_token:
        iri_token_data = refresh_tokens(iri_refresh_token)
        if iri_token_data is not None:
            return replace_iri_token(stored_tokens, iri_token_data), True

    auth_refresh_token = get_refresh_token(stored_tokens)
    if auth_refresh_token:
        auth_data = refresh_tokens(auth_refresh_token)
        if auth_data is not None:
            return auth_data, True

    return None, False


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
    if args.force_login and args.refresh_only:
        raise RuntimeError("Choose only one of --force-login or --refresh-only")

    tokens = None if args.force_login else load_tokens(args.token_file)
    auth_data = None  # type: Optional[Dict[str, Any]]
    used_refresh = False

    if tokens:
        status = token_status(tokens)
        ttl = status["ttl_seconds"]
        if (
            status["has_access_token"]
            and status["valid_for_required_scopes"]
            and ttl is not None
            and ttl >= args.min_ttl
        ):
            auth_data = tokens
        else:
            auth_data, used_refresh = refresh_stored_tokens(tokens)

    if auth_data is None:
        if args.refresh_only:
            raise RuntimeError(
                "Refresh-only mode failed. No usable saved refresh token was found "
                "or token refresh did not return the required IRI token."
            )
        auth_data = interactive_login(prompt_login=args.prompt_login)

    try:
        iri_token_data = validate_auth_data(auth_data)
    except RuntimeError as exc:
        if used_refresh and "Missing token for required IRI scope" in str(exc):
            print(
                "Refreshed tokens did not include the IRI token; "
                "switching to interactive login."
            )
            auth_data = interactive_login(prompt_login=args.prompt_login)
            iri_token_data = validate_auth_data(auth_data)
        else:
            raise

    save_tokens(args.token_file, auth_data)

    validation_data = None  # type: Any
    if args.validate_iri:
        validation_data = validate_iri_token(iri_token_data, args.iri_validate_url)

    status = token_status(auth_data)
    if args.json:
        output = {
            "token_file": str(args.token_file),
            "status": status,
            "access_token": iri_token_data.get("access_token") if args.print_token else None,
            "iri_validate_url": args.iri_validate_url if args.validate_iri else None,
            "iri_validation": validation_data if args.validate_iri else None,
        }
        print(json.dumps(output, indent=2))
    else:
        if args.validate_iri:
            print(f"IRI validation succeeded against {args.iri_validate_url}")
            if isinstance(validation_data, dict):
                session_info = validation_data.get("session_info")
                if isinstance(session_info, dict):
                    session_id = session_info.get("session_id")
                    if session_id:
                        print(f"IRI session_id: {session_id}")
            elif isinstance(validation_data, list):
                print(f"IRI validation response items: {len(validation_data)}")

        expires_at = iri_token_data.get("expires_at_seconds")
        if expires_at:
            ttl = int(expires_at - time.time())
            print(f"\nIRI access token valid for ~{max(ttl, 0)} seconds.")

        print(f"Saved token data to {args.token_file}")
        print(f"Granted Globus Auth scopes: {auth_data.get('scope', '')}")
        print(f"IRI token resource server: {iri_token_data.get('resource_server')}")
        print(f"IRI token scopes: {iri_token_data.get('scope', '')}")

        if args.print_token:
            print("\nIRI access token:")
            print(iri_token_data["access_token"])
        else:
            print(
                "IRI access token not printed "
                "(use --print-token to display it for the NERSC IRI API)."
            )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, refresh, validate, or obtain Globus tokens for IRI API."
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
        help="Ensure a usable IRI token exists (reuse, refresh, or interactive login)",
    )
    ensure_parser.add_argument(
        "--min-ttl",
        type=int,
        default=300,
        help="Minimum TTL in seconds for reusing an existing IRI access token",
    )
    ensure_parser.add_argument(
        "--force-login",
        action="store_true",
        help="Skip reuse/refresh and force interactive login",
    )
    ensure_parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Refresh saved tokens only; do not fall back to interactive login",
    )
    ensure_parser.add_argument(
        "--prompt-login",
        action="store_true",
        help="Add prompt=login to the authorize URL to force IdP re-authentication",
    )
    ensure_parser.add_argument(
        "--validate-iri",
        action="store_true",
        help="Validate the IRI token by calling an IRI endpoint",
    )
    ensure_parser.add_argument(
        "--iri-validate-url",
        default=DEFAULT_IRI_VALIDATE_URL,
        help=f"IRI endpoint used by --validate-iri (default: {DEFAULT_IRI_VALIDATE_URL})",
    )
    ensure_parser.add_argument(
        "--print-token",
        action="store_true",
        help="Include the IRI access token in output",
    )
    ensure_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    ensure_parser.set_defaults(func=cmd_ensure)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
