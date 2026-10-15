#!/usr/bin/env python3
"""Observe actual dpkg dependency state in a separate owned installation root."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from owned_lab import checked, directory, init_lab, lab, new_file, prerequisites, regular, run, sha

KIND = "dependency-layout-v1"
APP = "linux-layout-app"
BASE = "linux-layout-base"
PROGRAM = '''#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[2]
try:
    version = (root / "usr/share/linux-layout-lab/base-version.txt").read_text().strip()
except OSError:
    print("runtime dependency file is missing", file=sys.stderr)
    sys.exit(1)
if version != "2.0":
    print("runtime needs base 2.0; observed " + version, file=sys.stderr)
    sys.exit(2)
print("dependency-demo ready base=" + version)
'''


def manager(root, *arguments):
    return ["dpkg", "--root=" + str(root / "root"), "--force-not-root", "--no-triggers",
            "--log=" + str(root / "dpkg.log"), *arguments]


def package(root, name, version):
    tree = root / "builds" / (name + "-" + version)
    tree.mkdir(mode=0o700)
    (tree / "DEBIAN").mkdir()
    control = (f"Package: {name}\nVersion: {version}\nArchitecture: all\n"
               "Maintainer: Linux Systems Lab <lab@example.invalid>\n"
               "Section: education\nPriority: optional\n"
               "Description: owned local dependency observation package\n")
    if name == APP:
        control += "Depends: linux-layout-base (>= 2.0)\n"
        target = tree / "usr/bin/linux-layout-demo.py"
        content = PROGRAM
    else:
        target = tree / "usr/share/linux-layout-lab/base-version.txt"
        content = version + "\n"
    new_file(tree / "DEBIAN/control", control, 0o644)
    target.parent.mkdir(parents=True)
    new_file(target, content, 0o755 if name == APP else 0o644)
    # Keep this owned lab's UID/GID in the locally built archive. No maintainer
    # scripts, triggers or root-owned payloads are included.
    checked(root, ["dpkg-deb", "--build", str(tree), str(root / "packages" / (name + "-" + version + ".deb"))])


def action(args):
    prerequisites()
    if not all(shutil.which(name) for name in ["dpkg", "dpkg-deb", "dpkg-query"]):
        raise ValueError("this lab requires the Debian dpkg tools")
    if args.action == "init":
        root = init_lab(args.lab, KIND)
        for name in ["builds", "packages", "root"]:
            (root / name).mkdir(mode=0o700)
        database = root / "root/var/lib/dpkg"
        for name in ["info", "updates", "triggers", "parts"]:
            (database / name).mkdir(parents=True, exist_ok=True)
        for name in ["status", "available"]:
            new_file(database / name, b"")
        return 0
    root = lab(args.lab, KIND)
    for name in ["builds", "packages", "root", "root/var/lib/dpkg"]:
        directory(root / name)
    for entry in (root / "root").rglob("*"):
        if entry.is_symlink():
            raise ValueError("the disposable installation root must not contain symbolic links")
        (directory if entry.is_dir() else regular)(entry)
    if args.action == "build":
        for name, version in [(BASE, "1.0"), (BASE, "2.0"), (APP, "1.0")]:
            package(root, name, version)
        manifest = {file.name: sha(file) for file in sorted((root / "packages").glob("*.deb"))}
        if len(manifest) != 3:
            raise ValueError("unexpected package set")
        new_file(root / "packages/manifest.json", json.dumps(manifest, indent=2) + "\n")
        print("BUILT=base 1.0, base 2.0, app 1.0 requiring base >= 2.0")
        return 0
    if args.action in ("install-app", "install-base"):
        name, version = (APP, "1.0") if args.action == "install-app" else (BASE, args.version)
        archive = regular(root / "packages" / (name + "-" + version + ".deb"))
        manifest = json.loads(regular(root / "packages/manifest.json").read_text())
        if manifest.get(archive.name) != sha(archive):
            raise ValueError("package archive changed after its recorded build")
        argv = manager(root, "--install", str(archive))
    elif args.action == "configure-app":
        argv = manager(root, "--configure", APP)
    elif args.action == "remove-app":
        argv = manager(root, "--remove", APP)
    elif args.action == "remove-base":
        argv = manager(root, "--remove", BASE)
    elif args.action == "audit":
        argv = manager(root, "--audit")
    elif args.action == "query":
        argv = ["dpkg-query", "--admindir=" + str(root / "root/var/lib/dpkg"),
                "--show", "--showformat=${binary:Package}\\t${Version}\\t${Status}\\n", APP, BASE]
    else:
        program = regular(root / "root/usr/bin/linux-layout-demo.py")
        argv = [sys.executable, str(program)]
    status, stdout, stderr = run(root, argv)
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "build", "install-app", "install-base", "configure-app",
                                          "remove-app", "remove-base", "audit", "query", "run"])
    parser.add_argument("--lab", required=True, type=Path)
    parser.add_argument("--version", choices=["1.0", "2.0"], default="1.0")
    try:
        return action(parser.parse_args())
    except (OSError, ValueError, RuntimeError) as error:
        print("Dependency lab failed: " + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
