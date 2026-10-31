"""Entregas para pessoas (E6): relatório de qualidade e ficha de pendências por poço.

Tudo sai do banco final e das tabelas de conciliação, nada é digitado à mão: se o pipeline
roda de novo, o relatório e as fichas mudam junto.

- docs/relatorio.html: proveniência no topo, números de antes × depois, problemas por
  regra, conciliação e decisões. Abre direto no navegador.
- docs/fichas/<poço>.md: o que o intérprete precisa decidir, o que falta no dado e o que
  a base já tratou, poço a poço. O índice (docs/fichas/README.md) ordena pela nota.

Uso: uv run python -m pocos.report
"""

import html
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from pocos.database import DB, DECISIONS
from pocos.inventory import PROCESSED
from pocos.standardize import INTERIM

REPORT = Path("docs/relatorio.html")
README = Path("README.md")
SHEETS = Path("docs/fichas")

# Para a ficha, cada regra cai num de dois grupos: o dado está lá mas pede julgamento de
# quem interpreta, ou o dado simplesmente falta. R12 não entra: a base já trocou o código
# de nulo (D10), e isso aparece em "já tratado".
NEEDS_DECISION = {"R02", "R03", "R05", "R06", "R08", "R10", "R11", "R14"}
MISSING = {"R01", "R04", "R07", "R09", "R13", "R15"}
SEVERITY_ORDER = {"alta": 0, "media": 1, "baixa": 2}
SEVERITY_LABEL = {"alta": "alta", "media": "média", "baixa": "baixa"}
TOP_CLASSES = [
    "igual",
    "divergente",
    "deslocamento uniforme do poço",
    "fora do trecho perfilado",
    "só na Sodir",
    "só em npd_2020",
    "só em perfil_force",
]
BASIC_CURVES = ["GR", "RHOB", "NPHI", "DTC", "RDEP"]
HINTS = {
    "R02": "O valor está no banco sem correção; conferir a ferramenta no trecho.",
    "R08": "Para usar a densidade, filtrar `amostra.rhob_arrombado`.",
    "R14": "Para usar o PEF como indicador de litologia, filtrar `amostra.pef_baritina`.",
}


def well_slug(well: str) -> str:
    return re.sub(r"[/ ]+", "_", well)


def sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def fmt(value, digits: int = 0) -> str:
    """Número no formato brasileiro: ponto no milhar, vírgula na decimal."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    text = f"{value:,.{digits}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def decision_sections(text: str) -> dict[str, str]:
    """D01..Dnn -> texto da seção, para saber quais decisões citam cada poço."""
    parts = re.split(r"^## (D\d+) — ", text, flags=re.M)[1:]
    return {code: body for code, body in zip(parts[::2], parts[1::2], strict=True)}


def decisions_for(well: str, sections: dict[str, str]) -> list[str]:
    return [code for code, body in sections.items() if f"`{well}`" in body]


def name_matches(tops_raw: pd.DataFrame) -> tuple[int, int]:
    """Topos de 2020 que casam com a Sodir sem conciliação: pelo nome exato e só tirando
    o ponto final e passando para maiúsculas."""

    def keys(source: str, clean) -> set:
        t = tops_raw[tops_raw["fonte"] == source]
        return set(zip(t["poco"], clean(t["unidade"].str.strip()), strict=True))

    def trivial(s: pd.Series) -> pd.Series:
        return s.str.upper().str.rstrip(".")

    exact = len(keys("npd_2020", lambda s: s) & keys("sodir", lambda s: s))
    return exact, len(keys("npd_2020", trivial) & keys("sodir", trivial))


def before_after(con: duckdb.DuckDBPyConnection, tops_raw: pd.DataFrame, rec: dict) -> list:
    """Linhas (o quê, antes, depois, como) do quadro principal do relatório e do README."""
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    wells = q("SELECT count(*) FROM poco")
    same_name = q("SELECT count(*) FROM poco WHERE poco = poco_force")

    exact, _ = name_matches(tops_raw)
    matched = sum(v for k, v in rec["topos"]["npd_2020 × sodir"].items() if not k.startswith("só"))
    samples = q("SELECT count(*) FROM amostra")
    no_trajectory = json.loads((PROCESSED / "padronizacao.json").read_text(encoding="utf-8"))[
        "amostras_sem_trajetoria"
    ]
    nulls = json.loads((PROCESSED / "banco.json").read_text(encoding="utf-8"))
    swapped = sum(nulls["nulos_trocados_D10"].values())
    official = pd.read_csv(PROCESSED / "topos_oficiais.csv")
    problems = q("SELECT count(*) FROM problema")
    rules = q("SELECT count(*) FROM regra")
    return [
        (
            "Poços ligados ao cadastro oficial (Sodir)",
            f"{same_name} de {wells} pelo nome",
            f"{wells} de {wells}",
            "dois desvios técnicos mapeados por posição e mesa rotativa (D01, D02)",
        ),
        (
            "Topos de 2020 casados com os topos oficiais de hoje",
            f"{fmt(exact)} pelo nome exato",
            fmt(matched),
            "nome-base, grafia norueguesa, duas renomeações (D03)",
        ),
        (
            "Amostras com profundidade medida (MD)",
            fmt(samples - no_trajectory),
            fmt(samples),
            "índice do LAS no lugar da coluna de trajetória (D06)",
        ),
        (
            "Códigos de ausência de dado",
            "2 (−999,25 e −999)",
            "1 (NULL)",
            f"{fmt(swapped)} valores trocados em 34/11-2 S (D10)",
        ),
        (
            "Topos oficiais com profundidade vertical (TVDSS)",
            "0 (a Sodir publica só MD)",
            fmt(official["Z"].notna().sum()),
            "interpolação na trajetória do perfil",
        ),
        (
            "Problemas registrados com regra, poço e intervalo",
            "0",
            fmt(problems),
            f"{rules} regras em config/regras.yaml; marcam, não corrigem",
        ),
    ]


def fill_block(text: str, block: str, name: str = "numeros") -> str:
    """Troca o que está entre <!-- name:inicio --> e <!-- name:fim --> por block."""
    pattern = re.compile(rf"(<!-- {name}:inicio -->\n).*?(<!-- {name}:fim -->)", re.S)
    if not pattern.search(text):
        raise ValueError(f"marcadores {name} ausentes")
    return pattern.sub(lambda m: m.group(1) + block + m.group(2), text)


def before_after_markdown(rows: list) -> str:
    lines = ["| O quê | Antes | Depois | Como |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | **{c}** | {d} |" for a, b, c, d in rows]
    return "\n".join(lines) + "\n"


def completeness(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Fração de amostras com dado e poços com a curva em mais da metade do perfil."""
    rows = []
    for c in BASIC_CURVES:
        overall, wells = con.execute(
            f"""
            WITH w AS (SELECT poco, avg(({c} IS NOT NULL)::INT) AS f FROM amostra GROUP BY poco)
            SELECT (SELECT avg(({c} IS NOT NULL)::INT) FROM amostra), count(*) FILTER (f >= 0.5)
            FROM w
            """
        ).fetchone()
        rows.append({"curva": c, "amostras_com_dado": overall, "pocos_acima_de_50": wells})
    return pd.DataFrame(rows)


