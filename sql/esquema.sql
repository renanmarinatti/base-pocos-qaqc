-- Esquema do banco final (E5). Fonte única do dicionário de dados: os comentários abaixo
-- viram docs/dicionario.md (src/pocos/database.py). Mudou o esquema, o dicionário muda
-- junto, sem edição à mão.
--
-- Profundidades em metros, MD a partir da mesa rotativa; TVDSS positiva para baixo do mar.

CREATE TABLE fonte (
    arquivo        VARCHAR PRIMARY KEY,
    id             VARCHAR NOT NULL,
    url            VARCHAR NOT NULL,
    coletado_em    TIMESTAMP NOT NULL,
    bytes          BIGINT NOT NULL,
    sha256         VARCHAR NOT NULL,
    checksum_fonte VARCHAR,
    licenca        VARCHAR NOT NULL
);
COMMENT ON TABLE fonte IS 'Arquivos coletados (manifesto da E1). Toda linha das outras tabelas aponta para um deles.';
COMMENT ON COLUMN fonte.arquivo IS 'Caminho relativo a data/raw/; chave.';
COMMENT ON COLUMN fonte.id IS 'Identificador da fonte em config/fontes.yaml.';
COMMENT ON COLUMN fonte.url IS 'De onde o arquivo foi baixado.';
COMMENT ON COLUMN fonte.coletado_em IS 'Data e hora da coleta.';
COMMENT ON COLUMN fonte.bytes IS 'Tamanho do arquivo.';
COMMENT ON COLUMN fonte.sha256 IS 'Hash do arquivo, para provar que é o mesmo que veio da fonte.';
COMMENT ON COLUMN fonte.checksum_fonte IS 'Hash publicado pela fonte e conferido na coleta (o Zenodo publica md5).';
COMMENT ON COLUMN fonte.licenca IS 'Licença de uso declarada.';

CREATE TABLE poco (
    poco                 VARCHAR PRIMARY KEY,
    poco_force           VARCHAR NOT NULL UNIQUE,
    tipo                 VARCHAR NOT NULL,
    mesa_rotativa_m      DOUBLE,
    lamina_dagua_m       DOUBLE,
    prof_final_md_m      DOUBLE,
    prof_final_tvd_m     DOUBLE,
    inclinacao_max_graus DOUBLE,
    x_utm31_ed50         DOUBLE,
    y_utm31_ed50         DOUBLE,
    lat_wgs84            DOUBLE,
    lon_wgs84            DOUBLE,
    md_min_perfil        DOUBLE NOT NULL,
    md_max_perfil        DOUBLE NOT NULL,
    desvio_max_m         DOUBLE,
    nota_qualidade       INTEGER NOT NULL CHECK (nota_qualidade BETWEEN 0 AND 100),
    achados_conciliacao  VARCHAR,
    arquivo_las          VARCHAR NOT NULL REFERENCES fonte (arquivo),
    arquivo_sodir        VARCHAR NOT NULL REFERENCES fonte (arquivo)
);
COMMENT ON TABLE poco IS 'Um registro por ramal (wellbore). Cadastro da Sodir; perfil do FORCE.';
COMMENT ON COLUMN poco.poco IS 'Nome oficial do ramal na Sodir (ex.: 16/1-6 A); chave.';
COMMENT ON COLUMN poco.poco_force IS 'Nome do ramal no arquivo do FORCE; difere do oficial em 2 poços (decisões D01, D02).';
COMMENT ON COLUMN poco.tipo IS 'Exploração ou desenvolvimento (Sodir).';
COMMENT ON COLUMN poco.mesa_rotativa_m IS 'Elevação da mesa rotativa (RKB) sobre o nível do mar; referência do MD (Sodir).';
COMMENT ON COLUMN poco.lamina_dagua_m IS 'Lâmina d''água (Sodir).';
COMMENT ON COLUMN poco.prof_final_md_m IS 'Profundidade final em MD (Sodir; em geral a do sondador).';
COMMENT ON COLUMN poco.prof_final_tvd_m IS 'Profundidade final vertical (Sodir).';
COMMENT ON COLUMN poco.inclinacao_max_graus IS 'Inclinação máxima do ramal (Sodir).';
COMMENT ON COLUMN poco.x_utm31_ed50 IS 'Coordenada E da cabeça do poço, UTM 31N sobre ED50 (EPSG:23031), convertida da Sodir.';
COMMENT ON COLUMN poco.y_utm31_ed50 IS 'Coordenada N da cabeça do poço, UTM 31N sobre ED50 (EPSG:23031).';
COMMENT ON COLUMN poco.lat_wgs84 IS 'Latitude da cabeça do poço em WGS84 (EPSG:4326).';
COMMENT ON COLUMN poco.lon_wgs84 IS 'Longitude da cabeça do poço em WGS84 (EPSG:4326).';
COMMENT ON COLUMN poco.md_min_perfil IS 'MD da primeira amostra de perfil.';
COMMENT ON COLUMN poco.md_max_perfil IS 'MD da última amostra de perfil.';
COMMENT ON COLUMN poco.desvio_max_m IS 'Maior valor de MD − TVD no perfil, descontada a mesa rotativa; acima de 50 m, poço desviado.';
COMMENT ON COLUMN poco.nota_qualidade IS 'Nota de 0 a 100: 100 menos 15, 5 ou 1 por regra alta, média ou baixa disparada (E3).';
COMMENT ON COLUMN poco.achados_conciliacao IS 'O que a conciliação com a Sodir encontrou no poço (E4); vazio se nada.';
COMMENT ON COLUMN poco.arquivo_las IS 'Arquivo de perfil de origem (dentro do zip do FORCE).';
COMMENT ON COLUMN poco.arquivo_sodir IS 'Tabela da Sodir de onde vem o cadastro.';

