from __future__ import annotations

import re


def is_safe_sql(sql: str) -> bool:
    normalized = re.sub(r"--.*?$|/\*.*?\*/", " ", sql.lower(), flags=re.MULTILINE | re.DOTALL)
    blocked = ("drop", "delete", "update", "insert", "alter", "truncate", "create", "replace", "attach", "detach")
    return not any(re.search(rf"\b{word}\b", normalized) for word in blocked)
