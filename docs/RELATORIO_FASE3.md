# Fase 3 — relatório de entrega (plataforma e cobrança)

## Entregáveis do PRD x situação

| Entregável | Situação |
|---|---|
| Painel da plataforma (RF-PLT-001…008) | **Entregue** (métricas, clientes, CRUD, ficha, suspender/reativar/cancelar, impersonation) |
| Pacotes e feature flags (RF-PLT-010…013) | **Entregue** (CRUD, módulos por pacote bloqueados no servidor, limite efetivo com exceção) |
| Assinaturas (RF-PLT-012) | **Entregue** (pacote, ciclo, trial, renovação, troca com ajuste proporcional no upgrade) |
| Faturas + cobrança (RF-PLT-020/021) | **Entregue** (geração automática, Pix via Asaas, modo simulado sem chave) |
| Baixa por webhook idempotente (RF-PLT-022) | **Entregue** (token, idempotência por evento, reativação automática, estorno) |
| Régua de cobrança (RF-PLT-023) | **Entregue** (D-3→D+30 configurável, evento por marco, sem repetir/perder) |
| Relatório financeiro (RF-PLT-025) | **Entregue** (MRR/ARR, inadimplência por cliente, CSV) |
| Ciclo de vida do tenant | **Entregue** (trial → ativo → inadimplente → somente leitura → suspenso → cancelado) |
| Impersonation auditada (RF-PLT-007) | **Entregue** (motivo obrigatório, registro, banner, saída, ficha de saúde fora do alcance) |
| Métricas MRR/churn (RF-PLT-006) | **Entregue** |
| Nota fiscal/recibos (RF-PLT-024) | **Pendente** — decisão contábil (§16.5) |
| Venda self-service (Fase 4) | **Pendente por escopo** |

## Evidências (ambiente de dev, PostgreSQL)

- `pytest`: **253 testes verdes** (88 novos nesta fase).
- `ruff check` + `ruff format`: **All checks passed**; `manage.py check`: sem problemas.
- `makemigrations --check`: sem mudanças pendentes (`plataforma.0001_initial` e `0002` aplicadas).
- Cobertura: **82%** em core+api+gestao+plataforma (plataforma: models 87%, servicos 90%,
  views 79%, gateways 45% — o caminho HTTP real do Asaas só roda com chave).
- Comandos rodados de verdade no dev: `seed_plataforma` (cria Prata 100/5, Bronze 150/10 e Ouro
  ilimitado + token de webhook + trial), `gerar_faturas`, `rodar_regua` (sem erros nem warnings).

## Fluxo provado por teste (ponta a ponta, sem dinheiro real)

1. Assinatura vence → `gerar_faturas` cria a fatura e emite a cobrança (Pix simulado).
2. Webhook `PAYMENT_RECEIVED` → fatura paga + tenant reativado; **evento repetido não refaz nada**.
3. Sem pagamento: D-3/D0/D+1/D+5 avisam (cada marco uma única vez), **D+10 bloqueia escrita**,
   **D+30 suspende** — e o pagamento posterior reativa.
4. Teto do pacote: cadastro recusado com mensagem, auditoria registrada, nenhum dado apagado.
5. Suporte: entra com motivo, vê o painel do cliente, **não vê ficha de saúde**, sai e o acesso cai.

## Decisões tomadas

1. **Preço não foi inventado**: os pacotes nascem com 0,00 e o comando aceita os valores — a
   decisão comercial é sua (§16.2). Sugestão de ancoragem segue no §23.5 do PRD.
2. **Modo simulado por padrão**: sem chave Asaas, nada cobra de verdade; o painel avisa. Isso
   permite homologar tudo antes de plugar a chave.
3. **Marcos de pré-vencimento são exatos** (D-3 só 3 dias antes), enquanto os de atraso disparam a
   partir do dia (quem chega em D+10 recebe os avisos anteriores que ainda não recebeu) — é o que
   garante "não perder disparo" sem spammar.
4. **`is_staff` = equipe SafeStack** com nível máximo no painel do tenant (é o que dá sentido ao
   suporte); a fronteira real é o contexto de rede + a auditoria.
5. **Plataforma fora do escopo automático do manager** (`plataforma` é ignorado no teste genérico
   de isolamento): esses modelos precisam agregar entre tenants; eles têm teste de isolamento
   próprio no painel do cliente.

## Riscos e dívidas assumidas

- **Chave do Asaas e token do webhook ficam em texto no banco** (mascarados na tela): criptografar
  no cofre/`SECRET_KEY` é a evolução natural (Fase 5).
- Sem **rate limit** no endpoint do webhook além do token; sem reentrega nossa para o gateway.
- Sem **Pix automático/recorrência** (depende de habilitação no Asaas) e sem boleto/cartão expostos.
- Nenhuma cobrança real foi feita — **o critério de saída da Fase 3 ("cobrar um cliente real") só se
  cumpre com a chave do Asaas configurada e um cliente real**; a lógica está pronta e testada.