CREATE TABLE curva (
    curva       VARCHAR PRIMARY KEY,
    unidade     VARCHAR NOT NULL,
    faixa_min   DOUBLE,
    faixa_max   DOUBLE,
    descricao   VARCHAR NOT NULL
);
COMMENT ON TABLE curva IS 'Catálogo de curvas (config/mnemonicos.yaml): nome canônico, unidade e faixa física plausível.';
COMMENT ON COLUMN curva.curva IS 'Mnemônico canônico; é o nome da coluna em amostra.';
COMMENT ON COLUMN curva.unidade IS 'Unidade da curva.';
COMMENT ON COLUMN curva.faixa_min IS 'Menor valor fisicamente plausível (regra R02).';
COMMENT ON COLUMN curva.faixa_max IS 'Maior valor fisicamente plausível (regra R02).';
COMMENT ON COLUMN curva.descricao IS 'O que a curva mede.';

CREATE TABLE amostra (
    poco           VARCHAR NOT NULL REFERENCES poco (poco),
    md             DOUBLE NOT NULL,
    tvdss          DOUBLE,
    x_utm31_ed50   DOUBLE,
    y_utm31_ed50   DOUBLE,
    GR DOUBLE, SGR DOUBLE, RHOB DOUBLE, DRHO DOUBLE, NPHI DOUBLE, PEF DOUBLE,
    DTC DOUBLE, DTS DOUBLE, RDEP DOUBLE, RMED DOUBLE, RSHA DOUBLE, RXO DOUBLE, RMIC DOUBLE,
    SP DOUBLE, CALI DOUBLE, DCAL DOUBLE, BS DOUBLE, ROP DOUBLE, ROPA DOUBLE,
    litologia_codigo INTEGER,
    confianca      DOUBLE,
    rhob_arrombado BOOLEAN NOT NULL,
    pef_baritina   BOOLEAN NOT NULL,
    arquivo        VARCHAR NOT NULL,
    PRIMARY KEY (poco, md)
);
COMMENT ON TABLE amostra IS 'Uma linha por profundidade de perfil (passo 0,152 m). Curvas com nome canônico; nulo como NULL. MUDWEIGHT fica fora (D09); −999 vira NULL (D10).';
COMMENT ON COLUMN amostra.poco IS 'Ramal (poco.poco).';
COMMENT ON COLUMN amostra.md IS 'Profundidade medida ao longo do poço, a partir da mesa rotativa (m).';
COMMENT ON COLUMN amostra.tvdss IS 'Profundidade vertical abaixo do nível do mar (m), do Z_LOC do FORCE com o sinal invertido.';
COMMENT ON COLUMN amostra.x_utm31_ed50 IS 'Coordenada E da amostra (X_LOC do FORCE).';
COMMENT ON COLUMN amostra.y_utm31_ed50 IS 'Coordenada N da amostra (Y_LOC do FORCE).';
COMMENT ON COLUMN amostra.GR IS 'Raios gama naturais (gAPI). Demais curvas: ver tabela curva.';
COMMENT ON COLUMN amostra.litologia_codigo IS 'Litologia interpretada (código FORCE; nome em litologia_intervalo).';
COMMENT ON COLUMN amostra.confianca IS 'Confiança da interpretação: 1 alta, 2 média, 3 baixa.';
COMMENT ON COLUMN amostra.rhob_arrombado IS 'Verdadeiro se o RHOB da amostra está em trecho arrombado ou com |DRHO| alto (regra R08). O valor é mantido.';
COMMENT ON COLUMN amostra.pef_baritina IS 'Verdadeiro se o PEF passa de 10, efeito da baritina da lama (regra R14, decisão D11). O valor é mantido.';
COMMENT ON COLUMN amostra.arquivo IS 'Arquivo LAS de origem.';

