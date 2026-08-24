#!/usr/bin/env python3
"""Create ignored, local-only credentials for the disposable test stack."""

from __future__ import annotations

import argparse
import os
import secrets
import string
from pathlib import Path


def random_alphanumeric(length: int = 36) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def write_config(path: Path, force: bool) -> bool:
    if path.exists() and not force:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "# Generated locally by tools/create_test_environment_config.py.",
            "# This file is ignored by Git. Do not commit or share it.",
            f"IMMICH_DB_PASSWORD={random_alphanumeric()}",
            f"COMPANION_DB_PASSWORD={random_alphanumeric()}",
            f"IMMICH_TEST_ADMIN_PASSWORD={random_alphanumeric()}",
            "",
        ]
    )

    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    created = write_config(args.output.resolve(), args.force)
    action = "Created" if created else "Reused"
    print(f"{action} local test configuration at {args.output}")


if __name__ == "__main__":
    main()
