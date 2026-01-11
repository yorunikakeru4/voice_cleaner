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
        # Получаем базовую информацию через ffprobe
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
        # Если не можем получить базовую информацию, используем дефолты
        sample_rate = 48000
        channels = 2
        duration = 30.0

    # Анализ статистики с помощью astats
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

    # Парсим RMS и пиковые значения
    rms_level = _parse_rms_from_output(stats_result.stderr)
    peak_level = _parse_peak_from_output(stats_result.stderr)

    # Анализ громкости
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

    # Детект клиппинга
    clipping_detected = peak_level > -0.1 if peak_level else False

    # Оценка динамического диапазона
    dynamic_range = abs(peak_level - rms_level) if (peak_level and rms_level) else 20.0

    # Определяем уровень шума
    noise_level = _estimate_noise_level(rms_level, dynamic_range)

    analysis = {
        "sample_rate": sample_rate,
        "channels": channels,
        "duration": duration,
        "rms_level_db": rms_level,
        "peak_level_db": peak_level,
        "mean_volume_db": mean_volume,
        "dynamic_range_db": dynamic_range,
        "clipping_detected": clipping_detected,
        "noise_level": noise_level,
    }

    return analysis


def _parse_rms_from_output(stderr: str) -> float:
    """Извлекает RMS уровень из вывода astats."""
    match = re.search(r"RMS level dB:\s*([-\d.]+)", stderr)
    if match:
        try:
            value = match.group(1)
            if value == "-":
                return -30.0
            return float(value)
        except ValueError:
            return -30.0
    return -30.0


def _parse_peak_from_output(stderr: str) -> float:
    """Извлекает пиковый уровень."""
    match = re.search(r"Peak level dB:\s*([-\d.]+)", stderr)
    if match:
        try:
            value = match.group(1)
            if value == "-":
                return -3.0
            return float(value)
        except ValueError:
            return -3.0
    return -3.0


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


def _estimate_noise_level(rms_level: float, dynamic_range: float) -> str:
    """
    Оценивает уровень шума:
    - high: громкая музыка/шум, мало динамики
    - medium: средний уровень
    - low: чистая запись
    """
    if rms_level > -15 and dynamic_range < 10:
        return "high"
    elif rms_level > -25 and dynamic_range < 20:
        return "medium"
    else:
        return "low"


def suggest_filter_config(analysis):
    """
    HQ профиль: максимум качества без ML.
    """
    noise_level = analysis["noise_level"]

    # Параметры подавления зависят от шума

    if noise_level == "high":
        afftdn = {"nr": 10, "nf": -45, "rf": -55}
    elif noise_level == "medium":
        afftdn = {"nr": 8, "nf": -50, "rf": -60}
    else:
        afftdn = {"nr": 6, "nf": -60, "rf": -70}

    return {
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "audio_filters": [
            # 1. В моно (снижает фазовую музыку)
            {
                "name": "pan",
                "args": {"args": "mono|c0=0.5*c0+0.5*c1"},
            },
            # 2. МЯГКО формируем речь (НЕ режем топором)
            {"name": "highpass", "args": {"f": 80}},
            {"name": "lowpass", "args": {"f": 6000}},
            # 3. Лёгкое подавление мути
            {
                "name": "equalizer",
                "args": {"f": 300, "width_type": "o", "width": 1.0, "g": -1.5},
            },
            # 4. Подчёркиваем разборчивость
            {
                "name": "equalizer",
                "args": {"f": 1800, "width_type": "o", "width": 1.0, "g": 3},
            },
            {
                "name": "equalizer",
                "args": {"f": 4200, "width_type": "o", "width": 0.8, "g": 2},
            },
            # 5. Основное шумоподавление (ЛУЧШЕ afftdn)
            {
                "name": "afftdn",
                "args": afftdn,
            },
            # 6. Downward expander вместо gate
            {
                "name": "agate",
                "args": {
                    "threshold": 0.02,
                    "ratio": 3,
                    "attack": 5,
                    "release": 200,
                },
            },
            # 7. Мягкая компрессия речи
            {
                "name": "acompressor",
                "args": {
                    "threshold": "-22dB",
                    "ratio": 2.5,
                    "attack": 8,
                    "release": 90,
                    "makeup": 4,
                },
            },
            # 8. Loudness (без убийства динамики)
            {
                "name": "loudnorm",
                "args": {
                    "I": -18,
                    "LRA": 9,
                    "TP": -1.2,
                },
            },
            # 9. Safety limiter
            {
                "name": "alimiter",
                "args": {"limit": 0.98, "attack": 2, "release": 60},
            },
        ],
    }


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

        # Проверка синхронизации (допуск 0.1 сек)
        if abs(input_duration - output_duration) > 0.1:
            return (
                False,
                f"Рассинхрон: вход={input_duration:.2f}s, выход={output_duration:.2f}s",
            )

        # Проверка клиппинга
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
