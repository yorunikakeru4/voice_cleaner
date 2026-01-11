from typing import Any, Dict, List


def build_filter_chain_string(filters_cfg: List[Dict[str, Any]]) -> str:
    """
    Строит цепочку ffmpeg аудиофильтров из конфигурации.

    Args:
        filters_cfg: Список словарей с ключами 'name' и 'args'

    Returns:
        Строка фильтров для параметра -af в ffmpeg

    Example:
        >>> cfg = [
        ...     {"name": "highpass", "args": {"f": 200, "p": 2}},
        ...     {"name": "lowpass", "args": {"f": 3500}}
        ... ]
        >>> build_filter_chain_string(cfg)
        'highpass=f=200:p=2,lowpass=f=3500'
    """
    filter_strings = []

    for flt in filters_cfg:
        name = flt.get("name")
        args = flt.get("args", {})

        if not name:
            continue

        if name == "pan" and "args" in args:
            filter_strings.append(f"pan={args['args']}")
        elif name == "loudnorm":
            parts = []
            if "I" in args:
                parts.append(f"I={args['I']}")
            if "LRA" in args:
                parts.append(f"LRA={args['LRA']}")
            if "TP" in args:
                parts.append(f"TP={args['TP']}")
            filter_strings.append(f"loudnorm={':'.join(parts)}")
        elif args:
            arg_parts = [f"{k}={v}" for k, v in args.items() if k != "args"]
            if arg_parts:
                filter_strings.append(f"{name}={':'.join(arg_parts)}")
            else:
                filter_strings.append(name)
        else:
            filter_strings.append(name)

    return ",".join(filter_strings)