CREATE TABLE litologia_intervalo (
    poco       VARCHAR NOT NULL REFERENCES poco (poco),
    topo_md    DOUBLE NOT NULL,
    base_md    DOUBLE NOT NULL CHECK (base_md > topo_md),
    codigo     INTEGER NOT NULL,
    litologia  VARCHAR NOT NULL,
    confianca  DOUBLE,
    amostras   INTEGER NOT NULL,
    PRIMARY KEY (poco, topo_md)
);
COMMENT ON TABLE litologia_intervalo IS 'Litologia interpretada como intervalos topo–base, quebrados onde o perfil tem buraco.';
COMMENT ON COLUMN litologia_intervalo.poco IS 'Ramal.';
COMMENT ON COLUMN litologia_intervalo.topo_md IS 'Topo do intervalo (MD, m).';
COMMENT ON COLUMN litologia_intervalo.base_md IS 'Base do intervalo (MD, m): topo da amostra seguinte, quando contígua.';
COMMENT ON COLUMN litologia_intervalo.codigo IS 'Código FORCE (config/litologia.yaml).';
COMMENT ON COLUMN litologia_intervalo.litologia IS 'Nome da litologia em português.';
COMMENT ON COLUMN litologia_intervalo.confianca IS 'Mediana da confiança das amostras do intervalo.';
COMMENT ON COLUMN litologia_intervalo.amostras IS 'Quantas amostras formam o intervalo.';

CREATE TABLE topo (
    poco              VARCHAR NOT NULL REFERENCES poco (poco),
    nivel             VARCHAR NOT NULL,
    unidade           VARCHAR NOT NULL,
    unidade_base      VARCHAR NOT NULL,
    ocorrencia        INTEGER NOT NULL,
    topo_md           DOUBLE NOT NULL,
    base_md           DOUBLE,
    topo_md_npd2020   DOUBLE,
    situacao_npd2020  VARCHAR,
    topo_md_perfil    DOUBLE,
    situacao_perfil   VARCHAR,
    arquivo           VARCHAR NOT NULL REFERENCES fonte (arquivo),
    PRIMARY KEY (poco, unidade_base, ocorrencia)
);
COMMENT ON TABLE topo IS 'Topos litoestratigráficos oficiais (Sodir, referência pela D04), com a comparação contra a cópia de 2020 e os rótulos do perfil (E4).';
COMMENT ON COLUMN topo.poco IS 'Ramal.';
COMMENT ON COLUMN topo.nivel IS 'GRUPO ou FORMACAO.';
COMMENT ON COLUMN topo.unidade IS 'Nome oficial da unidade, como a Sodir escreve.';
COMMENT ON COLUMN topo.unidade_base IS 'Nome-base usado para casar as versões (D03).';
COMMENT ON COLUMN topo.ocorrencia IS 'Ordem da ocorrência da unidade no poço (1, 2…): unidades podem se repetir.';
COMMENT ON COLUMN topo.topo_md IS 'Topo oficial (MD, m, a partir da mesa rotativa).';
COMMENT ON COLUMN topo.base_md IS 'Base oficial (MD, m).';
COMMENT ON COLUMN topo.topo_md_npd2020 IS 'O mesmo topo na cópia do NPD de 2020, se existir.';
COMMENT ON COLUMN topo.situacao_npd2020 IS 'igual, divergente, deslocamento uniforme do poço ou só na Sodir.';
COMMENT ON COLUMN topo.topo_md_perfil IS 'Início do trecho com o rótulo dessa unidade no perfil do FORCE, se existir.';
COMMENT ON COLUMN topo.situacao_perfil IS 'igual, divergente, deslocamento uniforme do poço, fora do trecho perfilado ou só na Sodir.';
COMMENT ON COLUMN topo.arquivo IS 'Tabela da Sodir de origem.';

