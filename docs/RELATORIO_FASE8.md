# Fase 8 (parte 1) — remuneracao variavel, gamificacao, NPS e PWA do aluno

## O que entrou

**`remuneracao/` — comissoes de professor (RF-RED-017 / RF-CMP-014).** Regras por aula, por aluno
ativo, percentual do recebido ou valor fixo, com piso e teto mensal, escolhidas em cascata
(professor -> unidade -> rede) e com vigencia. A apuracao e **idempotente por professor x unidade x
periodo** — o que ja resolve o **rateio do professor multi-unidade** — guarda **memoria de calculo
linha a linha**, **hash reproduzivel** do numero e **conferencia por recalculo** (o demonstrativo diz
"confere, zero divergencia" ou lista exatamente qual linha divergiu). Tem baixa de pagamento, atraso
automatico e **extrato que o proprio professor acessa**. A comissao por aula **se recusa a inventar
numero** quando a agenda nao tem professor vinculado: registra "nao apuravel" e diz a fonte.

**`gamificacao/` — pontos, niveis, conquistas e ranking.** Regra de pontos por evento com **limite
diario**, nivel a cada 500 pontos, conquistas por quantidade de eventos (com bonus) e ranking por
unidade + indicador de engajamento do mes.

**`nps/` — pesquisas e NPS.** Pesquisa NPS/nota/texto, calculo de NPS (promotores 9-10, neutros 7-8,
detratores 0-6) com classificacao, **NPS por unidade** para achar a unidade fraca e **fila de
tratamento do detrator** (marcar tratado guarda a observacao na resposta).

**`area_do_aluno/` — PWA do aluno (RF-RED-002/003).** Manifest e **service worker por escopo**
(cache das telas, funciona offline), **check-in em qualquer unidade da rede** que pontua na
gamificacao, tela de pontos/ranking, resposta de pesquisa pelo celular, avisos da academia, marca da
rede (nome e cor vindos do cliente) e **acessibilidade AA**: skip link, foco visivel, `aria-live` nas
mensagens e `prefers-reduced-motion`.

## Correcao e verificacao

A integracao com o painel estava quebrada: o enum de modulos tinha os tres modulos novos, mas o
**mapa de rotas do menu** nao — o que fazia o menu renderizar uma URL vazia e derrubar **todas** as
telas do painel com `NoReverseMatch` (5 testes de `rede` e `governanca` junto). Corrigido com o mapa
completo **e** com dois testes de invariante que impedem a reincidencia: todo modulo do enum precisa
ter rota reversivel, e os tres modulos novos precisam existir no enum e na matriz de papeis.

Causa de fundo da instabilidade: o envio de arquivos levava o diretorio de trabalho inteiro, entao
copias locais antigas de `gestao/*` **sobrescreviam no servidor** o que os patches acabavam de
aplicar. O envio passou a ser **so dos arquivos alterados** e as copias velhas foram removidas.

Erro de processo corrigido: publicar com `pytest | tail` engole o codigo de saida do pytest, e
`grep -q failed` nao pega o resumo. Agora a suite roda com `code=$?` e o commit so acontece com
`code = 0`.

## Numeros

**Suite inteira verde** (codigo de saida 0), `manage.py check` sem problemas, migracoes
`remuneracao.0001`, `gamificacao.0001`, `nps.0001` e `area_do_aluno.0001` aplicadas. 20 testes novos
nesta fase, incluindo o ciclo do check-in (registra, recusa unidade de outra rede, recusa matricula
inativa), o calculo do NPS, a conquista por quantidade, o demonstrativo de comissao conferivel, o
PWA com manifest e service worker, e a acessibilidade das telas.

## Decisao registrada

Os modelos da fase 8 declaram **FK explicita de rede** (como o app `rede/`), em vez de herdar
`TenantModel`: as consultas de apuracao e ranking sao por periodo e por unidade, e o manager escopado
por contexto esconderia linhas legitimas de outras unidades da mesma rede. Ficam listados como
excecao deliberada no teste de isolamento — a chave de isolamento existe e esta indexada.

## Ainda pendente na fase 8

Design system e as telas restantes do inventario 21.3, midia com upload em partes e player com URL
assinada, PDFs dos documentos de negocio, busca global, Playwright nos fluxos criticos e os itens de
paridade que dependem de decisao comercial: Wellhub/TotalPass/ClassPass, catraca, NFS-e, Pix
automatico, PDV/estoque, CRM/leads, assinatura digital de contrato e retencao/evasao.
