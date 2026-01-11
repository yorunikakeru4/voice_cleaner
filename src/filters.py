from typing import Any, Dict, List


def build_filter_chain_string(filters_cfg):
    parts = []
    for flt in filters_cfg:
        seg = _build_simple_filter(flt)
        if seg:
            parts.append(seg)
    # линейный chain, поэтому запятая
    return ",".join(parts)


def _build_asplit(flt: Dict[str, Any]) -> str:
    """
    Создаёт asplit фильтр.
    Пример: asplit=2[speech][music]
    """
    args = flt.get("args", {})
    n = args.get("n", 2)
    output_labels = flt.get("output_labels", [])

    labels_str = "".join(f"[{lbl}]" for lbl in output_labels)
    return f"asplit={n}{labels_str}"


def _build_chain(flt: Dict[str, Any]) -> str:
    """
    Создаёт цепочку фильтров с входной и выходной метками.
    Пример: [speech]highpass=f=100,lowpass=f=4000,volume=3dB[speech_clean]
    """
    input_label = flt.get("input_label")
    output_label = flt.get("output_label")
    filters = flt.get("filters", [])

    if not filters:
        return ""

    # Строим последовательность фильтров
    filter_parts = []
    for f in filters:
        fname = f.get("name")
        fargs = f.get("args", {})
        filter_parts.append(_format_filter(fname, fargs))

    chain_str = ",".join(filter_parts)

    # Добавляем метки
    if input_label and output_label:
        return f"[{input_label}]{chain_str}[{output_label}]"
    elif input_label:
        return f"[{input_label}]{chain_str}"
    elif output_label:
        return f"{chain_str}[{output_label}]"
    else:
        return chain_str


def _build_ducking(flt: Dict[str, Any]) -> str:
    """
    Создаёт sidechaincompress для ducking эффекта.
    Формат: [музыка][речь]sidechaincompress=threshold=0.015:ratio=10[музыка_ducked]

    inputs[0] = основной сигнал (музыка)
    inputs[1] = sidechain (речь)
    """
    inputs = flt.get("inputs", [])
    filter_name = flt.get("filter", "sidechaincompress")
    args = flt.get("args", {})
    output_label = flt.get("output_label")

    if len(inputs) < 2:
        return ""

    inputs_str = f"[{inputs[0]}][{inputs[1]}]"
    args_str = _format_args(args)
    filter_str = f"{filter_name}={args_str}" if args_str else filter_name

    if output_label:
        return f"{inputs_str}{filter_str}[{output_label}]"
    else:
        return f"{inputs_str}{filter_str}"


def _build_amix(flt: Dict[str, Any]) -> str:
    """
    Создаёт amix для смешивания потоков.
    Пример: [speech_clean][music_ducked]amix=inputs=2:weights=1.0 0.25[mixed]
    """
    inputs = flt.get("inputs", [])
    args = flt.get("args", {})
    output_label = flt.get("output_label")

    if not inputs:
        return ""

    inputs_str = "".join(f"[{inp}]" for inp in inputs)
    args_str = _format_args(args)
    filter_str = f"amix={args_str}" if args_str else "amix"

    if output_label:
        return f"{inputs_str}{filter_str}[{output_label}]"
    else:
        return f"{inputs_str}{filter_str}"


def _build_simple_filter(flt: Dict[str, Any]) -> str:
    """
    Создаёт простой фильтр с опциональными метками.
    Пример: [mixed]loudnorm=I=-16:LRA=11:TP=-1.5
    """
    name = flt.get("name")
    args = flt.get("args", {})
    input_label = flt.get("input_label")
    output_label = flt.get("output_label")
    if not name:
        return ""
    filter_str = _format_filter(name, args)

    if input_label and output_label:
        return f"[{input_label}]{filter_str}[{output_label}]"
    elif input_label:
        return f"[{input_label}]{filter_str}"
    elif output_label:
        return f"{filter_str}[{output_label}]"
    else:
        return filter_str


def _format_filter(name: str, args: Dict[str, Any]) -> str:
    """Форматирует одиночный фильтр с аргументами."""
    if not name:
        return ""

    # Специальная обработка для pan
    if name == "pan" and "args" in args:
        return f"pan={args['args']}"

    # Специальная обработка для loudnorm (использует : вместо =)
    if name == "loudnorm":
        parts = []
        if "I" in args:
            parts.append(f"I={args['I']}")
        if "LRA" in args:
            parts.append(f"LRA={args['LRA']}")
        if "TP" in args:
            parts.append(f"TP={args['TP']}")
        return f"loudnorm={':'.join(parts)}" if parts else "loudnorm"

    # Специальная обработка для volume (чтобы не было volume=volume=X)
    if name == "volume":
        vol_value = args.get("volume", 1.0)
        return f"volume={vol_value}"

    # Обычные фильтры
    args_str = _format_args(args)
    return f"{name}={args_str}" if args_str else name


def _format_args(args: Dict[str, Any]) -> str:
    """Форматирует аргументы фильтра в строку key=value:key=value."""
    parts = []
    for k, v in args.items():
        if k == "args":  # Служебное поле
            continue
        parts.append(f"{k}={v}")
    return ":".join(parts)
