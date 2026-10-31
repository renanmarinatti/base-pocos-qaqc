# Dicionário de dados

Gerado de `sql/esquema.sql` pelo próprio banco (`uv run python -m pocos.database`). Não editar à mão.

## `fonte`

Arquivos coletados (manifesto da E1). Toda linha das outras tabelas aponta para um deles.

Linhas: 10

- Chave: `arquivo`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `arquivo` | VARCHAR | não | Caminho relativo a data/raw/; chave. |
| `id` | VARCHAR | não | Identificador da fonte em config/fontes.yaml. |
| `url` | VARCHAR | não | De onde o arquivo foi baixado. |
| `coletado_em` | TIMESTAMP | não | Data e hora da coleta. |
| `bytes` | BIGINT | não | Tamanho do arquivo. |
| `sha256` | VARCHAR | não | Hash do arquivo, para provar que é o mesmo que veio da fonte. |
| `checksum_fonte` | VARCHAR | sim | Hash publicado pela fonte e conferido na coleta (o Zenodo publica md5). |
| `licenca` | VARCHAR | não | Licença de uso declarada. |

## `poco`

Um registro por ramal (wellbore). Cadastro da Sodir; perfil do FORCE.

Linhas: 118

- Chave: `poco`
- `arquivo_las` → `fonte`
- `arquivo_sodir` → `fonte`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `poco` | VARCHAR | não | Nome oficial do ramal na Sodir (ex.: 16/1-6 A); chave. |
| `poco_force` | VARCHAR | não | Nome do ramal no arquivo do FORCE; difere do oficial em 2 poços (decisões D01, D02). |
| `tipo` | VARCHAR | não | Exploração ou desenvolvimento (Sodir). |
| `mesa_rotativa_m` | DOUBLE | sim | Elevação da mesa rotativa (RKB) sobre o nível do mar; referência do MD (Sodir). |
| `lamina_dagua_m` | DOUBLE | sim | Lâmina d'água (Sodir). |
| `prof_final_md_m` | DOUBLE | sim | Profundidade final em MD (Sodir; em geral a do sondador). |
| `prof_final_tvd_m` | DOUBLE | sim | Profundidade final vertical (Sodir). |
| `inclinacao_max_graus` | DOUBLE | sim | Inclinação máxima do ramal (Sodir). |
| `x_utm31_ed50` | DOUBLE | sim | Coordenada E da cabeça do poço, UTM 31N sobre ED50 (EPSG:23031), convertida da Sodir. |
| `y_utm31_ed50` | DOUBLE | sim | Coordenada N da cabeça do poço, UTM 31N sobre ED50 (EPSG:23031). |
| `lat_wgs84` | DOUBLE | sim | Latitude da cabeça do poço em WGS84 (EPSG:4326). |
| `lon_wgs84` | DOUBLE | sim | Longitude da cabeça do poço em WGS84 (EPSG:4326). |
| `md_min_perfil` | DOUBLE | não | MD da primeira amostra de perfil. |
| `md_max_perfil` | DOUBLE | não | MD da última amostra de perfil. |
| `desvio_max_m` | DOUBLE | sim | Maior valor de MD − TVD no perfil, descontada a mesa rotativa; acima de 50 m, poço desviado. |
| `nota_qualidade` | INTEGER | não | Nota de 0 a 100: 100 menos 15, 5 ou 1 por regra alta, média ou baixa disparada (E3). |
| `achados_conciliacao` | VARCHAR | sim | O que a conciliação com a Sodir encontrou no poço (E4); vazio se nada. |
| `arquivo_las` | VARCHAR | não | Arquivo de perfil de origem (dentro do zip do FORCE). |
| `arquivo_sodir` | VARCHAR | não | Tabela da Sodir de onde vem o cadastro. |

## `curva`

Catálogo de curvas (config/mnemonicos.yaml): nome canônico, unidade e faixa física plausível.

Linhas: 19

