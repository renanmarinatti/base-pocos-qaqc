# Registro de decisões

Quando as fontes discordam ou o dado admite mais de uma leitura, a escolha fica registrada
aqui: o que foi visto, o que se decidiu, por quê e com que evidência. O código cita o
número da decisão (`config/nomes_pocos.yaml`, regras de qualidade).

Fontes: FORCE 2020 (Zenodo 10.5281/zenodo.4351156) e Sodir FactPages, snapshot de
2026-10-31.

---

## D01 — `16/11-1 ST3` (FORCE) é o ramal `16/11-1 S` da Sodir
**Visto (E1):** o FORCE tem `16/11-1 ST3`; a Sodir não tem esse nome. O ramal mais próximo
é `16/11-1 S`.

**Decidido:** tratar como o mesmo ramal, com ressalva.

**Por quê:** `ST3` indica desvio técnico (*technical sidetrack*), que a Sodir não registra
como ramal próprio; o perfil fica no ramal de origem.

**Evidência (E2):**
- posição na cabeça do poço: 1,9 m entre as duas fontes;
- mesa rotativa: a referência vertical do FORCE bate com a elevação da Sodir (diferença
  < 0,01 m);
- **ressalva:** o perfil do FORCE termina em 1.832 m MD, e a Sodir dá profundidade final de
  3.050 m. Compatível com um desvio técnico perfilado só em parte, mas não comprova. Os
  topos abaixo de 1.832 m não podem ser conciliados com o perfil desse poço.

## D02 — `25/2-13 T4` (FORCE) é o ramal `25/2-13` da Sodir
**Visto (E1):** o FORCE tem `25/2-13 T4`; a Sodir só tem `25/2-13`.

**Decidido:** tratar como o mesmo ramal.

**Por quê:** `T4` é o quarto desvio técnico, que a Sodir registra sob o ramal de origem.

**Evidência (E2):** posição a 1,2 m; mesa rotativa igual (< 0,02 m); profundidade final
3.901 m no perfil contra 3.908 m na Sodir.

---

## D03 — Nomes de unidade: comparar pelo nome-base, com duas renomeações
**Visto (E4):** a mesma unidade aparece com grafias diferentes nas três versões:
`Statfjord Fm.` (2020) e `STATFJORD GP` (hoje), `Blodoeks Fm.` e `BLODØKS FM`,
`INTRA DRAUPNE FM SST` e `SS`, `BAAT GP.` e `BRENT GP`, `ROTLIEGENDES` e `ROTLIEGEND`.

**Decidido:** casar pelo nome-base (maiúsculas, sem ponto, Ø → OE, sem o sufixo de nível)
e aceitar duas renomeações: `BAAT → BRENT` e `ROTLIEGENDES → ROTLIEGEND`
(`config/nomes_unidades.yaml`). A mudança de nível (membro que virou formação, formação
que virou grupo) é registrada como informação, não como divergência: 206 topos.

**Evidência:** dos 49 topos `BAAT GP` de 2020, 98% estão à mesma profundidade (±1 m) que
`BRENT GP` hoje. Marcadores sem nome formal da Sodir (`NO FORMAL NAME`,
`UNDIFFERENTIATED`, `NO GROUP DEFINED`) ficam fora da comparação.

## D04 — Topos: a Sodir de hoje é a referência
**Visto (E4):** os rótulos de grupo e formação do FORCE seguem a cópia do NPD de 2020.
Desde então a Sodir reinterpretou 26 topos (de 2 a 409 m), 13 deles do topo da Formação
Utsira.

**Decidido:** no banco final, o topo oficial é o da Sodir (snapshot 2026-10-31). Os rótulos
do perfil ficam como estavam (são a interpretação usada na competição), e cada topo
divergente fica marcado na tabela de conciliação.

**Por quê:** a Sodir é a fonte oficial e a mais recente. Corrigir os rótulos amostra a
amostra seria reinterpretar, e reinterpretar não é papel da base.

## D05 — `34/10-16 R`: 27 topos deslocados 3 m de uma vez
**Visto (E4):** entre 2020 e hoje, 27 topos desse poço mudaram exatamente 3 m na Sodir. Os
mesmos topos no perfil do FORCE divergem 3,1 m.

**Decidido:** classificar como **mudança de referência**, não reinterpretação. Vale a
Sodir (D04). Os 2 topos do poço que fogem dos 3 m continuam como divergência comum.

**Por quê:** reinterpretação muda um topo ou outro; deslocar todos pelo mesmo valor é
sinal de que mudou a referência de profundidade do poço.

