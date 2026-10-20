"""Reserve immutable versions and verify retry-safe PyPI uploads (CI only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dmarket-client"
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")


def version_tuple(value: str) -> tuple[int, int, int]:
    if not VERSION.fullmatch(value):
        raise ValueError(f"Expected a stable major.minor.patch version, got {value!r}")
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def select_version(tags: dict[str, str], sha: str, initial: str) -> str:
    """Reuse a reserved version on reruns; otherwise advance the stable patch."""
    floor = version_tuple(initial)
    stable = {
        name[1:]: target
        for name, target in tags.items()
        if name.startswith("v") and VERSION.fullmatch(name[1:])
    }
    matching = [version for version, target in stable.items() if target == sha]
    if len(matching) > 1:
        raise ValueError("Multiple release tags point to this commit; resolve ambiguity first")
    if matching:
        return matching[0]
    latest = max((version_tuple(version) for version in stable), default=None)
    candidate = floor if latest is None else max(floor, (latest[0], latest[1], latest[2] + 1))
    return ".".join(map(str, candidate))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def request_json(url: str, *, token: str | None = None, data: dict[str, str] | None = None) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "dmarket-client-release"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=None if data is None else json.dumps(data).encode(), headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def output(name: str, value: str) -> None:
    print(f"{name}={value}")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")


def prepare(*, dry_run: bool = False) -> None:
    sha = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Release requires a clean tracked working tree")
    tags = {
        name: git("rev-list", "-n", "1", name) for name in git("tag", "--list", "v*").splitlines()
    }
    initial = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["dmarket-release"][
        "initial-version"
    ]
    version = select_version(tags, sha, initial)
    tag = f"v{version}"
    if not dry_run:
        if (
            os.environ.get("GITHUB_REF") != "refs/heads/master"
            or os.environ.get("GITHUB_SHA") != sha
        ):
            raise ValueError("Only the tested master revision may reserve a release")
        repository = os.environ["GITHUB_REPOSITORY"]
        if repository != "ykirshov/dmarket-client":
            raise ValueError("Unexpected publishing repository")
        token = os.environ["GH_TOKEN"]
        api = f"https://api.github.com/repos/{repository}/git"
        try:
            request_json(f"{api}/refs", token=token, data={"ref": f"refs/tags/{tag}", "sha": sha})
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422):
                raise
            remote = request_json(f"{api}/ref/tags/{tag}", token=token)
            if remote["object"]["type"] != "commit" or remote["object"]["sha"] != sha:
                raise ValueError(f"Refusing to move existing remote tag {tag}") from error
        if tag not in tags:
            git("tag", tag, sha)
    output("version", version)
    output("tag", tag)


def distribution_hashes(directory: Path, version: str) -> dict[str, str]:
    version_tuple(version)
    files = sorted(path for path in directory.iterdir() if path.name != ".gitignore")
    wheels = [path for path in files if path.suffix == ".whl"]
    sources = [path for path in files if path.name.endswith(".tar.gz")]
    if len(files) != 2 or len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("Wheel metadata is ambiguous")
        wheel_metadata = archive.read(names[0])
    with tarfile.open(sources[0], "r:gz") as archive:
        names = [
            member
            for member in archive.getmembers()
            if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        if len(names) != 1:
            raise ValueError("Source distribution metadata is ambiguous")
        stream = archive.extractfile(names[0])
        if stream is None:
            raise ValueError("Missing source distribution metadata")
        source_metadata = stream.read()
    for metadata in (wheel_metadata, source_metadata):
        parsed = BytesParser().parsebytes(metadata)
        if parsed["Name"] != PACKAGE or parsed["Version"] != version:
            raise ValueError("Distribution name/version does not match the reserved release")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def needs_publication(local: dict[str, str], remote_files: list[dict]) -> bool:
    """Fail on collisions; allow recovery of matching partial uploads."""
    remote = {item["filename"]: item["digests"]["sha256"] for item in remote_files}
    if remote.keys() - local.keys():
        raise ValueError("Existing PyPI version contains unexpected files")
    for name, digest in remote.items():
        if local[name] != digest:
            raise ValueError(f"Existing PyPI artifact differs: {name}; never overwrite a release")
    return remote.keys() != local.keys()


def verify(version: str, directory: Path) -> None:
    local = distribution_hashes(directory, version)
    try:
        remote = request_json(f"https://pypi.org/pypi/{PACKAGE}/{version}/json")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        remote = {"urls": []}
    output("publish-needed", str(needs_publication(local, remote["urls"])).lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--dry-run", action="store_true")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--version", required=True)
    verify_parser.add_argument("--directory", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(dry_run=args.dry_run)
    else:
        verify(args.version, args.directory)


if __name__ == "__main__":
    main()
