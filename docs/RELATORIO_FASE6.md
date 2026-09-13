# Fase 6 — relatório de entrega (rede e franquias)

## Critério de saída do PRD

> "uma rede com 3 unidades operando, com dados isolados por rede e por unidade, comparativo correto e
> **um repasse emitido e conferido linha a linha**."

**Cumprido e demonstrado** (`bash scripts/demo_rede.sh`, que remove o que cria):
rede com 3 unidades (1 própria, 2 franqueadas) → regra de repasse da rede (8% sobre líquido, fundo de
1,5%, taxas de gateway de 2,5% excluídas, piso de R$ 50) → 3 repasses emitidos → demonstrativo com
memória de cálculo (receita → exclusão → royalty → fundo) → **conferência OK, mesmo número no recálculo,
zero divergência**, com hash `8934b0ee…` → comparativo correto → política travando desconto acima do teto.

## Entregáveis (24 `RF-RED-*`)

| Requisito | Situação |
|---|---|
| RF-RED-001 unidades (CNPJ, tipo, cidade, gestor, status, sobrescrita de marca) | **Entregue** |
| RF-RED-004/024 transferência de aluno e encerramento de unidade em lote | **Entregue** |
| RF-RED-006 catálogo da rede com distribuição em lote | **Entregue** |
| RF-RED-008 metas por unidade/período com realizado e atingimento | **Entregue** (ocupação depende de dados de turma do cliente) |
| RF-RED-009/010 comparativo, ranking e consolidado da rede | **Entregue** |
| RF-RED-012 repasse/royalty configurável, memória de cálculo, conciliação e reprodutibilidade | **Entregue** |
| RF-RED-013 marca herdada com sobrescrita controlada | **Entregue** (política + `sobrescrever_branding`) |
| RF-RED-014 governança do que a unidade não pode mudar | **Entregue** |
| RF-RED-015 comunicados com confirmação de leitura | **Entregue** |
| RF-RED-016 onboarding de unidade com template e checklist | **Entregue** |
| RF-RED-018 alçadas e aprovações (solicita → decide → registra) | **Entregue** |
| RF-RED-021/022 limites de unidades do pacote com mensagem acionável | **Entregue** |
| RF-RED-023 importação multi-unidade com relatório de conferência por unidade | **Entregue** |
| RF-RED-002/003 aluno e check-in entre unidades | **Parcial** (o aluno já tem unidade; o check-in cross-unidade depende do app do aluno — Fase 8) |
| RF-RED-005 preços em dois níveis com sinal de divergência | **Parcial** (o plano aceita unidade ou rede; falta a tela de divergência) |
| RF-RED-007 templates de grade | **Parcial** (cópia de grade implementada; falta o alerta de divergência) |
| RF-RED-011 cobrança centralizada × local | **Pendente** (decisão §16.14 — hoje o gateway é por rede/unidade) |
| RF-RED-017 equipe multi-unidade com rateio de remuneração | **Pendente** (Fase 8, comissões) |
| RF-RED-019 auditoria por unidade e exportação | **Parcial** (auditoria já registra a unidade; falta o filtro na tela) |
| RF-RED-020 visão de grupo multi-bandeira | **Pendente** (decisão §16.20) |

## Fase 6 também entrega jobs e dry-run

- `RotinaAgendada` + `executar_rotinas` (cron de hora em hora): métricas, backup com verificação,
  faturas, régua, **repasses do mês**, retenção, domínios, metas e atrasos — cada execução guarda
  situação, resultado e duração, e **falha não derruba as outras** (testado).
- `--dry-run` global: mostra o que seria feito sem gravar nada (a prévia do repasse na tela usa isso).

## Evidências

- **427 testes verdes** (93 novos), `ruff check` limpo, `manage.py check` sem problemas,
  migrações geradas e aplicadas no dev (`rede.0001`, `governanca.0002`).
- Isolamento preservado: o teste que bloqueia o go-live (`tests/test_isolamento.py`) continua verde —
  os modelos de rede entram na lista de entidades de plataforma (FKs explícitas para rede/unidade).

## Decisões

1. **Repasse reproduzível por hash**: o demonstrativo guarda o `hash_do_calculo`; conferir recalcula e
   compara linha a linha. É o que permite auditar e "provar o número" para a franqueada.
2. **Base de cálculo configurável** (bruto/líquido, com exclusão de taxas, estornos, impostos e planos
   de parceiros) — a decisão comercial de §16 fica no cadastro da regra, não no código.
3. **Piso mínimo** entra como linha própria na memória, para não parecer royalty.
4. **Falha em rotina é dado de operação**: fica registrada na rotina e no alerta, nunca engolida.

## Pendências assumidas

- Cobrança centralizada × local (§16.14), visão de grupo (§16.20), check-in cross-unidade e equipe
  multi-unidade com rateio ficam para a Fase 8 (dependem de decisão comercial ou do app do aluno).
- Alertas automáticos por e-mail/WhatsApp das rotinas que falham: hoje aparecem no painel de saúde.

## Sobre a fase 7 (próxima)

A Fase 7 do PRD é a API REST completa (JWT + token de serviço, 30 recursos, OpenAPI no CI), os
**webhooks de saída com HMAC e reentrega** e o `dry_run` em lote pela API — o `dry_run` e os jobs já
ficaram prontos nesta fase.
