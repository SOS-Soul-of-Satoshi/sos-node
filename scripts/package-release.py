#!/usr/bin/env python3
"""Verify CI payloads and create deterministic public node archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path


PLATFORMS = {
    "linux-x64": {
        "binary": "sos-node",
        "required": {
            "sos-node",
            "genesis.json",
            "BUILDINFO.txt",
            "DYNAMIC_DEPENDENCIES.txt",
            "SHA256SUMS",
        },
        "archive": "tar.gz",
    },
    "windows-x64": {
        "binary": "sos-node.exe",
        "required": {
            "sos-node.exe",
            "genesis.json",
            "BUILDINFO.txt",
            "SHA256SUMS",
        },
        "archive": "zip",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_buildinfo(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = raw.partition("=")
        if not separator or not key or key in values:
            raise ValueError(f"invalid BUILDINFO line: {raw!r}")
        values[key] = value
    return values


def verify_ci_manifest(payload: Path) -> None:
    seen: set[str] = set()
    for raw in (payload / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^/\\]+)", raw)
        if match is None:
            raise ValueError(f"invalid SHA256SUMS line: {raw!r}")
        expected, name = match.groups()
        if name in seen:
            raise ValueError(f"duplicate SHA256SUMS entry: {name}")
        seen.add(name)
        target = payload / name
        if not target.is_file() or sha256(target) != expected.lower():
            raise ValueError(f"CI payload hash mismatch: {name}")
    if not seen:
        raise ValueError("empty CI SHA256SUMS")


def write_sbom(
    root: Path,
    files: list[Path],
    binary_name: str,
    release_version: str,
    platform: str,
    buildinfo: dict[str, str],
) -> None:
    components = []
    for path in files:
        components.append(
            {
                "bom-ref": f"file:{path.name}",
                "type": "file",
                "name": path.name,
                "hashes": [{"alg": "SHA-256", "content": sha256(path)}],
            }
        )
    binary_hash = sha256(root / binary_name)
    serial_seed = f"{release_version}|{platform}|{buildinfo['sourceCommit']}"
    bom = {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, serial_seed)}",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": f"pkg:generic/sos-node@{release_version}?platform={platform}",
                "type": "application",
                "name": "sos-node",
                "version": release_version,
                "hashes": [{"alg": "SHA-256", "content": binary_hash}],
                "properties": [
                    {"name": "sos:sourceCommit", "value": buildinfo["sourceCommit"]},
                    {"name": "sos:platform", "value": platform},
                    {"name": "sos:profile", "value": buildinfo["profile"]},
                    {
                        "name": "sos:genesisSha256",
                        "value": buildinfo["genesisSha256"],
                    },
                ],
            }
        },
        "components": components,
    }
    (root / "SBOM.cdx.json").write_text(
        json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_release_manifest(root: Path) -> None:
    files = sorted(
        path for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    content = "".join(f"{sha256(path)}  {path.name}\n" for path in files)
    (root / "SHA256SUMS").write_text(content, encoding="ascii")


def create_tar_gz(root: Path, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                directory = tarfile.TarInfo(root.name)
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                directory.mtime = 0
                archive.addfile(directory)
                for path in sorted(root.iterdir()):
                    info = tarfile.TarInfo(f"{root.name}/{path.name}")
                    info.size = path.stat().st_size
                    info.mode = 0o755 if path.name == "sos-node" else 0o644
                    info.mtime = 0
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)


def create_zip(root: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(root.iterdir()):
            info = zipfile.ZipInfo(f"{root.name}/{path.name}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name.endswith(".exe") else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def package(
    payload: Path,
    output_dir: Path,
    platform: str,
    release_version: str,
    source_commit: str,
) -> dict[str, str]:
    config = PLATFORMS[platform]
    actual = {path.name for path in payload.iterdir() if path.is_file()}
    if actual != config["required"]:
        raise ValueError(
            f"unexpected payload files for {platform}: "
            f"missing={sorted(config['required'] - actual)}, "
            f"extra={sorted(actual - config['required'])}"
        )
    verify_ci_manifest(payload)
    buildinfo = parse_buildinfo(payload / "BUILDINFO.txt")
    if buildinfo.get("sourceCommit") != source_commit:
        raise ValueError("BUILDINFO source commit does not match the requested release")
    if buildinfo.get("version") != "sos-node 0.2.0":
        raise ValueError(f"unexpected binary version: {buildinfo.get('version')!r}")
    genesis_hash = sha256(payload / "genesis.json")
    if buildinfo.get("genesisSha256") != genesis_hash:
        raise ValueError("BUILDINFO genesis hash does not match genesis.json")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"sos-node-{release_version}-{platform}"
    with tempfile.TemporaryDirectory(prefix="sos-node-release-") as temporary:
        root = Path(temporary) / stem
        root.mkdir()
        for name in sorted(config["required"] - {"SHA256SUMS"}):
            shutil.copy2(payload / name, root / name)
        initial_files = sorted(path for path in root.iterdir() if path.is_file())
        write_sbom(
            root,
            initial_files,
            config["binary"],
            release_version,
            platform,
            buildinfo,
        )
        write_release_manifest(root)
        extension = config["archive"]
        archive = output_dir / f"{stem}.{extension}"
        if extension == "tar.gz":
            create_tar_gz(root, archive)
        else:
            create_zip(root, archive)

    archive_hash = sha256(archive)
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{archive_hash}  {archive.name}\n", encoding="ascii")
    return {
        "platform": platform,
        "binarySha256": sha256(payload / config["binary"]),
        "archive": archive.name,
        "archiveSha256": archive_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        parser.error("--source-commit must be a lowercase 40-character Git hash")
    result = package(
        args.payload.resolve(),
        args.output.resolve(),
        args.platform,
        args.version,
        args.source_commit,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
