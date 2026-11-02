#!/usr/bin/env python3
"""Prepare only Azure Speech configuration; never print subscription keys."""

import argparse
import getpass
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

FIELDS = {"AZURE_SPEECH_KEY", "AZURE_API_KEY_1", "AZURE_SPEECH_REGION"}


def read_config(source):
    """Read literal Azure fields from a dotenv file, ignoring all other keys.

    Accepts quoted/unquoted values, comments and optional `export`. Deliberately
    does not expand variables or execute shell syntax.
    """
    values = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Z_0-9]+)\s*=(.*)$", line)
        if not match or match[1] not in FIELDS:
            continue
        try:
            parts = shlex.split(match[2], comments=True, posix=True)
        except ValueError:
            raise ValueError("An Azure Speech field has invalid quoting.") from None
        if len(parts) > 1:
            raise ValueError("Azure Speech fields must contain one literal value.")
        values[match[1]] = parts[0] if parts else ""
    return (values.get("AZURE_SPEECH_KEY") or values.get("AZURE_API_KEY_1", ""),
            values.get("AZURE_SPEECH_REGION", ""))


def write_config(directory, key, region, *, force=False, unconfigured=False):
    """Store a protected host secret plus a non-secret Compose .env file."""
    if not unconfigured:
        if not key or len(key) > 512 or any(not 33 <= ord(c) <= 126 for c in key):
            raise ValueError("A non-empty, single-line Azure Speech key is required.")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,49}", region):
            raise ValueError("A valid Azure Speech region is required.")
    secret_dir = directory / ".secrets"
    secret = secret_dir / "azure_speech_key"
    settings = directory / ".env"
    if any(p.is_symlink() for p in (secret_dir, secret, settings)):
        raise ValueError("Refusing to write configuration through a symlink.")
    if not force and (secret.exists() or settings.exists()):
        raise ValueError("Configuration already exists; use --force to replace it.")
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    secret_dir.chmod(0o700)
    # Compose file secrets are bind mounts; uid/gid/mode remapping is not
    # portable. A 0700 parent protects the host file while 0444 lets the
    # non-root container user read the individually mounted secret.
    descriptor, temporary_name = tempfile.mkstemp(prefix=".key-", dir=secret_dir)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(key + "\n" if key else "")
        temporary.chmod(0o444)
        temporary.replace(secret)
    finally:
        temporary.unlink(missing_ok=True)
    settings.write_text(
        "# API key is mounted from .secrets/azure_speech_key.\n"
        f"AZURE_SPEECH_REGION={region}\n"
        "STUDIO_PORT=5000\nCALCULATOR_PORT=5001\n", encoding="utf-8"
    )
    settings.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-env", type=Path, help="Read only Azure Speech fields from this file")
    source.add_argument("--unconfigured", action="store_true", help="Run without credentials; speech will report unavailable")
    parser.add_argument("--force", action="store_true", help="Replace existing local configuration")
    args = parser.parse_args()
    try:
        if args.from_env:
            key, region = read_config(args.from_env)
        elif args.unconfigured:
            key, region = "", ""
        else:
            key = getpass.getpass("Azure Speech key (hidden): ").strip()
            region = input("Azure Speech region: ").strip()
        write_config(Path(__file__).resolve().parent, key, region,
                     force=args.force, unconfigured=args.unconfigured)
    except (OSError, UnicodeError):
        print("Could not read/write local configuration. Check paths and permissions.", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Local configuration prepared. No key was printed. Recreate containers after changing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
