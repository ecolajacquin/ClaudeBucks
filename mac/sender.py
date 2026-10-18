"""Pico USB transport, with a standalone dummy-data test."""
import argparse
import json
import time

import serial
import serial.tools.list_ports


def find_pico():
    ports = [p for p in serial.tools.list_ports.comports() if p.vid == 0x2E8A]
    if not ports:
        raise RuntimeError('Pico not found; is USB connected?')
    if len(ports) != 1:
        raise RuntimeError('Multiple Pico serial ports detected; pass --port')
    return ports[0].device


class PicoSender:
    def __init__(self, port: str | None = None):
        self.port = port
        self.serial: serial.Serial | None = None

    def __enter__(self):
        self.serial = serial.Serial(
            self.port or find_pico(),
            baudrate=115200,
            timeout=1,
            write_timeout=2,
        )
        time.sleep(2)
        return self

    def close(self):
        """Release the serial port safely."""
        connection = self.serial
        self.serial = None

        if connection is not None:
            try:
                if connection.is_open:
                    connection.close()
            except (OSError, serial.SerialException):
                pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def send(
        self,
        used: float,
        budget: float,
        status: str = "ok",
    ):
        if self.serial is None or not self.serial.is_open:
            raise RuntimeError("Serial port is not connected")

        payload = {
            "used": used,
            "budget": budget,
            "status": status,
        }

        message = json.dumps(payload) + "\n"
        self.serial.write(message.encode("utf-8"))
        self.serial.flush()


def main():
    parser = argparse.ArgumentParser(description='Test Pico sender with dummy values')
    parser.add_argument('--budget', type=float, default=1000.0,
                        help='Dummy test value; not the production budget')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--port')
    args = parser.parse_args()
    if args.budget <= 0 or args.interval <= 0:
        parser.error('Budget and interval must be positive')
    with PicoSender(args.port) as pico:
        for percent in range(0, 101, 10):
            pico.send(args.budget * percent / 100, args.budget)
            print(f'Sent {percent}%')
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
