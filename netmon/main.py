from __future__ import annotations

import argparse
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="netmon",
        description="Network monitor with AI analysis for Linux",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    return parser.parse_args()


def main() -> None:
    _parse_args()

    # Проверяем зависимости при старте
    try:
        import psutil  # noqa: F401
        import textual  # noqa: F401
        import anthropic  # noqa: F401
    except ImportError as e:
        print(f"[netmon] Отсутствует зависимость: {e}", file=sys.stderr)
        print("Установи: pip install -e .", file=sys.stderr)
        sys.exit(1)

    from netmon.ui.app import NetmonApp
    app = NetmonApp()
    app.run()


if __name__ == "__main__":
    main()
