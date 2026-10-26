import json
from datetime import datetime


def to_dict(obj):
    data = {}
    for col in getattr(obj, "__table__", None).columns if hasattr(obj, "__table__") else []:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[col.name] = val
    return data


def from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
