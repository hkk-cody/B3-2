"""Run from the root of the Git repository being summarized."""

import sys


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        print("[ERROR] Python 3.10 이상이 필요합니다. python3 --version을 확인하세요.", file=sys.stderr)
        sys.exit(2)
    from gitgen.cli import main

    sys.exit(main())
