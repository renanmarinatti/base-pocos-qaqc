-- Consultas de exemplo sobre o banco final. Cada bloco começa com "-- name:" e um título;
-- src/pocos/queries.py roda todas e grava o resultado em docs/consultas.md.

-- name: Os 10 poços com pior nota de qualidade, e o que pesou
SELECT p.poco, p.nota_qualidade AS nota,
       string_agg(DISTINCT pr.regra || ' ' || r.gravidade, ', ' ORDER BY pr.regra || ' ' || r.gravidade) AS regras
FROM poco p
JOIN problema pr USING (poco)
JOIN regra r USING (regra)
GROUP BY p.poco, p.nota_qualidade
ORDER BY nota, p.poco
LIMIT 10;

-- name: Quanto do RHOB é utilizável, por poço (fora de trecho arrombado e com DRHO normal)
SELECT poco,
       count(RHOB) AS amostras_com_rhob,
       round(100.0 * count(RHOB) FILTER (WHERE NOT rhob_arrombado) / count(RHOB), 1) AS pct_utilizavel
FROM amostra
WHERE RHOB IS NOT NULL
GROUP BY poco
ORDER BY pct_utilizavel
LIMIT 10;

-- name: Topos que a Sodir reinterpretou desde a cópia de 2020
SELECT poco, unidade, topo_md_npd2020 AS md_2020, topo_md AS md_hoje,
       topo_md - topo_md_npd2020 AS mudanca_m
FROM topo
WHERE situacao_npd2020 = 'divergente'
ORDER BY abs(topo_md - topo_md_npd2020) DESC
LIMIT 10;

-- name: Espessura das formações mais atravessadas (topo e base oficiais)
SELECT unidade, count(DISTINCT poco) AS pocos,
       round(median(base_md - topo_md), 0) AS espessura_mediana_m,
       round(max(base_md - topo_md), 0) AS espessura_max_m
FROM topo
WHERE nivel = 'FORMACAO' AND base_md IS NOT NULL
GROUP BY unidade
ORDER BY pocos DESC
LIMIT 10;

-- name: Litologia (pelo perfil) dentro dos intervalos testemunhados
SELECT l.litologia,
       round(sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md)), 0) AS metros,
       round(100.0 * sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md))
             / sum(sum(least(l.base_md, t.base_md) - greatest(l.topo_md, t.topo_md))) OVER (), 1) AS pct
FROM testemunho t
JOIN litologia_intervalo l
  ON l.poco = t.poco AND l.base_md > t.topo_md AND l.topo_md < t.base_md
GROUP BY l.litologia
ORDER BY metros DESC;

-- name: Completude das curvas básicas no trecho perfilado (% de amostras com dado)
SELECT round(100.0 * count(GR) / count(*), 1) AS gr,
       round(100.0 * count(RHOB) / count(*), 1) AS rhob,
       round(100.0 * count(NPHI) / count(*), 1) AS nphi,
       round(100.0 * count(DTC) / count(*), 1) AS dtc,
       round(100.0 * count(RDEP) / count(*), 1) AS rdep,
       round(100.0 * count(tvdss) / count(*), 1) AS trajetoria
FROM amostra;
