import subprocess
from pathlib import Path
from typing import Any, Dict
from src.filters import build_filter_chain_string
from src.analyze import analyze_audio, suggest_filter_config, validate_output


def _get_fallback_config() -> Dict[str, Any]:
    """
    Возвращает агрессивную конфигурацию для удаления музыки.
    """
    return {
        "audio_codec": "aac",
        "audio_bitrate": "256k",
        "audio_filters": [
            {"name": "pan", "args": {"args": "mono|c0=0.5*c0+0.5*c1"}},
            {"name": "highpass", "args": {"f": 300, "p": 2}},
            {"name": "lowpass", "args": {"f": 3000, "p": 2}},
            {"name": "afftdn", "args": {"nr": 30, "nf": -50, "tn": 1}},
            {"name": "afftdn", "args": {"nr": 20, "nf": -40, "tn": 1}},
            {
                "name": "agate",
                "args": {
                    "threshold": 0.04,
                    "ratio": 50,
                    "attack": 1,
                    "release": 100,
                    "knee": 1,
                    "detection": "rms",
                },
            },
            {
                "name": "equalizer",
                "args": {"f": 800, "width_type": "o", "width": 1.2, "g": 8},
            },
            {
                "name": "equalizer",
                "args": {"f": 2000, "width_type": "o", "width": 1, "g": 6},
            },
            {
                "name": "equalizer",
                "args": {"f": 400, "width_type": "o", "width": 1.5, "g": -6},
            },
            {
                "name": "acompressor",
                "args": {
                    "threshold": "-25dB",
                    "ratio": 8,
                    "attack": 2,
                    "release": 50,
                    "makeup": 10,
                },
            },
            {"name": "alimiter", "args": {"limit": 0.9, "attack": 3, "release": 50}},
            {"name": "loudnorm", "args": {"I": -14, "LRA": 8, "TP": -0.5}},
        ],
    }


def process_file(
    input_path: Path,
    output_path: Path,
    cfg: Dict[str, Any],
    overwrite: bool = True,
) -> None:
    """
    Обрабатывает видеофайл с автоматическим анализом или ручной конфигурацией.

    Если в cfg указан "auto_analyze": true, то анализирует файл и генерирует
    оптимальные параметры. Иначе использует параметры из cfg.
    """

    # Проверяем, нужен ли автоанализ
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
                print(" ОБНАРУЖЕН КЛИППИНГ")

            # Генерируем оптимальную конфигурацию
            cfg = suggest_filter_config(analysis)
            print(f"\nСгенерировано фильтров: {len(cfg['audio_filters'])}")

        except Exception as e:
            print(f"  ⚠ Ошибка анализа: {e}")
            print(f"  Использую безопасную конфигурацию по умолчанию")

            # Генерируем безопасную конфигурацию
            cfg = _get_fallback_config()

    # Строим цепочку фильтров
    filters_cfg = cfg.get("audio_filters", [])

    # ВАЖНО: если фильтры пустые, используем fallback
    if not filters_cfg:
        print(f"  ⚠ Нет фильтров в конфигурации, использую fallback")
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
        print(f"\n✓ Обработка завершена")

        # Валидация результата
        print(f"\n{'=' * 60}")
        print("Валидация результата")
        print("=" * 60)

        valid, message = validate_output(input_path, output_path)

        if valid:
            print(f"  ✓ {message}")
        else:
            print(f"  ⚠ {message}")

    except subprocess.CalledProcessError as e:
        print(f"\n✗ ОШИБКА при обработке {input_path.name}")
        raise
