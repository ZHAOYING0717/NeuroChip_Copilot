from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neurochip.standard import convert_axion_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert vendor event exports to the NeuroChip standard table")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--format", choices=("auto", "axion"), default="auto")
    parser.add_argument("--well", help="Optional Axion well identifier such as A5")
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    metadata = convert_axion_csv(
        args.input,
        args.output,
        well=args.well,
        chunksize=args.chunksize,
        resume=args.resume,
    )
    print(json.dumps(metadata, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
