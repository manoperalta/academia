# Fase 2 — relatório de entrega (RBAC, convites e painel do tenant)

## O que foi pedido no PRD e o que foi entregue

| Entregável da Fase 2 | Situação |
|---|---|
| RBAC por rede (papel × módulo × unidade) | **Entregue** (`gestao/permissoes.py`, matriz testada) |
| Convites de equipe com aceite | **Entregue** (token de 7 dias, e-mail, criação de conta, vínculo) |
| Painel com os 10 módulos de §7.2 | **Entregue** (15 telas + assistente) |
| Assistente de configuração (§7.3) | **Entregue** (9 passos calculados dos dados reais) |
| Responsividade | **Parcial** (layout responsivo com menu colapsável; falta teste em dispositivos) |
| Operar sem o Django admin | **Atendido nos fluxos cobertos por teste** (falta fechar os itens da lista "o que ainda falta" em docs/PAINEL.md) |

## Evidências (rodadas no ambiente de dev, PostgreSQL)

- `pytest`: **174 testes, todos verdes** (inclui 60 novos da Fase 2).
- `ruff check` + `ruff format`: **All checks passed**.
- `manage.py check`: *no issues*.
- `makemigrations --check`: sem mudanças pendentes (migração `core.0002_conviteequipe` aplicada).
- Isolamento verificado nas telas: aluno de outra rede não aparece na lista (200 com lista vazia),
  detalhe/edição/arquivamento de outra rede devolvem **404**, pagamento/convite/auditoria de outra
  rede não aparecem, recepção não vê outra unidade da mesma rede.

## Decisões tomadas (e por quê)

1. **Papéis de rede veem todas as unidades por padrão**; papéis de unidade entram presos à sua.
   A unidade ativa vive na sessão (`rede_id` + `unidade_id`), resolvida pelo middleware — assim o
   mesmo mecanismo serve para o painel e para a API, e a troca é auditável.
2. **Permissão no nível da view, não do template**: o menu esconde o que não pode, mas quem digita a
   URL recebe 403 — esconder no HTML nunca é controle de acesso.
3. **Arquivar em vez de excluir** em todos os cadastros (soft delete restaurável, com auditoria).
4. **Convite sem senha por e-mail**: o link leva a uma página onde a própria pessoa cria a senha.
5. **Formulário genérico + tabela genérica**: cada módulo declara colunas/rotas/form; menos código
   para o mesmo resultado e menos divergência entre telas.
6. **Erro de contexto de rede não é mais silencioso em dev/teste**: em produção o middleware segue
   resiliente (loga e continua), mas em dev/teste ele estoura — foi exatamente esse silêncio que
   escondeu um `NameError` durante esta implementação.

## Riscos e dívidas assumidas

- Tailwind/HTMX/Alpine por **CDN**: empacotar antes de produção.
- Upload de vídeo sem partes/transcodificação (arquivo grande ainda bloqueia a requisição).
- Auditoria guarda `dados_antes`/`dados_depois` apenas onde o código preenche (hoje: nas ações que
  passam pelo `registrar()`); generalizar para todas as alterações de campo é trabalho da Fase 5.
- Sem 2FA e sem limite de tentativas de login específico do painel (Fase 5).
