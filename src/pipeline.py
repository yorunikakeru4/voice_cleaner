import subprocess
from pathlib import Path
from typing import Any, Dict

from src.filters import build_filter_chain_string


def process_file(
    input_path: Path,
    output_path: Path,
    cfg: Dict[str, Any],
    overwrite: bool = True,
) -> None:
    filters_cfg = cfg.get("audio_filters", [])
    af_chain = build_filter_chain_string(filters_cfg)

    acodec = cfg.get("audio_codec", "aac")
    abitrate = cfg.get("audio_bitrate", "192k")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        input_path,
        "-c:v",
        "copy",
        "-af",
        af_chain,
        "-c:a",
        acodec,
        "-b:a",
        abitrate,
    ]

    if overwrite:
        cmd.append("-y")

    cmd.append(output_path)

    subprocess.run(cmd, check=True)
