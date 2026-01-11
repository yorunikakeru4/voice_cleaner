import subprocess
from pathlib import Path
from typing import Any, Dict
from src.filters import build_filter_chain_string
from src.analyze import analyze_audio, suggest_filter_config, validate_output


def _get_fallback_config() -> Dict[str, Any]:
    """
    Безопасная конфигурация по умолчанию:
    мягкая очистка и нормализация без гейта/лимитера.
    """
    return {
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "audio_filters": [
            {"name": "highpass", "args": {"f": 90, "p": 1}},
            {"name": "afftdn", "args": {"nr": 4, "nf": -35}},
            {
                "name": "acompressor",
                "args": {
                    "threshold": "-20dB",
                    "ratio": 2.5,
                    "attack": 10,
                    "release": 120,
                    "makeup": 2,
                },
            },
            {"name": "loudnorm", "args": {"I": -16, "LRA": 11, "TP": -1.5}},
        ],
    }


def process_file(
    input_path: Path,
    output_path: Path,
    cfg: Dict[str, Any],
    isAggressive: bool = False,
    overwrite: bool = True,
) -> None:
    """
    Обрабатывает видеофайл с автоматическим анализом или ручной конфигурацией.

    Если в cfg указан "auto_analyze": true, то анализирует файл и генерирует
    оптимальные параметры. Иначе использует параметры из cfg.
    """

    use_auto_analyze = cfg.get("auto_analyze", False)

    if use_auto_analyze:
        print(f"\n{'=' * 60}")
        print(f"Анализ: {input_path.name}")
        print("=" * 60)

        try:
            analysis = analyze_audio(input_path)

            print(f"  Частота дискретизации: {analysis['sample_rate']} Hz")
            print(f"  Каналы: {analysis['channels']}")
            print(f"  Длительность: {analysis['duration']:.2f} сек")
            print(f"  RMS уровень: {analysis['rms_level_db']:.2f} dB")
            print(f"  Пиковый уровень: {analysis['peak_level_db']:.2f} dB")
            print(f"  Динамический диапазон: {analysis['dynamic_range_db']:.2f} dB")
            print(f"  Уровень шума: {analysis['noise_level'].upper()}")
            if analysis["clipping_detected"]:
                print("ОБНАРУЖЕН КЛИППИНГ")
            profile = "aggressive" if isAggressive else "light"
            cfg = suggest_filter_config(analysis, profile)
            print(f"\nСгенерировано фильтров: {len(cfg['audio_filters'])}")

        except Exception as e:
            print(f"   Ошибка анализа: {e}")
            print("Использую безопасную конфигурацию по умолчанию")

            cfg = _get_fallback_config()

    filters_cfg = cfg.get("audio_filters", [])

    if not filters_cfg:
        print("Нет фильтров в конфигурации, использую fallback")
        cfg = _get_fallback_config()
        filters_cfg = cfg.get("audio_filters", [])

    af_chain = build_filter_chain_string(filters_cfg)

    acodec = cfg.get("audio_codec", "aac")
    abitrate = cfg.get("audio_bitrate", "192k")

    print(f"\n{'=' * 60}")
    print(f"Обработка: {input_path.name}")
    print("=" * 60)
    print(f"  Выходной файл: {output_path.name}")
    print(f"  Аудиокодек: {acodec}")
    print(f"  Битрейт: {abitrate}")
    print(f"  Фильтров в цепочке: {len(filters_cfg)}")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stats",
        "-i",
        str(input_path),
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

    cmd.append(str(output_path))

    try:
        subprocess.run(cmd, check=True)
        print("\n Обработка завершена")

        print(f"\n{'=' * 60}")
        print("Валидация результата")
        print("=" * 60)

        valid, message = validate_output(input_path, output_path)

        if valid:
            print(f"   {message}")
        else:
            print(f"   {message}")

    except subprocess.CalledProcessError:
        print(f"\n✗ ОШИБКА при обработке {input_path.name}")
        raise