- Chave: `curva`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `curva` | VARCHAR | não | Mnemônico canônico; é o nome da coluna em amostra. |
| `unidade` | VARCHAR | não | Unidade da curva. |
| `faixa_min` | DOUBLE | sim | Menor valor fisicamente plausível (regra R02). |
| `faixa_max` | DOUBLE | sim | Maior valor fisicamente plausível (regra R02). |
| `descricao` | VARCHAR | não | O que a curva mede. |

## `amostra`

Uma linha por profundidade de perfil (passo 0,152 m). Curvas com nome canônico; nulo como NULL. MUDWEIGHT fica fora (D09); −999 vira NULL (D10).

Linhas: 2.337.639

- `poco` → `poco`
- Chave: `poco, md`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `poco` | VARCHAR | não | Ramal (poco.poco). |
| `md` | DOUBLE | não | Profundidade medida ao longo do poço, a partir da mesa rotativa (m). |
| `tvdss` | DOUBLE | sim | Profundidade vertical abaixo do nível do mar (m), do Z_LOC do FORCE com o sinal invertido. |
| `x_utm31_ed50` | DOUBLE | sim | Coordenada E da amostra (X_LOC do FORCE). |
| `y_utm31_ed50` | DOUBLE | sim | Coordenada N da amostra (Y_LOC do FORCE). |
| `GR` | DOUBLE | sim | Raios gama naturais (gAPI). Demais curvas: ver tabela curva. |
| `SGR` | DOUBLE | sim |  |
| `RHOB` | DOUBLE | sim |  |
| `DRHO` | DOUBLE | sim |  |
| `NPHI` | DOUBLE | sim |  |
| `PEF` | DOUBLE | sim |  |
| `DTC` | DOUBLE | sim |  |
| `DTS` | DOUBLE | sim |  |
| `RDEP` | DOUBLE | sim |  |
| `RMED` | DOUBLE | sim |  |
| `RSHA` | DOUBLE | sim |  |
| `RXO` | DOUBLE | sim |  |
| `RMIC` | DOUBLE | sim |  |
| `SP` | DOUBLE | sim |  |
| `CALI` | DOUBLE | sim |  |
| `DCAL` | DOUBLE | sim |  |
| `BS` | DOUBLE | sim |  |
| `ROP` | DOUBLE | sim |  |
| `ROPA` | DOUBLE | sim |  |
| `litologia_codigo` | INTEGER | sim | Litologia interpretada (código FORCE; nome em litologia_intervalo). |
| `confianca` | DOUBLE | sim | Confiança da interpretação: 1 alta, 2 média, 3 baixa. |
| `rhob_arrombado` | BOOLEAN | não | Verdadeiro se o RHOB da amostra está em trecho arrombado ou com |DRHO| alto (regra R08). O valor é mantido. |
| `pef_baritina` | BOOLEAN | não | Verdadeiro se o PEF passa de 10, efeito da baritina da lama (regra R14, decisão D11). O valor é mantido. |
| `arquivo` | VARCHAR | não | Arquivo LAS de origem. |

## `litologia_intervalo`

Litologia interpretada como intervalos topo–base, quebrados onde o perfil tem buraco.

Linhas: 40.295

- `poco` → `poco`
- Chave: `poco, topo_md`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `poco` | VARCHAR | não | Ramal. |
| `topo_md` | DOUBLE | não | Topo do intervalo (MD, m). |
| `base_md` | DOUBLE | não | Base do intervalo (MD, m): topo da amostra seguinte, quando contígua. |
| `codigo` | INTEGER | não | Código FORCE (config/litologia.yaml). |
| `litologia` | VARCHAR | não | Nome da litologia em português. |
| `confianca` | DOUBLE | sim | Mediana da confiança das amostras do intervalo. |
| `amostras` | INTEGER | não | Quantas amostras formam o intervalo. |

## `topo`

Topos litoestratigráficos oficiais (Sodir, referência pela D04), com a comparação contra a cópia de 2020 e os rótulos do perfil (E4).

Linhas: 2.799

