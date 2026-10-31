"""Roda o case inteiro, da coleta ao banco e à exportação, em ordem.

Cada etapa lê o que a anterior gravou em disco, então também dá para rodar uma etapa só
(uv run python -m pocos.<etapa>). A coleta não baixa de novo o que já está em disco.

Uso: uv run python -m pocos.pipeline
"""

from pocos import (
    collect,
    database,
    export,
    figures,
    inventory,
    quality,
    queries,
    reconcile,
    report,
    standardize,
)

STEPS = [
    ("E1 coleta", lambda: collect.collect(collect.load_sources())),
    ("E1 inventário", inventory.run),
    ("E2 padronização", standardize.run),
    ("E3 regras de qualidade", quality.run),
    ("E4 conciliação", reconcile.run),
    ("E5 banco e dicionário", database.run),
    ("E5 exportação", export.run),
    ("E5 consultas de exemplo", queries.run),
    ("figuras", figures.run),
    ("E6 relatório e fichas", report.run),
]


def run() -> None:
    for name, step in STEPS:
        print(f"== {name}")
        step()


if __name__ == "__main__":
    run()
