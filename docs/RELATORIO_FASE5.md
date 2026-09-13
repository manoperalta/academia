# Fase 5 — relatório de entrega (escala, marca e endurecimento)

## Entregáveis do PRD x situação

| Entregável | Situação |
|---|---|
| Subdomínio por tenant + RF-PLT-050 | **Entregue** (resolução por Host antes de sessão/vínculo; provisionamento visível) |
| Domínio próprio com verificação (RF-PLT-051) | **Entregue** (TXT + arquivo `/.well-known`, diagnóstico em linguagem de cliente) |
| Certificado com reemissão após falha ACME (RF-PLT-051) | **Entregue** (estado por cliente, "reemitir TLS" no painel e cron `verificar_dominios --emitir`) |
| Estado de provisionamento visível (RF-PLT-052) | **Entregue** (passos DNS → certificado → pronto) |
| Mídia em namespace por cliente com sessão (RNF-010) | **Entregue** (URL protegida, `X-Accel-Redirect`, comando de migração) |
| Backup + verificação por restauração + retenção (RNF-005) | **Entregue** (pg_dump ou dump lógico, sha256, verificação, 7+4, exportação por cliente) |
| Observabilidade por tenant (RNF-008) | **Entregue** (métricas/hora, erros 5xx deduplicados, alertas, log com tenant e usuário, `/status/`) |
| LGPD operacional (RNF-006, RF-TEN-021) | **Entregue** (exportação, anonimização com retenção fiscal, pedidos com prazo, registro de leitura de dado sensível, regras de retenção) |
| 2FA com códigos de recuperação (RNF-009) | **Entregue** (opcional para o dono, **obrigatório** para a equipe da plataforma) |
| Rate limit e bloqueio progressivo no login (RNF-009) | **Entregue** |
| App do professor/aluno evoluído | **Pendente** (Fase 8 do PRD) |
| Webhooks de saída do pacote Ouro | **Pendente** (Fase 8 do PRD) |

## Evidências

- **Suíte completa verde** (334 testes; 41 novos nesta fase) em GitHub Actions-ready, com
  `ruff check` limpo e `manage.py check` sem problemas; cobertura **84%**
  (core+api+gestao+plataforma+vitrine+governanca).
- **Vetores oficiais da RFC 6238** no TOTP (94287082 / 07081804 / 14050471 / 89005924).
- Comandos executados de verdade no dev:
  - `seed_governanca` → 6 regras de retenção criadas;
  - `agregar_metricas` → agregação + alertas (alertou corretamente "nenhum backup do banco registrado");
  - `backup_banco --metodo json` → arquivo + sha256 + verificação "backup lógico legível com 298 registros" + retenção simulada;
  - `aplicar_retencao` → nada vencido (correto).

## Dois bugs reais encontrados pelos próprios testes

1. **Verificação de domínio**: o retorno `(bool, mensagem)` da checagem por TXT estava sendo
   desempacotado errado — a **mensagem** era usada como resultado, então qualquer domínio com TXT
   "falhando" era dado como verificado.
2. **2FA obrigatório da equipe**: o curto-circuito de "sem 2FA ativo não há o que cobrar" pulava a
   obrigatoriedade da equipe da SafeStack — a plataforma abria sem o segundo fator.

## Decisões

1. **A plataforma fora do manager escopado** para métricas/backup/erros: são entidades de operação,
   consultadas fora do contexto de um cliente; o isolamento delas é coberto por testes próprios.
2. **Backup em dois modos**: `pg_dump` quando existe no ambiente, senão dump lógico gzipado — o mesmo
   caminho que a suíte usa, o que torna a verificação testável de ponta a ponta.
3. **Mídia por autorização, não por obscuridade**: URL única que confere o vínculo do usuário com o
   dono do arquivo, com `X-Accel-Redirect` para não passar bytes pelo Python.
4. **Retenção conserva o que a lei exige**: pagamentos nunca são anonimizados/eliminados pelo expurgo.

## Pendências assumidas

- `dnspython` é opcional: sem ele, a verificação de domínio usa o arquivo HTTP (funciona, mas o TXT é
  mais elegante). Instalar no deploy é 1 linha.
- Rate limit distribuído: hoje usa o cache local; com mais de um processo/instância, apontar para Redis.
- App do professor/aluno evoluído e webhooks de saída do Ouro seguem para a Fase 8.
- Nada foi publicado em produção: tudo na branch `feat/saas-multitenant` (dev no i3).
