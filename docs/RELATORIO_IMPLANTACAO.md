# Relatorio de implantacao — Fase 0 + nucleo da Fase 1

Branch: `feat/saas-multitenant` · Base: `1f881ea` · Ambiente: `/home/manoperalta/academia-saas` (i3)
Escopo: aplicar o PRD de SaaS multi-tenant ate o ponto em que a **fundacao e o isolamento** estejam
prontos, testados e documentados. **Nada foi alterado em producao.**

## Entregue e verificado

| Item | Evidencia |
|---|---|
| Configuracao por ambiente (12-factor), sem segredo no codigo | `app/settings_env/`; `manage.py check` → *no issues* |
| PostgreSQL no lugar do SQLite (dev e testes) | `docker-compose.dev.yml` + `Dockerfile.dev`; migrations aplicadas |
| Nucleo de tenancy: `Rede`, `Unidade`, `VinculoUsuario`, `TenantModel`/`UnidadeModel` | `core/models.py`; migrations `core.0001` |
| 18 modelos convertidos para escopo de rede | `scripts/apply_tenancy.py`; migrations em 8 apps |
| Managers escopados + contexto + middleware | `core/managers.py`, `core/context.py`, `core/middleware.py` |
| RBAC por rede/unidade + mixins de CBV | `core/papeis.py`, `core/mixins.py` |
| API REST (DRF) com token de servico e escopos | `api/` — 10 recursos, `/api/docs/`, OpenAPI |
| Auditoria append-only de escrita por API | `api/models.py`; teste dedicado |
| Erros RFC 7807 com codigo estavel | `api/exceptions.py`; testado no 401/403 |
| Suite de testes | **50 testes passando** (isolamento, caracterizacao, API) |
| Qualidade PEP8 | `ruff check` → *All checks passed*; `ruff format` aplicado |
| Migracoes consistentes | `makemigrations --check` → *No changes detected* |
| Comando de migracao de dados | `manage.py tenantizar` executado (rede padrao + matriz) |
| CI | `.github/workflows/ci.yml` (lint, testes com Postgres, migracao pendente, check) |
| Documentacao | `docs/ARQUITETURA.md`, `API_HERMES.md`, `MIGRACAO.md`, `PLANO_TESTES.md`, `OPERACAO.md` |

## Bug real encontrado e corrigido pelo caminho

A permissao de escopo da API (`EscopoNecessario`) lia `escopo_recurso`/`escopos_por_acao` **dela
mesma** em vez de ler do *view*. Resultado: **nenhum escopo era exigido** — um token somente-leitura
conseguia escrever. Foi o teste `test_token_sem_escopo_de_escrita_recebe_403` que pegou; a correcao
(ler do `view`) e os testes de leitura/escrita negada entraram junto.

Tambem corrigido: queryset capturado no atributo de classe (congelava o escopo no import e
desligava o isolamento por requisicao) — agora resolvido em `get_queryset`.

## O que NAO foi feito (e por que)

O PRD tem 9 fases; esta entrega cobre **Fase 0 inteira** e o **nucleo da Fase 1**. Ficam para as
proximas janelas, na ordem do PRD:

* Fase 1 completa: telas gravando com unidade explicita, rotas por rede (`/a/<slug>/`),
  `rede` obrigatoria no banco;
* Fase 2: painel administrativo novo do tenant (as telas de §21 do PRD);
* Fase 3/4: pacotes, assinatura, cobranca da plataforma (Asaas), limites e inadimplencia;
* Fase 6/7/8: repasses de franquia, webhooks de saida, `dry_run`, jobs assincronos e paridade
  competitiva.

## Como rodar agora

```bash
cd /home/manoperalta/academia-saas
make subir      # postgres + imagem de dev
make migrar     # aplica as migrations
make test       # 50 testes
make lint       # ruff
```

## Riscos e pendencias tecnicas registradas

1. `TenantModel.rede` e anulavel de proposito — tornar obrigatoria **depois** que todas as telas
   gravarem com contexto (ver `docs/ARQUITETURA.md`).
2. Credenciais de terceiros em texto no banco (SMTP/WhatsApp/gateway) — cifrar.
3. Testes de caracterizacao sao de fumaca por rota, nao de regra de negocio detalhada; nas proximas
   fases, cobrir regra por regra antes de refatorar cada tela.
4. `api.ApiToken` nao tem allowlist de IP nem idempotencia implementadas (previstas no PRD §20).
