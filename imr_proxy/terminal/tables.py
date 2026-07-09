from rich.table import Table
def sessions_table(rows):
    t=Table(title="imr-proxy sessions"); [t.add_column(c) for c in ["ID","Name","Version","Created"]]
    for r in rows: t.add_row(r["id"], r["name"], r["version"], r["created_at"])
    return t
