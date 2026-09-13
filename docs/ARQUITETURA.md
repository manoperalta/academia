# Arquitetura multi-tenant (rede / unidade)

## Hierarquia

```
Plataforma (SafeStack)
└── Rede  (tenant: dono dos dados, do contrato e do pagamento)   core.Rede
    └── Unidade (matriz, filial ou franqueada)                   core.Unidade
        ├── Equipe    (usuario + papel, por unidade)             core.VinculoUsuario
        ├── Alunos / professores / aulas / paineis / financeiro  (TenantModel)
        └── Token de API (escopo + recorte de unidade)           api.ApiToken
```

* **A rede é o limite de isolamento.** Nenhum dado de negócio pode existir sem `rede`.
* **A unidade é recorte de negócio**, não de isolamento: quem opera o dia a dia filtra por
  unidade; quem administra a rede enxerga todas.
* **A plataforma** enxerga todas as redes apenas por código explícito (`Model.todos`), sempre auditado.

## Onde está cada coisa

| Caminho | Papel |
|---|---|
| `core/` | Rede, Unidade, VinculoUsuario, bases abstratas, managers, contexto, middleware, mixins de CBV |
| `api/` | API REST (DRF): token de servico com escopos, auditoria, viewsets, erros RFC 7807, OpenAPI |
| `app/settings_env/` | `base.py` (comum), `dev.py`, `prod.py`, `test.py`; `app/settings.py` escolhe por `DJANGO_ENV` |
| `tests/` | Suite de isolamento, caracterizacao e apoio (preenchimento generico de modelos) |

## Isolamento em camadas (defesa em profundidade)

1. **Manager escopado** — `Model.objects` filtra pela rede do contexto. `Model.todos` nao filtra
   (uso restrito ao codigo da plataforma).
2. **Contexto de requisicao** — `core.context` (thread-local) com `rede`, `unidade` e `usuario`;
   instalado pelo `core.middleware.RedeMiddleware`.
3. **Base do modelo** — `TenantModel.save()` preenche `rede`/`unidade` a partir do contexto quando
   nao foram informadas (e o que mantem as telas atuais funcionando durante a transicao).
4. **Mixins de CBV** — `RedeRequiredMixin`, `UnidadeScopedMixin`, `EscritaPermitidaMixin`.
5. **Permissao de API** — `EscopoNecessario` exige o escopo **declarado no view**
   (`escopo_recurso`/`escopos_por_acao`) e `RedeNoContexto` exige rede resolvida.
6. **Testes obrigatorios** — `tests/test_isolamento.py` e `api/tests/test_api.py` provam que
   uma rede nao ve, nao edita e nao exclui dado de outra; nem por URL direta.

## Decisao consciente: `rede` anulavel nesta fase

`TenantModel.rede` e `null=True` **de proposito** nesta etapa: a base atual foi escrita para uma
unica academia e ainda existem telas gravando sem contexto explicito. O caminho e:

1. *agora* — campo anulavel + preenchimento pelo contexto + `manage.py tenantizar` para etiquetar o
   que ja existia;
2. *depois* — todas as telas gravando com `services` (rede/unidade explicitas) e entao
   `AlterField(null=False)`, com o teste de isolamento verde a cada passo.

Tornar obrigatorio antes disso quebraria a operacao sem necessidade.

## RBAC

`core.VinculoUsuario` liga usuario × rede × (unidade opcional) × papel. `unidade=None` significa
"vale para a rede inteira" (admin da rede, financeiro, auditor). Papeis em `core/papeis.py`.
O mesmo usuario pode ter papeis diferentes em redes diferentes.

## O que ainda NAO existe (proximas fases do PRD)

* rotas por rede (`/a/<slug>/`) e subdominio com certificado;
* painel administrativo novo (telas de §21 do PRD) e o painel da plataforma;
* pacotes, assinatura e cobranca da plataforma (Asaas), limites de pacote e bloqueio por inadimplencia
  (o `RedeMiddleware` ja aplica o status da rede, mas nao existe a cobranca);
* repasses/royalties (§18), webhooks de saida, `dry_run`, jobs assincronos (Celery) e
  administracao do dia a dia por conversa (os endpoints base ja existem);
* cifragem de credenciais de terceiros (SMTP/WhatsApp/gateway) hoje em texto no banco.
