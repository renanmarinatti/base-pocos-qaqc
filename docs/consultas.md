# Consultas de exemplo

Geradas de `sql/consultas.sql` sobre o banco final (`uv run python -m pocos.queries`).

## Os 10 poços com pior nota de qualidade, e o que pesou

```sql
SELECT p.poco, p.nota_qualidade AS nota,
       string_agg(DISTINCT pr.regra || ' ' || r.gravidade, ', ' ORDER BY pr.regra || ' ' || r.gravidade) AS regras
FROM poco p
JOIN problema pr USING (poco)
JOIN regra r USING (regra)
GROUP BY p.poco, p.nota_qualidade
ORDER BY nota, p.poco
LIMIT 10;
```

| poco | nota | regras |
|---|---|---|
| 34/11-2 S | 54 | R02 alta, R07 media, R12 alta, R13 baixa, R14 media, R15 media |
| 35/8-4 | 59 | R01 media, R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 16/10-2 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/2-14 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/3-1 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/5-3 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/5-4 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/7-2 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/8-7 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |
| 25/9-1 | 64 | R02 alta, R07 media, R08 media, R13 baixa, R14 media, R15 media |

## Quanto do RHOB é utilizável, por poço (fora de trecho arrombado e com DRHO normal)

```sql
SELECT poco,
       count(RHOB) AS amostras_com_rhob,
       round(100.0 * count(RHOB) FILTER (WHERE NOT rhob_arrombado) / count(RHOB), 1) AS pct_utilizavel
FROM amostra
WHERE RHOB IS NOT NULL
GROUP BY poco
ORDER BY pct_utilizavel
LIMIT 10;
```

| poco | amostras_com_rhob | pct_utilizavel |
|---|---|---|
| 36/7-3 | 10089 | 0.0 |
| 25/7-2 | 28926 | 33.7 |
| 16/11-1 S | 3573 | 35.7 |
| 16/4-1 | 15914 | 40.9 |
| 34/10-33 | 23923 | 41.9 |
| 16/7-4 | 17196 | 48.3 |
| 25/2-7 | 25643 | 50.7 |
| 34/8-1 | 17890 | 52.1 |
| 15/9-15 | 17672 | 55.1 |
| 25/2-14 | 16275 | 56.5 |

## Topos que a Sodir reinterpretou desde a cópia de 2020

```sql
SELECT poco, unidade, topo_md_npd2020 AS md_2020, topo_md AS md_hoje,
       topo_md - topo_md_npd2020 AS mudanca_m
FROM topo
WHERE situacao_npd2020 = 'divergente'
ORDER BY abs(topo_md - topo_md_npd2020) DESC
LIMIT 10;
```

| poco | unidade | md_2020 | md_hoje | mudanca_m |
|---|---|---|---|---|
| 35/8-6 S | HORDALAND GP | 1372.0 | 963.0 | -409.0 |
| 25/8-5 S | LISTA FM | 2420.0 | 2068.0 | -352.0 |
| 35/11-15 S | HEATHER FM | 3137.0 | 2829.0 | -308.0 |
| 25/4-5 | LISTA FM | 2347.0 | 2090.0 | -257.0 |
| 30/3-5 S | UTSIRA FM | 1027.0 | 807.0 | -220.0 |
| 25/2-13 | UTSIRA FM | 262.0 | 437.0 | 175.0 |
| 25/5-1 | UTSIRA FM | 612.0 | 444.0 | -168.0 |
| 25/5-4 | UTSIRA FM | 294.0 | 453.0 | 159.0 |
| 34/10-35 | UTSIRA FM | 753.0 | 910.0 | 157.0 |
| 34/10-16 R | UTSIRA FM | 858.0 | 1002.0 | 144.0 |

## Espessura das formações mais atravessadas (topo e base oficiais)

```sql
SELECT unidade, count(DISTINCT poco) AS pocos,
       round(median(base_md - topo_md), 0) AS espessura_mediana_m,
       round(max(base_md - topo_md), 0) AS espessura_max_m
FROM topo
WHERE nivel = 'FORMACAO' AND base_md IS NOT NULL
GROUP BY unidade
ORDER BY pocos DESC
LIMIT 10;
```

| unidade | pocos | espessura_mediana_m | espessura_max_m |
|---|---|---|---|
| LISTA FM | 116 | 100.0 | 483.0 |
| BALDER FM | 116 | 47.0 | 144.0 |
| SELE FM | 100 | 42.0 | 399.0 |
| DRAUPNE FM | 90 | 27.0 | 239.0 |
| UTSIRA FM | 87 | 98.0 | 630.0 |
| HEATHER FM | 84 | 54.0 | 730.0 |
| VÅLE FM | 66 | 22.0 | 143.0 |
| RØDBY FM | 64 | 37.0 | 291.0 |
| ÅSGARD FM | 54 | 34.0 | 374.0 |
| DRAKE FM | 54 | 72.0 | 223.0 |

## Litologia (pelo perfil) dentro dos intervalos testemunhados

```sql
SELECT l.litologia,
       round(sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md)), 0) AS metros,
       round(100.0 * sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md))
             / sum(sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md))) OVER (), 1) AS pct
FROM testemunho t
JOIN litologia_intervalo l
  ON l.poco = t.poco AND l.base_md > t.topo_md AND l.topo_md < t.base_md
GROUP BY l.litologia
ORDER BY metros DESC;
```

| litologia | metros | pct |
|---|---|---|
| arenito | 3710.0 | 44.3 |
| arenito/folhelho | 2359.0 | 28.2 |
| folhelho | 1862.0 | 22.2 |
| calcário | 222.0 | 2.7 |
| carvão | 117.0 | 1.4 |
| marga | 73.0 | 0.9 |
| giz | 21.0 | 0.3 |
| dolomito | 10.0 | 0.1 |
| embasamento | 0.0 | 0.0 |

## Completude das curvas básicas no trecho perfilado (% de amostras com dado)

```sql
SELECT round(100.0 * count(GR) / count(*), 1) AS gr,
       round(100.0 * count(RHOB) / count(*), 1) AS rhob,
       round(100.0 * count(NPHI) / count(*), 1) AS nphi,
       round(100.0 * count(DTC) / count(*), 1) AS dtc,
       round(100.0 * count(RDEP) / count(*), 1) AS rdep,
       round(100.0 * count(tvdss) / count(*), 1) AS trajetoria
FROM amostra;
```

| gr | rhob | nphi | dtc | rdep | trajetoria |
|---|---|---|---|---|---|
| 98.3 | 59.7 | 44.2 | 76.7 | 94.9 | 95.0 |
