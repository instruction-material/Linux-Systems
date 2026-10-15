"""The named policy; studio_observer supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def artifact_is_current(state, artifact, expected_sha256):
    # TODO: verify the current output, not only the process result.
    return state.get('Result') == 'success' and state.get('ExecMainStatus') == '0'


if __name__ == '__main__':
    from studio_observer import main
    raise SystemExit(main(artifact_is_current, 'output'))
