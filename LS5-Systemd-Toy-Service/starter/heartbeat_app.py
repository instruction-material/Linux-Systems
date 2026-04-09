import os
import time


def main():
	interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5"))

	while True:
		print("heartbeat")
		time.sleep(interval)


if __name__ == "__main__":
	main()