def well_sheet(
    well: pd.Series,
    problems: pd.DataFrame,
    tops: pd.DataFrame,
    cores: pd.DataFrame,
    decisions: list[str],
    titles: dict[str, str],
) -> str:
    """Ficha de um poço em Markdown, escrita para quem vai interpretar."""
    name = well["poco"]
    alias = "" if well["poco_force"] == name else f" (no FORCE: `{well['poco_force']}`)"
    out = [
        f"# {name}{alias}",
        "",
        f"Poço de {well['tipo']}. Nota de qualidade **{well['nota_qualidade']}** de 100. "
        f"Perfil de {fmt(well['md_min_perfil'])} a {fmt(well['md_max_perfil'])} m MD; "
        f"profundidade final oficial {fmt(well['prof_final_md_m'])} m MD, mesa rotativa "
        f"{fmt(well['mesa_rotativa_m'], 1)} m, lâmina d'água {fmt(well['lamina_dagua_m'])} m.",
        "",
        f"Fontes: `{well['arquivo_las']}` e `{well['arquivo_sodir']}` "
        "(hash em `data/raw/manifesto.csv`).",
        "",
        "## Para decidir",
        "",
    ]
    decide = []
    if isinstance(well["achados_conciliacao"], str) and well["achados_conciliacao"]:
        decide += [f"- Cadastro: {a}." for a in well["achados_conciliacao"].split("; ")]
    for r in problems[problems["regra"].isin(NEEDS_DECISION)].itertuples():
        where = f" entre {fmt(r.topo_md)} e {fmt(r.base_md)} m" if pd.notna(r.topo_md) else ""
        hint = f" {HINTS[r.regra]}" if r.regra in HINTS else ""
        decide.append(f"- {sentence(r.nome)} ({r.regra}, {r.curva}{where}): {r.detalhe}.{hint}")
    for column, label in [
        ("situacao_perfil", "o rótulo do perfil"),
        ("situacao_npd2020", "a cópia de 2020"),
    ]:
        md_col = "topo_md_perfil" if column == "situacao_perfil" else "topo_md_npd2020"
        for t in tops[
            tops[column].isin(["divergente", "deslocamento uniforme do poço"])
        ].itertuples():
            delta = getattr(t, md_col) - t.topo_md
            decide.append(
                f"- Topo {t.unidade}: oficial a {fmt(t.topo_md, 1)} m, {label} a "
                f"{fmt(getattr(t, md_col), 1)} m ({fmt(delta, 1)} m; {getattr(t, column)}). "
                "No banco vale o oficial (D04)."
            )
    for c in cores[cores["situacao"] != "com perfil"].itertuples():
        decide.append(
            f"- Testemunho {c.numero} ({fmt(c.topo_md, 1)}–{fmt(c.base_md, 1)} m): {c.situacao}, "
            f"{fmt(100 * c.cobertura_perfil)}% do intervalo com perfil."
        )
    out += decide or ["Nada pendente de decisão."]
    out += ["", "## Falta no dado", ""]
    missing = [
        f"- {sentence(r.nome)} ({r.regra}, {r.curva}): {r.detalhe}."
        for r in problems[problems["regra"].isin(MISSING - {"R13"})].itertuples()
    ]
    no_unit = problems.loc[problems["regra"] == "R13", "curva"].tolist()
    if no_unit:
        missing.append(
            f"- Curvas sem unidade no cabeçalho (R13): {', '.join(no_unit)}. "
            "No banco, a unidade vem do catálogo (`config/mnemonicos.yaml`)."
        )
    out += missing or ["Nenhuma falta registrada."]
    out += ["", "## Já tratado na base", ""]
    done = [f"- {d}: {titles[d].replace('`', '')} ([registro](../decisoes.md))." for d in decisions]
    for r in problems[problems["regra"] == "R12"].itertuples():
        done.append(f"- {r.curva}: {r.detalhe}; virou nulo no banco (D10).")
    out += done or ["Nenhuma decisão específica deste poço."]
    out += [
        "",
        "## Topos oficiais",
        "",
        f"{len(tops)} topos da Sodir; {(tops['situacao_perfil'] == 'igual').sum()} batem com o "
        "perfil, "
        f"{(tops['situacao_perfil'] == 'fora do trecho perfilado').sum()} ficam fora do trecho "
        "perfilado.",
        "",
        f"Testemunhos: {len(cores)}.",
        "",
    ]
    return "\n".join(out)


