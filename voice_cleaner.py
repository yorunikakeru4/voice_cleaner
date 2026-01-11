from src.config import load_config
from src.cli import parse_args, resolve_paths
from src.pipeline import process_file


def main():
    args = parse_args()
    in_path, out_path, cfg_path = resolve_paths(args)
    cfg = load_config(cfg_path)
    if in_path.is_dir():
        out_path.mkdir(parents=True, exist_ok=True)
        for f in in_path.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() not in {".mp4", ".mkv", ".mov"}:
                continue
            out_file = out_path / f.name
            process_file(f, out_file, cfg)
    else:
        if out_path.is_dir():
            out_file = out_path / in_path.name
        else:
            out_file = out_path
        process_file(in_path, out_file, cfg)


if __name__ == "__main__":
    main()
