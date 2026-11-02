#!/usr/bin/env python3
"""Check running service restrictions and scan image layers for the local key.

Only pass/fail messages are printed. Docker output and the key stay in memory.
Run from speech_docker after `docker compose up -d --wait`.
"""

import gzip
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def command(*args):
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError("A Docker verification command failed")
    return result.stdout


def check(condition, label):
    if not condition:
        raise RuntimeError(label)


def scan_image(image, key):
    # docker save includes every layer, including files removed in later layers.
    # Docker's containerd store can save gzip-compressed layer blobs inside the
    # outer tar archive. Decompress those too; scanning only the outer bytes
    # would miss credentials inside compressed layers.
    process = subprocess.Popen(["docker", "image", "save", image], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    found = False
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                with archive.extractfile(member) as raw:
                    magic = raw.peek(4)[:4]
                    check(magic != b"\x28\xb5\x2f\xfd", "Unsupported zstd layer; credential scan cannot complete")
                    stream = gzip.GzipFile(fileobj=raw) if magic[:2] == b"\x1f\x8b" else raw
                    tail = b""
                    while chunk := stream.read(1024 * 1024):
                        if key in tail + chunk:
                            found = True
                        tail = chunk[-len(key):]
                    if stream is not raw:
                        stream.close()
        check(process.wait() == 0, "Cannot export image for credential scan")
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    check(not found, "Credential found in image layers or metadata")


def run():
    key = (ROOT / ".secrets/azure_speech_key").read_bytes().strip()
    for service in ("speech-studio", "voice-calculator"):
        container = command("docker", "compose", "ps", "-q", service).decode().strip()
        check(bool(container), "Service is not running")
        raw = command("docker", "inspect", container)
        info = json.loads(raw)[0]
        check(info["Config"]["User"] == "10001:10001", "Service is running as the wrong user")
        host = info["HostConfig"]
        check(host["ReadonlyRootfs"], "Root filesystem is writable")
        check("ALL" in host["CapDrop"], "Linux capabilities are not dropped")
        check("no-new-privileges:true" in host["SecurityOpt"], "Privilege escalation is not disabled")
        ports = host["PortBindings"].get("8000/tcp", [])
        check(ports and all(p["HostIp"] == "127.0.0.1" for p in ports), "Service is exposed beyond localhost")
        secret = [m for m in info["Mounts"] if m["Destination"] == "/run/secrets/azure_speech_key"]
        check(len(secret) == 1 and not secret[0]["RW"], "Secret mount must be read-only")
        check(info["State"]["Health"]["Status"] == "healthy", "Service is unhealthy")
        if key:
            check(key not in raw, "Credential found in Docker container metadata")
            logs = command("docker", "compose", "logs", "--no-color", service)
            check(key not in logs, "Credential found in application logs")
            image = info["Config"]["Image"]
            scan_image(image, key)
            print(f"PASS: {service} credential absent from image layers, metadata and logs")
        else:
            print(f"SKIP: {service} real-key scan (unconfigured)")
        print(f"PASS: {service} non-root, read-only, localhost-only and read-only secret mount")
    ignored = command("git", "check-ignore", ".env", ".secrets/azure_speech_key").decode().splitlines()
    check(len(ignored) == 2, "Local configuration is not ignored by Git")
    # Check all local source/build inputs without reporting credential contents.
    if key:
        for path in ROOT.rglob("*"):
            if path.is_file() and ".secrets" not in path.parts:
                check(key not in path.read_bytes(), "Credential found in a non-secret project file")
    print("PASS: Git exclusions and project-file credential scan")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(f"FAIL: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}", file=sys.stderr)
        sys.exit(1)
