#!/usr/bin/env python3
"""Utility for syncing the local workspace to a Hugging Face Space via HfApi."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from huggingface_hub import HfApi, SpaceHardware, SpaceStorage
from huggingface_hub.errors import HfHubHTTPError

DEFAULT_REPO_ID = "MCP-1st-Birthday/vawlrathh"
DEFAULT_REPO_TYPE = "space"
DEFAULT_REVISION = "main"
DEFAULT_SPACE_SDK = "gradio"
DEFAULT_IGNORE = [
    ".git/",
    ".git/*",
    "__pycache__/",
    "__pycache__/*",
    "*.pyc",
    ".DS_Store",
    "*.log",
    "*.tmp",
    ".pytest_cache/",
    ".pytest_cache/*",
    ".mypy_cache/",
    ".mypy_cache/*",
    ".ruff_cache/",
    ".ruff_cache/*",
    ".idea/",
    ".idea/*",
    ".vscode/",
    ".vscode/*",
    ".env",
    ".env.*",
    "env/",
    "env/*",
    ".venv/",
    ".venv/*",
    "venv/",
    "venv/*",
    "data/cache/",
    "data/cache/*",
    "data/cache/**",
    "data/.cache/",
    "data/.cache/*",
    "data/.cache/**",
    "cache/",
    "cache/*",
    "cache/**",
    "hf_payload_manifest.json",
    "**/hf_payload_manifest.json",
]


class SpaceAwareHfApi(HfApi):
    """Inject default space_sdk when the hub call forgets to set one."""

    def __init__(
        self,
        *,
        default_space_sdk: str = DEFAULT_SPACE_SDK,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._default_space_sdk = default_space_sdk

    def create_repo(
        self,
        repo_id: str,
        *,
        token: Optional[str] = None,
        private: Optional[bool] = None,
        repo_type: Optional[str] = None,
        exist_ok: bool = False,
        resource_group_id: Optional[str] = None,
        space_sdk: Optional[str] = None,
        space_hardware: Optional[SpaceHardware] = None,
        space_storage: Optional[SpaceStorage] = None,
        space_sleep_time: Optional[int] = None,
        space_secrets: Optional[List[dict[str, str]]] = None,
        space_variables: Optional[List[dict[str, str]]] = None,
    ):
        if repo_type == "space" and space_sdk is None:
            space_sdk = self._default_space_sdk
        return super().create_repo(
            repo_id,
            token=token,
            private=private,
            repo_type=repo_type,
            exist_ok=exist_ok,
            resource_group_id=resource_group_id,
            space_sdk=space_sdk,
            space_hardware=space_hardware,
            space_storage=space_storage,
            space_sleep_time=space_sleep_time,
            space_secrets=space_secrets,
            space_variables=space_variables,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--folder",
        default=".",
        help="Local folder to upload (defaults to repository root).",
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help="Target Hugging Face repo id (e.g. org/name).",
    )
    parser.add_argument(
        "--repo-type",
        default=DEFAULT_REPO_TYPE,
        choices=["model", "dataset", "space"],
        help="Target repository type (defaults to space).",
    )
    parser.add_argument(
        "--revision",
        default=DEFAULT_REVISION,
        help="Branch/revision to push to (defaults to main).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Explicit Hugging Face token. If omitted HF_TOKEN env var is used."
        ),
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Mark repo as private when auto-creating it.",
    )
    parser.add_argument(
        "--space-sdk",
        default=DEFAULT_SPACE_SDK,
        choices=["gradio", "streamlit", "docker", "static"],
        help=(
            "SDK to use when ensuring a Space repo exists "
            "(defaults to gradio)."
        ),
    )
    parser.add_argument(
        "--allow",
        nargs="*",
        default=None,
        help="Optional allow-pattern list to restrict uploads.",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=None,
        help="Additional ignore patterns beyond defaults and .gitignore.",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Override worker count used by upload_large_folder.",
    )
    parser.add_argument(
        "--print-report-every",
        type=int,
        default=60,
        help="Seconds between progress reports (default: 60).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable periodic progress printing.",
    )
    return parser.parse_args()


def read_gitignore_patterns(root: Path) -> List[str]:
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []

    patterns: List[str] = []
    for raw in gitignore_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            # upload_large_folder doesn't support negated patterns; skip them
            continue
        patterns.append(line)
    return patterns


def build_ignore_list(root: Path, extra: Optional[Iterable[str]]) -> List[str]:
    patterns = list(DEFAULT_IGNORE)
    patterns.extend(read_gitignore_patterns(root))
    if extra:
        patterns.extend(extra)
    cleaned = []
    seen = set()
    for pattern in patterns:
        normalized = pattern.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def main() -> None:
    args = parse_args()
    folder = Path(args.folder).resolve()
    if not folder.exists():
        print(f"Folder '{folder}' does not exist", file=sys.stderr)
        raise SystemExit(2)

    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        print(
            "HF_TOKEN is required. Pass --token or set env var.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    api = SpaceAwareHfApi(default_space_sdk=args.space_sdk, token=token)

    try:
        who = api.whoami(token=token)
    except HfHubHTTPError as exc:
        print(
            f"Failed to authenticate with Hugging Face Hub: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(
        f"Authenticated as: {who.get('name') or who.get('email') or 'unknown'}"
    )
    ignore_patterns = build_ignore_list(folder, args.ignore)
    allow_patterns = args.allow or None

    print("Preparing upload with the following settings:")
    print(f"  repo_id: {args.repo_id}")
    print(f"  repo_type: {args.repo_type}")
    print(f"  revision: {args.revision}")
    print(f"  folder: {folder}")
    if allow_patterns:
        print(f"  allow_patterns: {allow_patterns}")
    print(f"  ignore_patterns: {ignore_patterns}")

    try:
        api.upload_large_folder(
            repo_id=args.repo_id,
            folder_path=str(folder),
            repo_type=args.repo_type,
            revision=args.revision,
            private=args.private,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            num_workers=args.num_workers,
            print_report=not args.quiet,
            print_report_every=args.print_report_every,
        )
    except HfHubHTTPError as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("Upload complete.")


if __name__ == "__main__":
    main()
