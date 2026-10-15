"""Verify actual owner access and creation masks under an ordinary Linux UID."""
import argparse
import errno
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACKS = [
    "LS-07-unit-3-users-groups-and-permissions-supplemental-2",
    "LS-08-unit-3-users-groups-and-permissions-supplemental-3",
]
REPAIRS = [
    (
        "permission_observer.py",
        "return bool(file_mode & 0o200) # TODO: use owner write and search on the containing directory.",
        "return directory_mode & 0o300 == 0o300",
    ),
    (
        "creation_observer.py",
        "return 0o777 & ~mask # TODO: use the requested regular-file creation mode.",
        "return 0o666 & ~mask",
    ),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hashes(root):
    return {
        str(file.relative_to(root)): sha(file.read_bytes())
        for pack in PACKS
        for file in sorted((root / pack).rglob("*"))
        if file.is_file()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", required=True, type=Path)
    args = parser.parse_args()
    assert sys.platform == "linux" and os.getuid() > 0
    root = Path(__file__).resolve().parents[1]
    before = hashes(root)
    assert len(before) == 14
    args.proof = args.proof.resolve()
    args.proof.parent.mkdir(parents=True, exist_ok=True)
    ledger = args.proof.with_suffix(".processes.jsonl")
    observations = []
    profiles = []

    def event(entry):
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")

    def run(case, command, cwd):
        child = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        record = {
            "parentTaskId": "linux-permissions-source", "parentPid": os.getpid(),
            "pid": child.pid, "cwd": str(cwd), "command": command,
            "startTime": time.time(), "timeoutSeconds": 15,
        }
        event(dict(record, event="start"))
        cleanup = "owned process exited and reaped"
        try:
            stdout, stderr = child.communicate(timeout=15)
        except BaseException:
            cleanup = "owned process group terminated after timeout or interruption"
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate()
            raise
        finally:
            event(dict(record, event="end", endTime=time.time(), exitCode=child.returncode,
                       childProcessGroupCleanup=cleanup))
        row = {
            "case": case, "command": command, "cwd": str(cwd),
            "status": child.returncode, "stdout": stdout.decode(), "stderr": stderr.decode(),
        }
        observations.append(row)
        args.proof.with_suffix(".observations.json").write_text(
            json.dumps(observations, indent=2) + "\n", encoding="utf-8"
        )
        return row

    def rejected(row):
        assert row["status"] == 2 and not row["stdout"] and row["stderr"]

    with tempfile.TemporaryDirectory(prefix="linux-permissions-optional-") as directory:
        work = Path(directory)
        sentinel = work / "outside-sentinel.txt"
        sentinel.write_bytes(b"unchanged outside generated permission cases\n")
        outside_hash = sha(sentinel.read_bytes())
        for index, pack in enumerate(PACKS):
            helper, old, new = REPAIRS[index]
            for role in ["starter", "solution", "completed"]:
                initial = len(observations)
                profile = work / (str(index) + "-" + role)
                source_role = "starter" if role == "completed" else role
                shutil.copytree(root / pack / source_role, profile)
                if role == "completed":
                    source = (profile / helper).read_text()
                    assert source.count(old) == 1
                    (profile / helper).write_text(source.replace(old, new))
                parent = work / ("workspace " + str(index) + "-" + role)
                parent.mkdir(mode=0o700)
                script = str(profile / "task.sh")

                def inspect(parent_path, mask=None, case="owned observations", cwd=profile, inherited=None, index=index, role=role, script=script):
                    command = ["bash", script, str(parent_path)]
                    if index == 1:
                        command.append(mask or "0022")
                    if inherited is not None:
                        command = ["bash", "-c", 'umask "$1"; shift; exec "$@"', "mask-parent", inherited, *command]
                    row = run(case, command, cwd)
                    assert not row["stderr"]
                    result = json.loads(row["stdout"])
                    assert result["uid"] == os.getuid() and result["workspace"] == str(parent_path.resolve())
                    assert result["observationsCompleted"] and result["temporaryCasesRemoved"]
                    assert result["learnerWorksheetCompletionInferred"] is False
                    assert not list(parent_path.iterdir())
                    if index == 0:
                        a, b, c = result["observations"]
                        for item, modes, outcomes in [
                            (a, ("0700", "0400"), (False, True, True)),
                            (b, ("0500", "0600"), (True, True, False)),
                            (c, ("0300", "0400"), (False, False, True)),
                        ]:
                            assert (item["directoryMode"], item["fileMode"]) == modes
                            assert tuple(item[x]["succeeded"] for x in ["writeAttempt", "listAttempt", "unlinkAttempt"]) == outcomes
                            for action, succeeded in zip(["writeAttempt", "listAttempt", "unlinkAttempt"], outcomes):
                                assert item[action]["errno"] == (None if succeeded else errno.EACCES)
                            assert item["nameExistsAfterUnlink"] == (not outcomes[2])
                            assert item["beforeSha256"] == sha(b"owned example\n")
                            assert item["afterWriteSha256"] == sha(b"owned example\n" + (b"probe\n" if outcomes[0] else b""))
                            expected_prediction = bool(int(modes[1], 8) & 0o200) if role == "starter" else outcomes[2]
                            assert item["predictedCanUnlink"] == expected_prediction
                            if outcomes[1]:
                                assert item["listAttempt"]["value"] == ["document.txt"]
                        assert result["allPredictionsMatch"] == (role != "starter")
                        assert row["status"] == (1 if role == "starter" else 0)
                    else:
                        item = result["observation"]
                        mask_value = int(mask or "0022", 8)
                        assert item["mask"] == format(mask_value, "04o")
                        assert item["requestedFileMode"] == "0666" and item["requestedDirectoryMode"] == "0777"
                        assert item["actualFileMode"] == format(0o666 & ~mask_value, "04o")
                        assert item["actualDirectoryMode"] == format(0o777 & ~mask_value, "04o")
                        assert item["predictedFileMode"] == format((0o777 if role == "starter" else 0o666) & ~mask_value, "04o")
                        assert not item["fileHasExecutableBits"]
                        assert item["existingModeBefore"] == item["existingModeAfter"] == "0640"
                        assert item["existingBytesUnchanged"] and item["existingSha256"] == sha(b"existing data\n")
                        assert item["inheritedUmask"] == item["restoredUmask"]
                        if inherited is not None:
                            assert item["inheritedUmask"] == inherited
                        matched = item["predictedFileMode"] == item["actualFileMode"]
                        assert item["allPredictionsMatch"] == matched
                        assert row["status"] == (0 if matched else 1)

                if index == 0:
                    inspect(parent)
                    inspect(parent, case="repeat with restrictive inherited mask", inherited="0777")
                else:
                    for mask in ["0022", "0077", "0002", "0000", "0777", "0137"]:
                        inspect(parent, mask, "actual creation mask " + mask)
                    inspect(parent, "0002", "restore inherited process mask", inherited="0777")
                    for invalid in ["0088", "-1", "1000", "oops", "22", "00000", ""]:
                        rejected(run("invalid octal mask", ["bash", script, str(parent), invalid], profile))
                for name in ["with space", "trailing newline\n"]:
                    other = work / ("quoted " + str(index) + " " + role + " " + name)
                    other.mkdir(mode=0o700)
                    inspect(other, case="quoted workspace and caller directory", cwd=work)
                marker = parent / "keep.txt"
                marker.write_bytes(b"keep original workspace entry\n")
                before_marker = sha(marker.read_bytes())
                rejected(run("nonempty workspace retained", ["bash", script, str(parent)] + (["0022"] if index else []), profile))
                assert sha(marker.read_bytes()) == before_marker
                marker.unlink()
                for name, target in [
                    ("missing workspace", work / "missing"),
                    ("regular file workspace", sentinel),
                ]:
                    rejected(run(name, ["bash", script, str(target)] + (["0022"] if index else []), profile))
                link = work / ("link-" + str(index) + "-" + role)
                link.symlink_to(parent, target_is_directory=True)
                rejected(run("symlink workspace rejected", ["bash", script, str(link)] + (["0022"] if index else []), profile))
                assert link.is_symlink() and not list(parent.iterdir())
                parent.chmod(0o500)
                try:
                    row = run("actual workspace creation denial", ["bash", script, str(parent)] + (["0022"] if index else []), profile)
                    rejected(row)
                    assert "Permission denied" in row["stderr"]
                finally:
                    parent.chmod(0o700)
                for args_list in [[], [str(parent)] + (["0022"] if index else []) + ["extra"]]:
                    rejected(run("invalid argument count", ["bash", script, *args_list], profile))
                assert not list(parent.iterdir()) and sha(sentinel.read_bytes()) == outside_hash
                profiles.append({"pack": pack, "profile": role, "actualCases": len(observations)-initial,
                                     "outsideSentinelPreserved": True, "workspaceEntriesAndModeRestored": True,
                                     "starterIntentionallyIncomplete": role == "starter", "passed": True})
        assert len(profiles) == 6 and len(observations) == 102
        assert sorted(x["actualCases"] for x in profiles) == [11, 11, 11, 23, 23, 23]
        assert hashes(root) == before
        proof = {"nativePassed": True, "sourceHashes": before, "profiles": profiles,
                     "actualCases": len(observations), "unprivilegedUid": os.getuid(),
                     "sourceUnchanged": True, "temporaryCasesRemoved": True,
                     "actualAccessProbes": 108, "actualCreationExperiments": 27}
    assert not work.exists()
    args.proof.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in proof.items() if key != "sourceHashes"}))


if __name__ == "__main__":
    main()
