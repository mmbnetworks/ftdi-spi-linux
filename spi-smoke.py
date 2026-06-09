#!/usr/bin/env python3

import argparse
import os
import sys


def parse_device(device_path: str) -> tuple[int, int]:
    base = os.path.basename(device_path)
    if not base.startswith("spidev"):
        raise ValueError(f"unsupported device path: {device_path}")

    try:
        bus_str, cs_str = base[len("spidev"):].split(".", 1)
        return int(bus_str), int(cs_str)
    except ValueError as exc:
        raise ValueError(
            f"device path must look like /dev/spidevBUS.CS, got: {device_path}"
        ) from exc


def format_ascii(data: list[int]) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a simple SPI test string through a spidev device."
    )
    parser.add_argument(
        "message",
        nargs="?",
        default="FT232H SPI smoke test 01234567890\n",
        help="ASCII string to transmit",
    )
    parser.add_argument(
        "-d",
        "--device",
        default="/dev/spidev7.0",
        help="spidev node to open, default: /dev/spidev7.0",
    )
    parser.add_argument(
        "-s",
        "--speed",
        type=int,
        default=500000,
        help="SPI clock in Hz, default: 500000",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=int,
        choices=(0, 1, 2, 3),
        default=0,
        help="SPI mode, default: 0",
    )
    parser.add_argument(
        "--bpw",
        type=int,
        default=8,
        help="bits per word, default: 8",
    )
    parser.add_argument(
        "--lsb-first",
        action="store_true",
        help="use LSB-first transfer order",
    )
    args = parser.parse_args()

    try:
        import spidev
    except ImportError:
        print("python3-spidev is required: pip install spidev", file=sys.stderr)
        return 2

    try:
        bus, chip_select = parse_device(args.device)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    tx_data = list(args.message.encode("utf-8"))
    tx_payload = tx_data.copy()

    spi = spidev.SpiDev()
    try:
        spi.open(bus, chip_select)
        spi.max_speed_hz = args.speed
        spi.mode = args.mode
        spi.bits_per_word = args.bpw
        spi.lsbfirst = args.lsb_first
        rx_data = spi.xfer2(tx_data)
    finally:
        spi.close()

    print(f"device: {args.device}")
    print(f"mode: {args.mode}")
    print(f"speed_hz: {args.speed}")
    print(f"bits_per_word: {args.bpw}")
    print(f"lsb_first: {args.lsb_first}")
    print(f"tx_hex: {' '.join(f'{byte:02x}' for byte in tx_payload)}")
    print(f"rx_hex: {' '.join(f'{byte:02x}' for byte in rx_data)}")
    print(f"tx_ascii: {format_ascii(tx_payload)}")
    print(f"rx_ascii: {format_ascii(rx_data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())