def sheets(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    wells = con.execute("SELECT * FROM poco ORDER BY nota_qualidade, poco").df()
    problems = con.execute(
        "SELECT p.*, r.nome, r.gravidade FROM problema p JOIN regra r USING (regra)"
    ).df()
    problems["ordem"] = problems["gravidade"].map(SEVERITY_ORDER)
    problems = problems.sort_values(["ordem", "regra", "curva"])
    tops = con.execute("SELECT * FROM topo ORDER BY topo_md").df()
    cores = con.execute("SELECT * FROM testemunho ORDER BY topo_md").df()
    titles = dict(con.execute("SELECT decisao, titulo FROM decisao").fetchall())
    sections = decision_sections(DECISIONS.read_text(encoding="utf-8"))

    SHEETS.mkdir(parents=True, exist_ok=True)
    index = [
        "# Fichas de pendências por poço",
        "",
        "Uma ficha por poço, ordenada pela nota de qualidade (pior primeiro). Gerada por "
        "`uv run python -m pocos.report` a partir do banco final.",
        "",
        "| Poço | Nota | Para decidir | Falta no dado |",
        "|---|---|---|---|",
    ]
    for w in wells.itertuples(index=False):
        row = pd.Series(w._asdict())
        mine = problems[problems["poco"] == w.poco]
        text = well_sheet(
            row,
            mine,
            tops[tops["poco"] == w.poco],
            cores[cores["poco"] == w.poco],
            decisions_for(w.poco, sections),
            titles,
        )
        (SHEETS / f"{well_slug(w.poco)}.md").write_text(text, encoding="utf-8")
        n_decide = text.split("## Para decidir")[1].split("## Falta")[0].count("\n- ")
        n_missing = text.split("## Falta no dado")[1].split("## Já tratado")[0].count("\n- ")
        index.append(
            f"| [{w.poco}]({well_slug(w.poco)}.md) | {w.nota_qualidade} | {n_decide} | "
            f"{n_missing} |"
        )
    (SHEETS / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return wells


CSS = """
:root{--paper:#F6F4EF;--ink:#22252B;--ink2:#5A5D66;--line:#D6D1C5;--brand:#5E3A63;--card:#FFFFFF}
@media (prefers-color-scheme:dark){:root{--paper:#1B1D21;--ink:#ECE9E2;--ink2:#A9ACB3;
--line:#3A3D44;--brand:#C9A6CE;--card:#24272C}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.55 'IBM Plex Sans',system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font:600 30px/1.2 'IBM Plex Sans',sans-serif;margin:0 0 8px}
h2{font-size:21px;margin:44px 0 12px;padding-top:12px;border-top:1px solid var(--line)}
p,li{color:var(--ink)} .muted{color:var(--ink2)}
a{color:var(--brand)}
.prov{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--brand);
padding:14px 18px;margin:20px 0;font-size:15px}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14.5px;background:var(--card)}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{font-weight:600;color:var(--ink2)} td.n{text-align:right;font-variant-numeric:tabular-nums;
font-family:'IBM Plex Mono',monospace;white-space:nowrap}
.big{font:600 15px 'IBM Plex Mono',monospace}
figure{margin:20px 0} figure img{max-width:100%;height:auto;border:1px solid var(--line);
background:#F6F4EF} figcaption{font-size:14px;color:var(--ink2)}
code{font-family:'IBM Plex Mono',monospace;font-size:.92em}
"""


def table(headers: list[str], rows: list[list], numeric: set[int] = frozenset()) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="n">{v}</td>' if i in numeric else f"<td>{v}</td>" for i, v in enumerate(r)
        )
        + "</tr>"
        for r in rows
    )
    return (
        f'<div class="wrap"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def figure(name: str, caption: str) -> str:
    return (
        f'<figure><img src="figuras/{name}.png" alt="{html.escape(caption)}" loading="lazy">'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
    )


def render(con: duckdb.DuckDBPyConnection, wells: pd.DataFrame) -> str:
    e = html.escape
    tops_raw = pd.read_parquet(INTERIM / "topos.parquet")
    rec = json.loads((PROCESSED / "conciliacao.json").read_text(encoding="utf-8"))
    sources = con.execute("SELECT arquivo, licenca, checksum_fonte FROM fonte ORDER BY 1").df()
    snapshots = sources["arquivo"].str.extract(r"_(\d{4}-\d{2}-\d{2})\.csv$")[0].dropna()
    snapshot = ", ".join(sorted(snapshots.unique()))
    ba = before_after(con, tops_raw, rec)
    README.write_text(
        fill_block(README.read_text(encoding="utf-8"), before_after_markdown(ba)),
        encoding="utf-8",
    )
    comp = completeness(con)
    rules = con.execute(
        """
        SELECT r.regra, r.nome, r.gravidade, count(p.id) AS ocorrencias,
               count(DISTINCT p.poco) AS pocos
        FROM regra r LEFT JOIN problema p USING (regra)
        GROUP BY ALL ORDER BY r.regra
        """
    ).fetchall()
    worst = wells.head(10)
    decisions = con.execute("SELECT decisao, titulo FROM decisao ORDER BY 1").fetchall()
    npd, perfil = rec["topos"]["npd_2020 × sodir"], rec["topos"]["perfil_force × sodir"]
    classes = [k for k in TOP_CLASSES if npd.get(k) or perfil.get(k)]
    trivial = name_matches(tops_raw)[1]
    rules_by_well = dict(
        con.execute(
            "SELECT poco, string_agg(DISTINCT regra, ' ' ORDER BY regra) FROM problema GROUP BY 1"
        ).fetchall()
    )

    def code(text: str) -> str:
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", e(text))

    parts = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Relatório de qualidade</title>",
        "<link rel='preconnect' href='https://fonts.googleapis.com'>",
        "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&"
        "family=IBM+Plex+Sans:wght@400;600&display=swap' rel='stylesheet'>",
        f"<style>{CSS}</style></head><body><main>",
        "<h1>Base de poços: relatório de qualidade</h1>",
        f"<p class='muted'>{len(wells)} poços do Mar do Norte norueguês, duas fontes públicas "
        "que não concordam, um banco só.</p>",
        "<div class='prov'><strong>De onde vem o dado.</strong> Perfis e litologia: FORCE 2020 "
        "(Zenodo, DOI 10.5281/zenodo.4351156, CC BY 4.0; dado original do governo norueguês "
        "sob NLOD 2.0). Cadastro, topos e testemunhos oficiais: Sodir FactPages (NLOD 2.0), "
        f"snapshot de {e(str(snapshot))}. Dado público, sem nada proprietário nem sintético. "
        "Cada arquivo tem hash em <code>data/raw/manifesto.csv</code>, e cada linha do banco "
        "aponta para o arquivo de onde veio.</div>",
        "<h2>Antes e depois</h2>",
        "<p>O que mudou entre juntar as fontes direto e passar pela base. O dado medido não foi "
        "alterado; o que muda é o que fica ligado, comparável e marcado.</p>",
        table(
            ["O quê", "Antes", "Depois", "Como"],
            [
                [
                    e(a),
                    f"<span class='big'>{e(b)}</span>",
                    f"<span class='big'>{e(c)}</span>",
                    code(d),
                ]
                for a, b, c, d in ba
            ],
        ),
        "<p class='muted'>Sobre os topos: tirar o ponto final e passar para maiúsculas já casa "
        f"{fmt(trivial)}; o resto depende de grafia norueguesa (Ø, Å), sufixos e unidades "
        "renomeadas.</p>",
        "<h2>Completude das curvas básicas</h2>",
        "<p>Medida, não alterada: a base não preenche curva que falta. A reconstrução de curva "
        "ausente é uma etapa à parte e fica marcada como estimativa.</p>",
        table(
            ["Curva", "Amostras com dado", "Poços com a curva em mais da metade do perfil"],
            [
                [
                    r.curva,
                    fmt(100 * r.amostras_com_dado) + "%",
                    f"{r.pocos_acima_de_50} de {len(wells)}",
                ]
                for r in comp.itertuples()
            ],
            {1, 2},
        ),
        figure("e1_presenca_curvas", "Presença de cada curva por poço (inventário, E1)."),
        "<h2>Problemas por regra</h2>",
        "<p>As regras estão em <code>config/regras.yaml</code>, com gravidade e parâmetros. "
        "Cada uma tem teste nos dois sentidos (pega o caso ruim, deixa passar o bom). A nota do "
        "poço desconta 15 por regra alta, 5 por média e 1 por baixa.</p>",
        table(
            ["Regra", "O que verifica", "Gravidade", "Ocorrências", "Poços"],
            [[r[0], e(r[1]), SEVERITY_LABEL[r[2]], fmt(r[3]), fmt(r[4])] for r in rules],
            {3, 4},
        ),
        figure("e3_matriz_regras", "Regras disparadas por poço, ordenado pela nota."),
        "<h3>Os dez poços com pior nota</h3>",
        table(
            ["Poço", "Nota", "Regras", "Achados de cadastro"],
            [
                [
                    f"<a href='fichas/{well_slug(w.poco)}.md'>{e(w.poco)}</a>",
                    w.nota_qualidade,
                    rules_by_well.get(w.poco, ""),
                    e(w.achados_conciliacao or ""),
                ]
                for w in worst.itertuples()
            ],
            {1},
        ),
        "<p>Uma ficha por poço, escrita para quem interpreta, em "
        "<a href='fichas/README.md'>fichas/</a>.</p>",
        "<h2>Conciliação de topos</h2>",
        "<p>Os topos oficiais de hoje (Sodir) contra a cópia de 2020 que acompanha o FORCE e "
        "contra os rótulos de grupo e formação do próprio perfil. Tolerância de 1 m.</p>",
        table(
            ["Situação", "NPD 2020 × Sodir", "Perfil × Sodir"],
            [[e(k), fmt(npd[k]), fmt(perfil[k])] for k in classes],
            {1, 2},
        ),
        figure("e4_topos", "Diferença de profundidade dos topos entre as fontes."),
        "<h2>Poços e cadastro</h2>",
        f"<p>{rec['pocos_com_achado']} poços têm algum achado contra o cadastro oficial: na "
        "maioria, o perfil passa alguns metros da profundidade final oficial (sondador × "
        "perfilagem, D08); cinco têm referência vertical diferente da mesa rotativa (D07).</p>",
        figure("e2_mapa_pocos", "Posição dos poços: FORCE × Sodir."),
        figure("e2_md_tvd", "Profundidade medida × vertical: poços desviados."),
        "<h2>Decisões</h2>",
        "<p>Quando as fontes discordam, a escolha fica registrada com o que foi visto, o que se "
        "decidiu, por quê e com que evidência (<a href='decisoes.md'>decisoes.md</a>).</p>",
        "<ul>"
        + "".join(f"<li><strong>{d}</strong> — {code(t)}</li>" for d, t in decisions)
        + "</ul>",
        "<h2>Fontes</h2>",
        table(
            ["Arquivo", "Licença", "Checksum publicado"],
            [
                [f"<code>{e(r.arquivo)}</code>", e(r.licenca), e(r.checksum_fonte or "—")]
                for r in sources.itertuples()
            ],
        ),
        "<p class='muted'>Gerado por <code>uv run python -m pocos.report</code> a partir de "
        "<code>data/processed/base_pocos.duckdb</code>.</p>",
        "</main></body></html>",
    ]
    return "\n".join(parts)


def run() -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    wells = sheets(con)
    REPORT.write_text(render(con, wells), encoding="utf-8")
    con.close()
    return {"fichas": len(wells), "relatorio": str(REPORT)}


if __name__ == "__main__":
    print(run())