## D06 — `30/3-5 S`: posição e mesa rotativa não comparáveis pela primeira amostra
**Visto (E2):** a primeira amostra com coordenada está a 2,4 km da cabeça do poço, e
`MD − TVDSS` ali passa a mesa rotativa em mais de 1.000 m.

**Corrigido na E5:** a primeira leitura (E2) dizia que o perfil começava abaixo do ponto
de desvio. Não é isso. O perfil começa a 433 m, mas de 433 a 3.891 m só tem GR: as
colunas de trajetória (X, Y, Z e `DEPTH_MD`) ficam vazias. A trajetória só começa a
3.891 m, já desviada. O banco final recusou a carga por causa disso (MD nulo), e a
padronização passou a usar o índice do LAS (`DEPT`), que existe em toda amostra. O mesmo
acontece em 117 poços (115.746 amostras); em 68 deles passa de 1% do poço (regra R15).

**Decidido:** não comparar posição nem referência vertical desse poço pela primeira
amostra com trajetória. A conciliação marca "trajetória do perfil só começa a 3892 m, já
desviada".

**Por quê:** a coordenada do perfil é a do poço naquela profundidade, já desviado. Não é
erro de coordenada; é trajetória ausente no trecho raso.

## D07 — Referência vertical diferente da mesa rotativa em 5 poços
**Visto (E4, refeito na E5 com o MD corrigido):** em `16/2-11 A`, `29/6-1`, `34/10-35`,
`34/6-1 S` e `35/11-5`, `MD − TVDSS` na primeira amostra com trajetória difere da mesa
rotativa da Sodir em 0,6 a 2,0 m.

**Decidido:** a mesa rotativa oficial é a da Sodir. O MD do perfil não é deslocado.

**Por quê:** não se sabe qual dos dois mudou (o perfil ou o cadastro), e 2 m está dentro
do que separa profundidade de sondador e de perfilagem (D08). Deslocar o perfil seria
inventar uma correção. A diferença fica marcada por poço.

## D08 — Perfil abaixo da profundidade final oficial em 50 poços
**Visto (E4, refeito na E5 com o MD corrigido):** o perfil termina de 5 a 100 m abaixo da
profundidade final que a Sodir publica (mediana 8 m). Com o MD antigo, que perdia o
trecho sem trajetória, eram 30 poços e no máximo 40 m.

**Decidido:** manter o perfil. Marcar o poço; acima de 20 m, marcar para verificação:
`25/7-2` (100 m), `29/3-1` (40 m), `33/9-17` (27 m) e `35/4-1` (22 m).

**Por quê:** a profundidade final oficial costuma ser a do sondador (medida pela
tubulação), e a do perfil é a do cabo da perfilagem. As duas diferem por estiramento do
cabo e da coluna, e alguns metros são comuns. 100 m já não se explica assim.

## D09 — `MUDWEIGHT` fica fora do banco final
**Visto (E3):** nenhum dos 29 poços declara unidade, e a mediana por poço cai em três
escalas (0,13–0,17; 1,1–1,6; 156).

**Decidido:** não carregar a curva no banco final nem na exportação LAS. Ela continua no
bruto.

**Por quê:** sem unidade, converter seria adivinhar. A curva não é usada na
interpretação geológica, e uma curva sem unidade confiável é pior que nenhuma.

## D10 — −999 em `34/11-2 S` vira nulo no banco final
**Visto (E3):** `RXO` e `SP` usam −999, diferente do NULL declarado (−999,25).

**Decidido:** tratar como nulo no banco final e registrar a troca.

**Por quê:** −999 não é medida de resistividade (R02) nem de potencial plausível no
contexto; é o mesmo código de ausência com outra grafia.

## D11 — PEF contaminado por baritina: mantém o valor, marca o trecho
**Visto (E3):** 60 poços com PEF acima de 10.

**Decidido:** manter os valores e marcar os trechos (R14). A exportação inclui a marca.

**Por quê:** o valor foi medido de verdade; o problema é o que ele representa. Quem
interpreta decide se descarta. Apagar tiraria essa decisão de quem tem contexto para ela.

---

## Testemunhos (E4): sem decisão pendente
Os 501 intervalos testemunhados (89 poços) caem acima da profundidade final, inclusive
os 5 convertidos de pés. 499 têm perfil no intervalo inteiro, 1 tem perfil parcial
(`16/2-11 A`, 76%) e 1 não tem perfil (`25/2-7`, testemunho 4, abaixo do fim do perfil).
A litologia do perfil nos intervalos testemunhados é majoritariamente arenito (250 de
501), como se espera: testemunho é caro e vai para o reservatório.
