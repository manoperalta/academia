# Painel administrativo do tenant (Fase 2)

Critério de saída do PRD (Fase 2): **uma academia real opera sem tocar no Django admin.**
Este documento descreve o que já está implementado, como entrar, quem pode o quê e o que falta.

## Como acessar

- URL: `/gestao/` (ex.: `https://academia.safestack.com.br/gestao/`).
- Precisa de **vínculo ativo** com a rede (`core.VinculoUsuario`). Sem vínculo: 403.
- O menu lateral mostra **apenas** os módulos liberados para o papel do usuário.
- Seletor de unidade no cabeçalho: papéis de rede começam vendo **todas as unidades**;
  papéis de unidade já entram presos à própria unidade (e não conseguem trocar).

## Módulos (PRD §7.2)

| Módulo | Rota | O que faz hoje |
|---|---|---|
| Visão geral | `/gestao/` | KPIs (alunos ativos, professores, aulas, planos, receita do mês, a receber) + últimos alunos/pagamentos + progresso do assistente |
| Alunos | `/gestao/alunos/` | Lista com busca, filtro de status, "ver arquivados"; **ficha do aluno** com saúde, pagamentos e agendamentos; criar/editar (com criação do acesso de login); arquivar/restaurar |
| Professores | `/gestao/professores/` | Lista com busca; criar/editar (cria o acesso com perfil de professor); arquivar/restaurar |
| Aulas e vídeos | `/gestao/aulas/` | Lista com busca e filtro por categoria; criar/editar com upload de vídeo; arquivar/restaurar |
| Agenda e painéis | `/gestao/agenda/` | Grades de aula por data/horário/capacidade; agendamentos recentes com **check-in** |
| Financeiro | `/gestao/financeiro/` | Receita x despesa x resultado do mês, a receber, assinaturas vencendo em 7 dias; planos, pagamentos (lançar, editar, **dar baixa**) e despesas |
| Relatórios | `/gestao/relatorios/` | Indicadores + exportação **CSV** de alunos e pagamentos (com BOM para Excel); exportação é auditada |
| Comunicação | `/gestao/comunicacao/` | SMTP **da academia** (host, porta, TLS/SSL, remetente) e WhatsApp Cloud API; **e-mail de teste** |
| Identidade e dados fiscais | `/gestao/identidade/` | Título, CNPJ/IE, endereço, tema, mensagens de cobrança/aniversário; logotipo e favicon com pré-visualização |
| Equipe e acessos | `/gestao/equipe/` | Quem tem acesso, papel e unidade; ativar/desativar; **convites por e-mail** com link de aceite |
| Auditoria | `/gestao/auditoria/` | Toda escrita do painel (quem, o que, quando, IP) + filtros por ação/entidade |
| Assistente de configuração | `/gestao/configuracao/` | Checklist calculado dos dados reais: 9 passos com atalho para resolver cada um |

## Matriz de permissões (RBAC)

Níveis: `ver` (1) < `editar` (2) < `admin` (3). Implementada em `gestao/permissoes.py`
(`MATRIZ`) e coberta por teste (`gestao/tests/test_permissoes.py`).

| Papel | Visão geral | Alunos | Professores | Aulas | Agenda | Financeiro | Relatórios | Comunicação | Identidade | Equipe | Auditoria |
|---|---|---|---|---|---|---|---|---|---|---|---|
| superadmin da plataforma | admin | admin | admin | admin | admin | admin | admin | admin | admin | admin | admin |
| admin da rede | admin | admin | admin | admin | admin | admin | admin | admin | admin | admin | admin |
| gestor de unidade | ver | editar | editar | editar | editar | ver | ver | ver | ver | editar | ver |
| recepção | ver | editar | ver | ver | editar | ver | — | — | — | — | — |
| professor | ver | ver | — | editar | editar | — | — | — | — | — | — |
| financeiro da rede | ver | ver | ver | — | — | editar | ver | — | — | — | ver |
| auditor da rede | ver | ver | ver | ver | ver | ver | ver | ver | ver | ver | ver |
| aluno | — | — | — | — | — | — | — | — | — | — | — |

Regras adicionais de defesa em profundidade:

1. **Sem vínculo ativo → 403** (mesmo autenticado).
2. **Conta suspensa/somente leitura → escrita bloqueada** (`EscritaPermitidaMixin`).
3. **Isolamento por rede**: o manager escopado filtra tudo pela rede do contexto; pedir id de
   outra rede devolve **404** (nunca o dado).
4. **Isolamento por unidade**: quem opera uma unidade não enxerga a outra (mesmo na mesma rede).
5. **Toda escrita passa pela auditoria** (`api.RegistroAuditoria`), com ação, entidade, id,
   descrição, IP e origem.

## Convites de equipe

1. Admin da rede → **Equipe → Convidar**: escolhe e-mail, papel e (opcional) unidade.
2. O sistema gera um token (expira em **7 dias**) e envia o link pelo SMTP da própria academia.
3. A pessoa abre `/gestao/convite/<token>/` e **cria a própria senha** (não existe senha enviada por e-mail).
4. Ao aceitar, o `VinculoUsuario` é criado já com o papel do convite e a pessoa entra logada no painel.
5. Convite expirado/cancelado não cria vínculo; a equipe pode desativar acessos sem apagar histórico.

## Como rodar

```bash
cd /home/manoperalta/academia-saas
make subir && make migrar && make test          # ambiente de dev (PostgreSQL em 127.0.0.1:5433)
docker compose -f docker-compose.dev.yml run --rm web python manage.py createsuperuser
docker compose -f docker-compose.dev.yml run --rm web python manage.py tenantizar --nome "Academia"
docker compose -f docker-compose.dev.yml run --rm web python manage.py runserver 0.0.0.0:8000
```

## O que ainda falta para fechar a Fase 2 (honesto)

- **Meu plano / assinatura** da própria academia (depende da Fase 3 — cobrança da plataforma).
- **Aulas: imagens da aula** (`ImagemAula`) e upload em partes + transcodificação de vídeo
  (hoje o vídeo sobe inteiro no formulário).
- **Ações em massa com desfazer**, campos personalizados, etiquetas e notas internas (§22.3 do PRD).
- **Impressão/PDF** de fichas e recibos; busca global; estados de carregando/vazio padronizados.
- **Testes de navegador (Playwright)** nos fluxos críticos e acessibilidade AA.
- **Tarefas assíncronas** (fila/worker) para e-mails em massa e relatórios grandes.
- Os formulários usam classes Tailwind via CDN: antes de produção, empacotar o CSS
  (`tailwindcss build`) para não depender de CDN.

## Notas de implementação

- Templates genéricos (`lista.html`, `_tabela.html`, `formulario.html`) evitam repetição: cada
  módulo só declara `colunas`, busca, rotas e formulário.
- Listagens respondem a **HTMX** (busca e paginação trocam só a tabela).
- `gestao/emails.py` usa o SMTP da própria academia quando configurado; sem configuração,
  cai no backend padrão do Django (console em dev).
- O painel não depende do Django admin em nenhum fluxo coberto pelos testes.
