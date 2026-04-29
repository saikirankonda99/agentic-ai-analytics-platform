def is_safe_sql(sql: str) -> bool:
    sql = sql.lower()

    blocked = ["drop", "delete", "update", "insert", "alter"]

    return not any(word in sql for word in blocked)