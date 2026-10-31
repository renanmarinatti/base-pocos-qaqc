"""Roda as consultas de exemplo (sql/consultas.sql) e grava o resultado em docs/consultas.md.

Mostra que o banco responde perguntas de quem usa o dado, em SQL puro, sem Python no meio.

Uso: uv run python -m pocos.queries
"""

import re
from pathlib import Path

import duckdb

from pocos.database import DB

QUERIES = Path("sql/consultas.sql")
OUTPUT = Path("docs/consultas.md")


def parse(text: str) -> list[tuple[str, str]]:
    blocks = re.split(r"^-- name: (.+)$", text, flags=re.M)[1:]
    return [
        (title.strip(), sql.strip()) for title, sql in zip(blocks[::2], blocks[1::2], strict=True)
    ]


def markdown_table(df) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(lines)


def run() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    out = [
        "# Consultas de exemplo",
        "",
        "Geradas de `sql/consultas.sql` sobre o banco final (`uv run python -m pocos.queries`).",
        "",
    ]
    queries = parse(QUERIES.read_text(encoding="utf-8"))
    for title, sql in queries:
        out += [
            f"## {title}",
            "",
            "```sql",
            sql,
            "```",
            "",
            markdown_table(con.execute(sql).df()),
            "",
        ]
    con.close()
    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    return len(queries)


if __name__ == "__main__":
    print(run(), "consultas")