- `poco` → `poco`
- `arquivo` → `fonte`
- Chave: `poco, unidade_base, ocorrencia`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `poco` | VARCHAR | não | Ramal. |
| `nivel` | VARCHAR | não | GRUPO ou FORMACAO. |
| `unidade` | VARCHAR | não | Nome oficial da unidade, como a Sodir escreve. |
| `unidade_base` | VARCHAR | não | Nome-base usado para casar as versões (D03). |
| `ocorrencia` | INTEGER | não | Ordem da ocorrência da unidade no poço (1, 2…): unidades podem se repetir. |
| `topo_md` | DOUBLE | não | Topo oficial (MD, m, a partir da mesa rotativa). |
| `base_md` | DOUBLE | sim | Base oficial (MD, m). |
| `topo_md_npd2020` | DOUBLE | sim | O mesmo topo na cópia do NPD de 2020, se existir. |
| `situacao_npd2020` | VARCHAR | sim | igual, divergente, deslocamento uniforme do poço ou só na Sodir. |
| `topo_md_perfil` | DOUBLE | sim | Início do trecho com o rótulo dessa unidade no perfil do FORCE, se existir. |
| `situacao_perfil` | VARCHAR | sim | igual, divergente, deslocamento uniforme do poço, fora do trecho perfilado ou só na Sodir. |
| `arquivo` | VARCHAR | não | Tabela da Sodir de origem. |

## `testemunho`

Intervalos testemunhados (Sodir), em metros, conferidos contra o perfil (E4).

Linhas: 501

- `poco` → `poco`
- `arquivo` → `fonte`
- Chave: `poco, numero`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `poco` | VARCHAR | não | Ramal. |
| `numero` | INTEGER | não | Número do testemunho no poço. |
| `topo_md` | DOUBLE | não | Topo do intervalo testemunhado (MD, m). |
| `base_md` | DOUBLE | não | Base do intervalo testemunhado (MD, m). |
| `unidade_original` | VARCHAR | não | Unidade em que a Sodir publica (m ou ft); ft foi convertido. |
| `cobertura_perfil` | DOUBLE | não | Fração do intervalo com amostra de perfil (0 a 1). |
| `litologia_no_perfil` | VARCHAR | sim | Litologia dominante do perfil dentro do intervalo. |
| `situacao` | VARCHAR | não | com perfil, perfil parcial, sem perfil ou abaixo da profundidade final. |
| `arquivo` | VARCHAR | não | Tabela da Sodir de origem. |

## `regra`

Catálogo de regras de qualidade (config/regras.yaml).

Linhas: 15

- Chave: `regra`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `regra` | VARCHAR | não | Identificador estável (R01…). |
| `nome` | VARCHAR | não | Nome curto. |
| `gravidade` | VARCHAR | não | alta: impede o uso; media: exige cuidado; baixa: informa. |
| `descricao` | VARCHAR | não | O que a regra verifica. |

## `problema`

Registro de problemas de qualidade (E3): o que cada regra marcou, onde.

Linhas: 951

- Chave: `id`
- `regra` → `regra`
- `poco` → `poco`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INTEGER | não | Número do problema. |
| `regra` | VARCHAR | não | Regra que marcou. |
| `poco` | VARCHAR | não | Ramal. |
| `curva` | VARCHAR | sim | Curva ou unidade envolvida, se houver. |
| `topo_md` | DOUBLE | sim | Início do trecho afetado (MD, m), se houver. |
| `base_md` | DOUBLE | sim | Fim do trecho afetado (MD, m), se houver. |
| `amostras` | INTEGER | sim | Quantas amostras afetadas, quando se aplica. |
| `detalhe` | VARCHAR | não | Descrição legível do problema. |

## `decisao`

Decisões de tratamento (docs/decisoes.md): quando as fontes discordam, o que se escolheu.

Linhas: 11

- Chave: `decisao`

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `decisao` | VARCHAR | não | Identificador (D01…). |
| `titulo` | VARCHAR | não | Título da decisão; o texto completo, com evidência, está em docs/decisoes.md. |
