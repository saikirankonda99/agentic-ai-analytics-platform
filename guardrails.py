from __future__ import annotations

import re


_BLOCKED_WORDS = {
    "drop", "delete", "update", "insert", "alter", "truncate", "create", "replace",
    "attach", "detach", "pragma", "vacuum", "reindex", "analyze", "grant", "revoke",
    "copy", "call", "execute", "exec", "do", "set", "reset", "into", "load", "install",
    "load_extension", "writefile", "readfile", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "lo_import", "lo_export", "dblink",
}


def _sql_structure(sql: str) -> str | None:
    """Conservatively tokenize SQL; database read-only permissions remain the final boundary."""
    result = []
    index = 0
    while index < len(sql):
        if sql.startswith("--", index):
            end = sql.find("\n", index + 2)
            index = len(sql) if end < 0 else end + 1
            result.append(" ")
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0 or "/*" in sql[index + 2:end]:
                return None
            index = end + 2
            result.append(" ")
        elif sql[index] in "'\"`[":
            quoted_identifier = sql[index] != "'"
            closer = "]" if sql[index] == "[" else sql[index]
            index += 1
            start = index
            while index < len(sql):
                if sql[index] == closer:
                    if closer != "]" and index + 1 < len(sql) and sql[index + 1] == closer:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                return None
            identifier = sql[start:index - 1].replace(closer + closer, closer)
            result.append(f" {identifier} " if quoted_identifier and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", identifier) else " ? ")
        else:
            result.append(sql[index])
            index += 1
    return "".join(result)


def is_safe_sql(sql: str) -> bool:
    if not isinstance(sql, str) or len(sql) > 100_000:
        return False
    structure = _sql_structure(sql)
    if structure is None:
        return False
    structure = structure.strip()
    if structure.endswith(";"):
        structure = structure[:-1].rstrip()
    if ";" in structure or not re.match(r"^(select|with)\b", structure, flags=re.IGNORECASE):
        return False
    words = set(re.findall(r"\b[a-z_][a-z_0-9]*\b", structure.lower()))
    return not bool(words & _BLOCKED_WORDS)
