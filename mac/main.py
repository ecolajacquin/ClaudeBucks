
import argparse
import signal
import time

import serial

from collector import collect
from sender import PicoSender


# Configuration
DEFAULT_HEARTBEAT_INTERVAL = 5.0
DEFAULT_COLLECT_INTERVAL = 120.0
RECONNECT_INTERVAL = 5.0


def handle_shutdown(signum, frame):
    """Convert SIGTERM into a graceful shutdown."""
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(
        description="Claude Bucks background monitor"
    )

    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Override Claude Code's monthly allocation",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_HEARTBEAT_INTERVAL,
        help="USB heartbeat interval in seconds (default: 5)",
    )

    parser.add_argument(
        "--collect-interval",
        type=float,
        default=DEFAULT_COLLECT_INTERVAL,
        help="Usage collection interval in seconds (default: 120)",
    )

    parser.add_argument(
        "--port",
        default=None,
        help="Optional explicit Pico serial port",
    )

    args = parser.parse_args()

    if args.budget is not None and args.budget <= 0:
        parser.error("--budget must be positive")

    if args.interval <= 0:
        parser.error("--interval must be positive")

    if args.collect_interval <= 0:
        parser.error("--collect-interval must be positive")

    # Allow launchd to stop the process gracefully.
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("Claude Bucks starting...", flush=True)

    last_usage = None
    last_status = "error"
    last_collection = 0.0

    try:
        while True:
            try:
                # Context manager guarantees port cleanup.
                with PicoSender(port=args.port) as pico:
                    print("Pico connected", flush=True)

                    while True:
                        now = time.monotonic()

                        # Collect usage independently of USB heartbeats.
                        if (
                            last_usage is None
                            or now - last_collection
                            >= args.collect_interval
                        ):
                            last_collection = now

                            try:
                                last_usage = collect(
                                    budget=args.budget
                                )

                                last_status = (
                                    "stale"
                                    if last_usage.stale
                                    else "ok"
                                )

                            except RuntimeError as exc:
                                print(
                                    f"Collector error: {exc}",
                                    flush=True,
                                )
                                last_status = "error"

                        # Only send real, previously collected values.
                        if last_usage is not None:
                            pico.send(
                                used=last_usage.used,
                                budget=last_usage.budget,
                                status=last_status,
                            )

                            print(
                                f"Used: ₡{last_usage.used:.2f} | "
                                f"Left: ₡{last_usage.remaining:.2f} | "
                                f"{last_usage.percentage:.1f}% | "
                                f"Status: {last_status}",
                                flush=True,
                            )

                        time.sleep(args.interval)

            except (
                OSError,
                serial.SerialException,
                RuntimeError,
            ) as exc:
                print(
                    f"Pico unavailable: {exc}. "
                    f"Retrying in {RECONNECT_INTERVAL:.0f}s",
                    flush=True,
                )
                time.sleep(RECONNECT_INTERVAL)

    except KeyboardInterrupt:
        print(
            "\nStopping Claude Bucks gracefully...",
            flush=True,
        )

    finally:
        # The PicoSender context manager has already closed
        # the port before execution reaches this block.
        print(
            "Claude Bucks stopped. Serial port released.",
            flush=True,
        )


if __name__ == "__main__":
    main()
