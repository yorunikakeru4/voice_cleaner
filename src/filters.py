from typing import Any, Dict, List


def build_filter_chain_string(filters_cfg: List[Dict[str, Any]]) -> str:
    """
    Из списка фильтров делает строку для -af.
    Пример одного элемента: { "name": "highpass", "args": {"f": 80} }
    """
    parts: List[str] = []
    for f in filters_cfg:
        name = f["name"]
        args = f.get("args") or {}

        arg_items: List[str] = []
        for k, v in args.items():
            arg_items.append(f"{k}={v}")

        if arg_items:
            parts.append(f"{name}=" + ":".join(arg_items))
        else:
            parts.append(name)

    return ",".join(parts)
