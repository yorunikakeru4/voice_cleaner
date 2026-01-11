import subprocess
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple


def analyze_audio(input_path: Path) -> Dict[str, Any]:
    """
    Анализирует аудиодорожку видеофайла и возвращает параметры.
    """
    try:
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels,duration,bit_rate",
            "-of",
            "json",
            str(input_path),
        ]
        probe_result = subprocess.run(
            probe_cmd, capture_output=True, text=True, check=True
        )
        probe_data = json.loads(probe_result.stdout)

        if not probe_data.get("streams"):
            raise ValueError("Аудиодорожка не найдена")

        stream_info = probe_data["streams"][0]

        sample_rate = int(stream_info.get("sample_rate", 48000))
        channels = int(stream_info.get("channels", 2))
        duration = float(stream_info.get("duration", 0))

    except Exception:
        print(
            "Не удалось получить информацию о файле, использую значения по умолчанию."
        )
        sample_rate = 48000
        channels = 2
        duration = 30.0

    stats_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        "astats=metadata=1:reset=1",
        "-f",
        "null",
        "-",
    ]
    stats_result = subprocess.run(stats_cmd, capture_output=True, text=True)

    rms_level = _parse_rms_from_output(stats_result.stderr)
    peak_level = _parse_peak_from_output(stats_result.stderr)

    volume_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    volume_result = subprocess.run(volume_cmd, capture_output=True, text=True)
    mean_volume = _parse_mean_volume(volume_result.stderr)
    max_volume = _parse_max_volume(volume_result.stderr)
    clipping_detected = peak_level > -0.1
    dynamic_range = abs(peak_level - rms_level) if (peak_level and rms_level) else 20.0

    noise_level = _estimate_noise_level(rms_level, dynamic_range, mean_volume)
    analysis = {
        "sample_rate": sample_rate,
        "channels": channels,
        "duration": duration,
        "rms_level_db": rms_level,
        "peak_level_db": peak_level,
        "mean_volume_db": mean_volume,
        "dynamic_range_db": dynamic_range,
        "clipping_detected": clipping_detected,
        "max_volume_db": max_volume,
        "noise_level": noise_level,
    }

    return analysis


def _parse_rms_from_output(stderr: str) -> float:
    matches = re.findall(r"RMS level dB:\s*([-\d.]+)", stderr)
    vals = []
    for v in matches:
        try:
            vals.append(float(v))
        except ValueError:
            continue
    return sum(vals) / len(vals) if vals else -30.0


def _parse_max_volume(stderr: str) -> float:
    match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", stderr)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _parse_peak_from_output(stderr: str) -> float:
    matches = re.findall(r"Peak level dB:\s*([-\d.]+)", stderr)
    vals = []
    for v in matches:
        try:
            vals.append(float(v))
        except ValueError:
            continue
    return max(vals) if vals else -3.0


def _parse_mean_volume(stderr: str) -> float:
    """Извлекает средний уровень громкости."""
    match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", stderr)
    if match:
        try:
            value = match.group(1)
            if value == "-":
                return -20.0
            return float(value)
        except ValueError:
            return -20.0
    return -20.0


def _estimate_noise_level(
    rms_level: float, dynamic_range: float, mean_volume: float
) -> str:
    if rms_level > -12 and dynamic_range < 8 and mean_volume > -14:
        return "high"
    elif rms_level > -22 and dynamic_range < 18:
        return "medium"
    else:
        return "low"


def suggest_filter_config(
    analysis: Dict[str, Any],
    profile: str = "light",
) -> Dict[str, Any]:
    """
    Генерирует конфигурацию фильтров для речевых видео.
    Профили:
      - light: мягкая очистка + выравнивание
      - aggressive: более сильное шумоподавление и контроль динамики
    """
    noise_level = analysis.get("noise_level", "medium")

    config = {
        "audio_codec": "aac",
        "audio_bitrate": "192k" if profile == "light" else "256k",
        "audio_filters": [],
    }

    if profile == "light":
        hp_freq = 80 if noise_level == "low" else 90
    else:
        hp_freq = 100 if noise_level == "low" else 120

    config["audio_filters"].append({"name": "highpass", "args": {"f": hp_freq, "p": 1}})

    if noise_level != "low":
        lp_freq = 14000 if profile == "light" else 12000
        config["audio_filters"].append(
            {
                "name": "lowpass",
                "args": {"f": lp_freq, "p": 1},
            }
        )

    if noise_level != "low":
        if profile == "light":
            afftdn_args = {
                "nr": 4,
                "nf": -35,
            }
        else:
            afftdn_args = {
                "nr": 6,
                "nf": -30,
                "tn": 1,
            }

        config["audio_filters"].append(
            {
                "name": "afftdn",
                "args": afftdn_args,
            }
        )

    if profile == "light":
        comp_args = {
            "threshold": "-20dB",
            "ratio": 2.5,
            "attack": 10,
            "release": 120,
            "makeup": 2,
        }
    else:
        comp_args = {
            "threshold": "-22dB",
            "ratio": 3,
            "attack": 8,
            "release": 120,
            "makeup": 3,
        }

    config["audio_filters"].append(
        {
            "name": "acompressor",
            "args": comp_args,
        }
    )

    if profile == "aggressive" and noise_level in ("medium", "high"):
        config["audio_filters"].append(
            {
                "name": "agate",
                "args": {
                    "threshold": 0.005,
                    "ratio": 4,
                    "attack": 5,
                    "release": 150,
                    "knee": 2,
                    "detection": "rms",
                    "link": "average",
                },
            }
        )

    loudnorm_args = {
        "I": -16,
        "LRA": 11,
        "TP": -1.5,
    }

    config["audio_filters"].append(
        {
            "name": "loudnorm",
            "args": loudnorm_args,
        }
    )

    return config


def validate_output(input_path: Path, output_path: Path) -> Tuple[bool, str]:
    """
    Проверяет корректность выходного файла.
    """

    def get_duration(path):
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    try:
        input_duration = get_duration(input_path)
        output_duration = get_duration(output_path)

        if abs(input_duration - output_duration) > 0.1:
            return (
                False,
                f"Рассинхрон: вход={input_duration:.2f}s, выход={output_duration:.2f}s",
            )

        stats_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(output_path),
            "-af",
            "astats=metadata=1",
            "-f",
            "null",
            "-",
        ]
        stats_result = subprocess.run(stats_cmd, capture_output=True, text=True)
        peak = _parse_peak_from_output(stats_result.stderr)

        if peak and peak > -0.5:
            return False, f"Обнаружен клиппинг: пик={peak:.2f}dB"

        return True, "Длительность совпадает, клиппинг отсутствует"

    except Exception as e:
        return False, f"Ошибка валидации: {e}"
