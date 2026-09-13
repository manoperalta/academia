# Fase 7 — relatório de entrega (API REST e administração remota)

## O que foi entregue

**Catálogo completo dos 30 recursos** (`api/recursos.py`), cada um com modelo, escopo mínimo, campos
expostos, filtros, busca e ordenação — substituindo os 10 recursos iniciais. O comportamento comum
vive num único `RecursoDaApi`: escopo por operação, recorte de rede/unidade, paginação, filtros,
busca, **`updated_since`/`deleted_since`**, **`ETag`/304**, **`Idempotency-Key`**, **`dry_run`**,
**lote com relatório por item** (e `atomic=true`), **desfazer em 24 h** e **auditoria por token**.

**Autenticação**: JWT HS256 próprio (sem dependência nova) com `POST /api/v1/auth/token/` (e-mail e
senha → acesso + renovação) e `/api/v1/auth/refresh/`; os tokens de serviço continuam com escopos,
validade e uso registrado. Papel do painel → escopos da API em `ESCOPOS_POR_PAPEL` (RF-API-004: o
menor escopo possível — recepção não alcança financeiro de escrita, professor não vê ficha de saúde).

**Endpoints novos além do CRUD**: `/estado-da-rede/` (limites, uso, filas, rotinas — RF-API-014),
`/metricas-da-rede/`, `/inadimplencia/`, `/relatorios/<tipo>/` (gera job), `/jobs/<id>/`,
`/lgpd/titulares/<id>/<acao>/`, `/tarefas/<id>/download/` e o **playground** em `/api/v1/playground/`
(RF-API-016). A documentação OpenAPI/Swagger/ReDoc continua em `/api/schema/`, `/api/docs/` e
`/api/redoc/` (drf-spectacular, já no CI).

**Webhooks de saída** (RF-API-001/002/003): 14 eventos catalogados, assinatura **HMAC-SHA256** do corpo
com timestamp (cabeçalhos `X-Evento`, `X-Entrega`, `X-Timestamp`, `X-Assinatura`), **reentrega com
backoff** de 1 min → 5 min → 30 min → 2 h → 12 h, log de cada tentativa com a resposta e reenvio manual
pela API.

**Jobs assíncronos** (RF-API-012/015): `TarefaAssincrona` com relatório/importação/exportação/LGPD,
acompanhamento por `/jobs/<id>/` e download com expiração de 2 dias. As rotinas de hora em hora já
processam a fila de tarefas e entregam os webhooks (`executar_rotinas`, com dry-run).

## Evidências

- **453 testes verdes**, `ruff check` limpo, `manage.py check` sem problemas, migração `api.0002`
  aplicada. Os contratos da Fase 1 seguem valendo (`/api/v1/estado/` continua público e com o mesmo
  formato; escrita por API continua gerando auditoria com `entidade`, `acao` e o token).
- O ciclo do critério de saída é testado ponta a ponta: **lote com pré-visualização** (`dry_run` não
  grava), confirmação do lote, **métricas da rede** por endpoint, **relatório como job** e download do
  CSV, com **auditoria registrando o token** que escreveu.
- **Paridade tela ↔ endpoint** (RF-API-010) verificada por teste para as telas de escrita principais.

## Pendências assumidas

- **Limite e cota por token** (RF-API-007, `429` + `Retry-After`): ainda não implementado — hoje a
  proteção é o escopo e a validade do token.
- **Busca incremental com `deleted_since`** funciona para arquivamento lógico; falta o log de exclusões
  para sincronização real de quem apaga fisicamente.
- **Callback de término de job** (RF-API-015): hoje é polling documentado; o webhook de conclusão de
  tarefa não foi disparado.
- Ações extras de alguns recursos (por exemplo `/cobrancas/{id}/pix/`, `/midias/{id}/processar/`,
  `/campanhas/{id}/disparar/`) continuam sem endpoint dedicado: o CRUD está exposto, o comando não.
- **Assinatura digital de contrato** (`/contratos/{id}/assinar/`) segue fora: depende da Fase 8.

## Decisões

1. **JWT próprio em vez de `simplejwt`**: evita dependência nova e mantém tudo auditável; validado com
   testes de assinatura errada, expiração e emissor.
2. **Escrita injeta o contexto do token** (rede/unidade) antes da validação — o integrador não precisa
   mandar `rede`, e o token não consegue escrever em outra rede.
3. **Exclusão vira arquivamento** e o lote oferece desfazer: é o que torna a operação por agente
   reversível (RF-API-006).
4. **Nada de objeto de modelo em JSONField**: jobs guardam `rede_id`/`aluno_id` e resolvem na execução
   (erro que apareceu no meio do caminho e virou teste).
