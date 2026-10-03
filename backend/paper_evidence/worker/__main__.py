"""Explicit placeholder entry point for the future worker process."""

import sys


def main() -> int:
    print("Not Implemented：worker 功能待实现，未领取或执行任务。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
