"""The named policy; studio_observer supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def artifact_is_current(state, artifact, expected_sha256):
    import hashlib
    if state.get('Result') != 'success' or state.get('ExecMainStatus') != '0':
        return False
    return (not artifact.is_symlink() and artifact.is_file()
            and hashlib.sha256(artifact.read_bytes()).hexdigest() == expected_sha256)


if __name__ == '__main__':
    from studio_observer import main
    raise SystemExit(main(artifact_is_current, 'output'))
