"""Run one owned storage investigation and retain actual command evidence."""
import argparse
import json
import signal
import sys
import tarfile

from storage_tools import (
    apply_retention,
    archive_check,
    backup,
    guard,
    initialize,
    load_lab,
    name,
    observe,
    restore,
    retention_plan,
    run,
)

KIND = "retention"


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def main():
    guard()
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "observe", "backup", "change", "verify", "restore", "list", "damage", "plan", "apply"])
    parser.add_argument("--lab", required=True)
    parser.add_argument("--name", default="initial")
    parser.add_argument("--report", default="first")
    parser.add_argument("--destination", default="recovered-first")
    parser.add_argument("--text", default="version two")
    parser.add_argument("--reserve-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--mode", choices=["flip", "truncate"], default="flip")
    parser.add_argument("--keep", type=int, default=2)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.lab, KIND)
    else:
        lab = load_lab(args.lab, KIND)
        if args.command == "observe":
            result = observe(lab, args.report)
        elif args.command == "backup":
            result = backup(lab, args.name, args.reserve_bytes)
        elif args.command == "change":
            if not args.text or len(args.text) > 200 or "\x00" in args.text:
                raise ValueError("Use a nonempty change of at most 200 characters")
            (lab / "data/report.txt").write_text(args.text + "\n")
            result = {"changed": "data/report.txt", "text": args.text, "backupsUntouched": True}
        elif args.command == "verify":
            directory, manifest = archive_check(lab, args.name)
            result = {"backup": directory.name, "archiveAndInventoryExact": True, "manifest": manifest, "worksheetComplete": False}
        elif args.command == "restore":
            result = restore(lab, args.name, args.destination)
        elif args.command == "list":
            result = run(["tar", "--list", "--file", str(lab / "backups" / name(args.name) / "archive.tar")], lab)
        elif args.command == "damage":
            if KIND != "corruption":
                raise ValueError("Deliberate archive damage belongs to the separate corruption lab")
            directory, _ = archive_check(lab, args.name)
            archive = directory / "archive.tar"
            if args.mode == "flip":
                with tarfile.open(archive, "r:") as source:
                    offset = source.getmember("./report.txt").offset_data
                with archive.open("r+b") as stream:
                    stream.seek(offset)
                    byte = stream.read(1)
                    stream.seek(offset)
                    stream.write(bytes([byte[0] ^ 1]))
            else:
                with archive.open("r+b") as stream:
                    stream.truncate(100)
            result = {"deliberatelyDamaged": args.name, "mode": args.mode, "retainedManifestUnchanged": True}
        elif args.command == "plan":
            if KIND != "retention":
                raise ValueError("Retention belongs to the separate policy extension")
            result = retention_plan(lab, args.keep, args.report)
        else:
            if KIND != "retention":
                raise ValueError("Retention belongs to the separate policy extension")
            result = apply_retention(lab, args.report)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"error": "interrupted"}), file=sys.stderr)
        raise SystemExit(130)
    except (ValueError, FileExistsError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
    except (OSError, RuntimeError, KeyError, StopIteration, tarfile.TarError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
