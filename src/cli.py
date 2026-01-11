import argparse
from pathlib import Path

CONFIG_FILE = Path("config/filters.json")
INPUT_DIR = Path("data/fixtures")
OUTPUT_DIR = Path("data/output")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Voice cleaner")

    p.add_argument(
        "input",
        type=str,
        help="Input video file or directory, or 'auto' to use defaults",
    )
    p.add_argument(
        "output",
        nargs="?",
        type=str,
        help="Output file or directory (ignored in 'auto' mode)",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to filters config (JSON); ignored in 'auto' mode",
    )
    return p.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """
    Превращает аргументы в реальные пути с учётом режима 'auto'.
    """
    if args.input == "auto":
        in_path = INPUT_DIR
        out_path = OUTPUT_DIR
        cfg_path = CONFIG_FILE
    else:
        in_path = Path(args.input)
        if args.output is None:
            raise SystemExit("OUTPUT path is required when not using 'auto' mode")
        out_path = Path(args.output)
        cfg_path = args.config or CONFIG_FILE

    return in_path, out_path, cfg_path
