# Plano de testes

## Como rodar

```bash
make test          # suite completa (Postgres do docker-compose.dev.yml)
make lint          # ruff check + format
pytest -m isolamento      # so o que protege o isolamento entre clientes
pytest -m caracterizacao  # so o que congela o comportamento atual
pytest tests/manual_dbg.py -s -q   # diagnostico manual (nao roda na suite)
```

## Camadas

| Camada | Arquivo | O que garante |
|---|---|---|
| Estrutura | `tests/test_isolamento.py` | todo modelo de negocio herda de `TenantModel`; `rede` existe, indexada; nenhum modelo ficou fora |
| Escopo | `tests/test_isolamento.py` | com contexto de rede, `objects` nao enxerga outra rede; `todos` enxerga; unidade recorta |
| Caracterizacao | `tests/test_caracterizacao.py` | 14 rotas publicas e internas respondem sem 500, anonimo e logado; login cria sessao; admin abre |
| API | `api/tests/test_api.py` | token invalido 401; escopo insuficiente 403 (leitura e escrita); rede do token manda; **isolamento por API** (lista so a propria rede, id de outra rede 404); auditoria de escrita; revogacao |
| Integridade | `api/tests/test_api.py` | registro de auditoria e append-only (nao aceita alteracao) |

## Regras

1. Teste que falha **bloqueia** o merge: isolamento e o primeiro da fila.
2. Nenhuma funcionalidade nova sem teste (ver "definicao de pronto" em §19.6 do PRD).
3. Cobertura minima do nucleo (`core`, `api`) cresce a cada fase: hoje o piso do CI e 60%,
   a meta e 85%.
4. Teste de isolamento novo **por recurso** sempre que entrar um modelo novo (a suite descobre
   automaticamente os modelos de rede e cobra que todos tenham o campo).
