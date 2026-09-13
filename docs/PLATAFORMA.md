# Plataforma SafeStack (Fase 3): pacotes, cobrança e suporte

Painel em `/plataforma/`, exclusivo da equipe SafeStack (`is_staff`/`is_superuser`).
O tenant vê o próprio plano em `/gestao/plano/` ("Meu plano").

## Ciclo de vida do cliente

```
trial (14 dias, avisos em T-7/T-3/T-1) → ativo → inadimplente
   → D+10 somente_leitura (bloqueio de escrita) → D+30 suspenso → cancelado
```

- O status vive em `core.Rede.status` e **já era respeitado** pelo middleware e pelos mixins
  da Fase 1: ao entrar em `somente_leitura`/`suspenso`, a escrita é bloqueada e o dono continua
  lendo, com acesso à fatura — nunca retenção de dados (exportação sempre liberada).
- Pagamento recebido reativa o tenant automaticamente (`ATIVO`).

## Pacotes (RF-PLT-010/011/013)

| Pacote | Alunos | Professores | Unidades | Módulos que liga |
|---|---|---|---|---|
| Prata | 100 | 5 | 1 | impressão/PDF |
| Bronze | 150 | 10 | 1 | + WhatsApp, relatórios avançados |
| Ouro | ilimitado | ilimitado | ilimitado | + API, domínio próprio, multi-unidade, suporte prioritário |

- **Preço é decisão sua (§16.2 do PRD)** — o `seed_plataforma` cria com **0,00** e aceita
  `--prata/--bronze/--ouro` para gravar os valores. Enquanto for 0, nenhuma fatura tem valor.
- **Limite efetivo** = o mais restritivo entre pacote e exceção comercial (`motivo_excecao` +
  `autorizado_por` obrigatórios para criar exceção).
- **Contagem**: só cadastros **ativos** (inativos/arquivados não contam).
- **Teto atingido**: cadastro recusado com mensagem acionável apontando "Meu plano"; **nada é
  apagado**; o estado acima do teto só bloqueia cadastro novo.
- **Avisos em 80% e 95%** no painel do tenant e na lista de clientes da plataforma.
- **Módulos são bloqueados no servidor** (não só escondidos): exportação CSV exige
  `relatorios_avancados`; salvar a configuração do WhatsApp exige `whatsapp`.

## Cobrança (RF-PLT-020 a 025)

1. **Fatura** gerada por ciclo (`gerar_faturas`) com valor do pacote, desconto da assinatura,
   período e dados do emitente. Numeração legível `FAT-<ano>-<sequencial>`.
2. **Cobrança no gateway**: Pix (QR + copia-e-cola + link). Boleto/cartão ficam para a
   configuração do Asaas (§16.5).
3. **Baixa automática por webhook** (`POST /plataforma/webhook/asaas/`) — idempotente por
   `evento_id`; notificação repetida **não** refaz nada (fica registrada como "repetido").
4. **Régua configurável**: D-3, D0, D+1, D+5, D+10, D+30 (além dos avisos de trial).
   Cada disparo vira um `EventoCobranca` — único por (fatura, marco, canal), então rodar a régua
   duas vezes não duplica aviso nem perde marco.
5. **Relatório financeiro** com MRR/ARR, recebido x previsto, inadimplência por cliente e CSV.

### Gateway: Asaas ou modo simulado

- Com `asaas_api_key` preenchida em **Configuração da plataforma**, o sistema usa a API real
  (`sandbox`/`produção`).
- **Sem chave, roda em MODO SIMULADO**: gera ids/QR fictícios, permitindo testar todo o fluxo
  (fatura → cobrança → webhook → baixa → reativação) sem mover dinheiro. O painel avisa isso em
  amarelo, no topo das métricas.
- Botões de apoio no painel: **Cobrar**, **Baixar**, **Simular pagamento** (dispara um evento de
  gateway de mentira pelo caminho real do webhook) e **Cancelar**.

## Suporte com impersonation (RF-PLT-007)

- Entrar como cliente **exige motivo**, gera registro imutável (quem, quando, tenant, motivo, IP,
  user agent), marca o acesso como ativo e **conta cada ação** feita no modo suporte.
- Banner fixo no topo do painel do cliente com botão **Sair** — e sair encerra o registro.
- **Ficha de saúde fica fora do acesso de suporte** (nem exibe, nem aceita gravação).
- Auditoria: `impersonar` e cada ação saem em `api.RegistroAuditoria` com a etiqueta
  `[suporte:<usuário>]`.

## Métricas (RF-PLT-006)

MRR (ciclo anual normalizado por 12), ARR, clientes ativos/trial, inadimplentes (fatura vencida
em aberto), suspensos, churn do mês e percentual, ticket médio, novos no mês, receita por pacote,
em aberto e recebido no mês.

## Operação

```bash
# pacotes, configuração e trials (idempotente)
python manage.py seed_plataforma --prata 149 --bronze 249 --ouro 499

# fatura dos ciclos vencidos (idempotente por período)
python manage.py gerar_faturas              # --hoje AAAA-MM-DD  --sem-cobranca

# régua de cobrança: avisos, bloqueio em D+10, suspensão em D+30
python manage.py rodar_regua                # --hoje AAAA-MM-DD
```

Sugestão de cron (diário, 06:00 BRT):

```
0 9 * * *  python manage.py gerar_faturas
15 9 * * * python manage.py rodar_regua
```

## O que ainda falta nesta fase (honesto)

- **Self-service** (site de pacotes, cadastro público, provisionamento automático): é a Fase 4 —
  hoje a criação de tenant é manual, pelo painel da plataforma (venda assistida, RF-PLT-002).
- **NFS-e/recibos** (RF-PLT-024): depende da decisão contábil (§16.5) — os dados fiscais já ficam
  registrados na fatura e no cliente.
- **Boleto e cartão recorrente**: o cliente Asaas já está pronto (`criar_cobranca` usa Pix), falta
  expor a escolha e o cartão tokenizado no Asaas.
- **Avisos de limite por e-mail ao dono** (hoje aparecem no painel; o e-mail usa a régua, que cobre
  trial e cobrança).
- **Comunicação avulsa com o tenant** (RF-PLT-008) e **tickets de suporte** (RF-PLT-024+):
  planejados para a Fase 5.
