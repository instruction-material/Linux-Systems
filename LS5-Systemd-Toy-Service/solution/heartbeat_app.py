###########################
###   CODING STANDARD   ###
###########################
# Use named constants, descriptive names, and purpose comments before nontrivial scopes

import os
import time


def main():
    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5"))
    message = os.environ.get("HEARTBEAT_MESSAGE", "linux-heartbeat")

    while True:
        print(f"{message}: service alive", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
