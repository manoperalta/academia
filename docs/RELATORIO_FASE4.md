# Fase 4 — relatório de entrega (venda self-service e limites)

## Entregáveis do PRD x situação

| Entregável | Situação |
|---|---|
| Site de pacotes + cadastro público (RF-PLT-030/040) | **Entregue** (home, planos, ajuda, contato, cadastro com plano escolhido) |
| Provisionamento transacional (RF-PLT-031) | **Entregue** (Rede + Assinatura + dono + Configuracao + IdentidadeVisual; rollback testado) |
| Trial de 14 dias | **Entregue** (configurável, com avisos T-7/T-3/T-1) |
| Limites + avisos + upgrade/downgrade (RF-TEN-040…043) | **Entregue** (bloqueio no servidor, avisos 80/95, upgrade imediato proporcional, downgrade agendado) |
| Importação CSV de alunos/professores (RF-PLT-034) | **Entregue** (conferência antes de gravar, relatório por linha, teto respeitado, modelo para download) |
| E-mails do ciclo de vida (RF-PLT-032) | **Entregue** (boas-vindas + convite de primeiro acesso; trial e cobrança pela régua) |
| Central de ajuda inicial (RF-PLT-041) | **Entregue** (versão inicial por módulo) |

## Evidências

- **293 testes verdes** (40 novos nesta fase), `ruff check` limpo, `manage.py check` sem problemas,
  `makemigrations --check` sem pendências, cobertura **86%** (core+api+gestao+plataforma+vitrine).
- **Demonstração ponta a ponta executada no dev** (`bash scripts/demo_cadastro.sh`):
  site 200 → cadastro 302 → tenant criado (trial **e** via Pix) → fatura `FAT-2026-00003` com
  Pix copia e cola → webhook idempotente (1ª notificação processa, 2ª é ignorada) → fatura **Paga**
  e tenant **ativo** → convite de primeiro acesso → senha definida (302, já autenticado) →
  painel do cliente respondendo 200 em visão geral, Meu plano, alunos e importação.
  A demonstração remove, no fim, apenas os tenants que ela mesma criou.

## Decisões

1. **Preços aplicados**: Prata R$ 125,00 · Bronze R$ 99,00 · Ouro R$ 199,00 (anual = 12× com 15% de desconto).
2. **CNPJ alfanumérico aceito** (regra de 2026): a validação usa o mesmo módulo 11, com letras valendo ASCII-48.
3. **Site público na raiz**, com a landing antiga preservada em `/academia/` (nada foi apagado).
4. **Importação em dois tempos** (conferir → confirmar): quem vende migração precisa mostrar o que vai
   acontecer antes de tocar na base do cliente.
5. **Teto do pacote vale também na importação**: o excedente é recusado com motivo, nunca truncado em silêncio.

## Pendências assumidas

- Logins dos alunos importados (depende do portal do aluno + "esqueci minha senha" — Fase 5).
- Rate limit/captcha e verificação de e-mail no cadastro público antes de abrir ao mundo.
- Nota fiscal (RF-PLT-024, decisão contábil) e comunicação avulsa com o tenant (RF-PLT-008).
- **Critério de saída da Fase 4** ("uma academia nova entra sozinha, paga e começa a operar sem que
  ninguém da SafeStack toque no sistema"): **cumprido no ambiente de dev em modo simulado**; falta
  apenas a chave real do Asaas para a cobrança de verdade.