CREATE TABLE testemunho (
    poco               VARCHAR NOT NULL REFERENCES poco (poco),
    numero             INTEGER NOT NULL,
    topo_md            DOUBLE NOT NULL,
    base_md            DOUBLE NOT NULL,
    unidade_original   VARCHAR NOT NULL,
    cobertura_perfil   DOUBLE NOT NULL,
    litologia_no_perfil VARCHAR,
    situacao           VARCHAR NOT NULL,
    arquivo            VARCHAR NOT NULL REFERENCES fonte (arquivo),
    PRIMARY KEY (poco, numero)
);
COMMENT ON TABLE testemunho IS 'Intervalos testemunhados (Sodir), em metros, conferidos contra o perfil (E4).';
COMMENT ON COLUMN testemunho.poco IS 'Ramal.';
COMMENT ON COLUMN testemunho.numero IS 'Número do testemunho no poço.';
COMMENT ON COLUMN testemunho.topo_md IS 'Topo do intervalo testemunhado (MD, m).';
COMMENT ON COLUMN testemunho.base_md IS 'Base do intervalo testemunhado (MD, m).';
COMMENT ON COLUMN testemunho.unidade_original IS 'Unidade em que a Sodir publica (m ou ft); ft foi convertido.';
COMMENT ON COLUMN testemunho.cobertura_perfil IS 'Fração do intervalo com amostra de perfil (0 a 1).';
COMMENT ON COLUMN testemunho.litologia_no_perfil IS 'Litologia dominante do perfil dentro do intervalo.';
COMMENT ON COLUMN testemunho.situacao IS 'com perfil, perfil parcial, sem perfil ou abaixo da profundidade final.';
COMMENT ON COLUMN testemunho.arquivo IS 'Tabela da Sodir de origem.';

CREATE TABLE regra (
    regra       VARCHAR PRIMARY KEY,
    nome        VARCHAR NOT NULL,
    gravidade   VARCHAR NOT NULL CHECK (gravidade IN ('alta', 'media', 'baixa')),
    descricao   VARCHAR NOT NULL
);
COMMENT ON TABLE regra IS 'Catálogo de regras de qualidade (config/regras.yaml).';
COMMENT ON COLUMN regra.regra IS 'Identificador estável (R01…).';
COMMENT ON COLUMN regra.nome IS 'Nome curto.';
COMMENT ON COLUMN regra.gravidade IS 'alta: impede o uso; media: exige cuidado; baixa: informa.';
COMMENT ON COLUMN regra.descricao IS 'O que a regra verifica.';

CREATE TABLE problema (
    id        INTEGER PRIMARY KEY,
    regra     VARCHAR NOT NULL REFERENCES regra (regra),
    poco      VARCHAR NOT NULL REFERENCES poco (poco),
    curva     VARCHAR,
    topo_md   DOUBLE,
    base_md   DOUBLE,
    amostras  INTEGER,
    detalhe   VARCHAR NOT NULL
);
COMMENT ON TABLE problema IS 'Registro de problemas de qualidade (E3): o que cada regra marcou, onde.';
COMMENT ON COLUMN problema.id IS 'Número do problema.';
COMMENT ON COLUMN problema.regra IS 'Regra que marcou.';
COMMENT ON COLUMN problema.poco IS 'Ramal.';
COMMENT ON COLUMN problema.curva IS 'Curva ou unidade envolvida, se houver.';
COMMENT ON COLUMN problema.topo_md IS 'Início do trecho afetado (MD, m), se houver.';
COMMENT ON COLUMN problema.base_md IS 'Fim do trecho afetado (MD, m), se houver.';
COMMENT ON COLUMN problema.amostras IS 'Quantas amostras afetadas, quando se aplica.';
COMMENT ON COLUMN problema.detalhe IS 'Descrição legível do problema.';

CREATE TABLE decisao (
    decisao  VARCHAR PRIMARY KEY,
    titulo   VARCHAR NOT NULL
);
COMMENT ON TABLE decisao IS 'Decisões de tratamento (docs/decisoes.md): quando as fontes discordam, o que se escolheu.';
COMMENT ON COLUMN decisao.decisao IS 'Identificador (D01…).';
COMMENT ON COLUMN decisao.titulo IS 'Título da decisão; o texto completo, com evidência, está em docs/decisoes.md.';
