#!/usr/bin/env python3
"""Build, archive and inspect two manually installed owned releases."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from owned_lab import checked, directory, init_lab, lab, new_file, prerequisites, regular, run, sha

KIND = "manual-layout-v1"
MEMBERS = {"bin/layout-demo", "share/layout-demo/manifest.json"}


def installed(root, version):
    release = directory(directory(root / "releases") / version)
    directory(release / "bin")
    directory(directory(release / "share") / "layout-demo")
    names = {str(p.relative_to(release)) for p in release.rglob("*") if not p.is_dir()}
    if names != MEMBERS:
        raise ValueError("release has unexpected or missing files")
    manifest = json.loads(regular(release / "share/layout-demo/manifest.json").read_text())
    if manifest != dict(version=version, binarySha256=sha(release / "bin/layout-demo")):
        raise ValueError("installed bytes differ from their recorded manifest")
    return release


def active(root):
    link = root / "current"
    if not link.is_symlink() or os.readlink(link) not in ("releases/1.0", "releases/2.0"):
        raise ValueError("current is not a recognized owned release link")
    version = os.readlink(link).split("/")[1]
    return version, installed(root, version)


def action(args):
    prerequisites()
    if args.action == "init":
        root = init_lab(args.lab, KIND)
        for name in ("builds", "archives", "releases"):
            (root / name).mkdir(mode=0o700)
        return 0
    root = lab(args.lab, KIND)
    version = args.version
    for name in ("builds", "archives", "releases"):
        directory(root / name)
    if args.action == "build":
        if not shutil.which("cc"):
            raise ValueError("the lab needs a C compiler (cc)")
        build = root / "builds" / version
        build.mkdir(mode=0o700)
        source = regular(Path(__file__).resolve().parent / "layout_demo.c")
        checked(root, ["cc", "-std=c17", "-Wall", "-Wextra", "-Werror",
                       '-DAPP_VERSION="' + version + '"', str(source), "-o", str(build / "layout-demo")])
        print("BUILT=" + version)
    elif args.action == "archive":
        build = directory(root / "builds" / version)
        binary = regular(build / "layout-demo")
        manifest = (json.dumps(dict(version=version, binarySha256=sha(binary))) + "\n").encode()
        archive = root / "archives" / (version + ".tar.gz")
        with tarfile.open(archive, "x:gz") as stream:
            for name, content, mode in [("bin/layout-demo", binary.read_bytes(), 0o755),
                                        ("share/layout-demo/manifest.json", manifest, 0o600)]:
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(content), mode
                stream.addfile(info, io.BytesIO(content))
        new_file(root / "archives" / (version + ".sha256"), sha(archive) + "\n")
        print("ARCHIVED=" + str(archive))
    elif args.action == "install":
        archive = root / "archives" / (version + ".tar.gz")
        expected = regular(root / "archives" / (version + ".sha256")).read_text().strip()
        if sha(archive) != expected:
            raise ValueError("archive changed after its recorded build")
        destination = root / "releases" / version
        if destination.exists() or destination.is_symlink():
            raise ValueError("release already exists; preserve it and use another experiment")
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=root / "releases"))
        try:
            with tarfile.open(archive) as stream:
                members = stream.getmembers()
                if len(members) != 2 or {x.name for x in members} != MEMBERS or not all(x.isfile() for x in members):
                    raise ValueError("unexpected archive entries")
                for member in members:
                    path = stage / member.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(member) as content:
                        new_file(path, content.read(), 0o755 if member.name == "bin/layout-demo" else 0o600)
            manifest = json.loads((stage / "share/layout-demo/manifest.json").read_text())
            if manifest != dict(version=version, binarySha256=sha(stage / "bin/layout-demo")):
                raise ValueError("archive manifest does not match its binary")
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        print("INSTALLED=" + str(destination))
    elif args.action == "activate":
        installed(root, version)
        current = root / "current"
        if current.exists() or current.is_symlink():
            active(root)
        temporary = root / ".new-current"
        temporary.symlink_to("releases/" + version)
        try:
            os.replace(temporary, current)
        finally:
            temporary.unlink(missing_ok=True)
        print("ACTIVE=" + version)
    elif args.action == "check":
        current_version, release = active(root)
        binary = release / "bin/layout-demo"
        output = checked(root, [str(binary), "--version"]).decode()
        if output != current_version + "\n":
            raise ValueError("runtime version differs from the active release")
        owner_status, owner_stdout, owner_stderr = run(root, ["dpkg-query", "--search", str(binary)])
        if owner_status not in (0, 1):
            raise RuntimeError("ownership query failed: " + owner_stderr.decode())
        print(json.dumps(dict(version=current_version, binary=str(binary), binarySha256=sha(binary),
                              ownershipStatus=owner_status, ownershipOutput=owner_stdout.decode().strip(),
                              packageManaged=owner_status == 0, manualReceiptIsAuthenticityProof=False,
                              learnerWorksheetCompletionInferred=False)))
    elif args.action == "remove":
        release = installed(root, version)
        current = root / "current"
        if current.exists() or current.is_symlink():
            current_version, _ = active(root)
            if current_version == version:
                current.unlink()
        (release / "bin/layout-demo").unlink()
        (release / "share/layout-demo/manifest.json").unlink()
        (release / "bin").rmdir()
        (release / "share/layout-demo").rmdir()
        (release / "share").rmdir()
        release.rmdir()
        print("REMOVED=" + version + "; archives, evidence and other releases retained")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "build", "archive", "install", "activate", "check", "remove"])
    parser.add_argument("--lab", required=True, type=Path)
    parser.add_argument("--version", choices=["1.0", "2.0"], default="1.0")
    try:
        return action(parser.parse_args())
    except (OSError, ValueError, RuntimeError, tarfile.TarError) as error:
        print("Manual lab failed: " + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
