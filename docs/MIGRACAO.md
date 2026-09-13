# Como aplicar esta versao (rede/unidade) numa instalacao que ja opera

> O schema e **aditivo**: todos os campos novos sao anulaveis, entao a versao antiga do codigo
> continua funcionando depois da migracao (rollback seguro).

## Antes de tudo

1. Backup do banco e da midia, **com teste de restauracao**:
   `sqlite3 db.sqlite3 ".backup backup.db"` (ou `pg_dump`) e um snapshot de `media/`.
2. Conferir variaveis de ambiente (ver `docs/OPERACAO.md`): `DJANGO_ENV`, `DJANGO_SECRET_KEY`,
   `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`.

## Passos

```bash
# 1) Postgres no ar (a suite de testes e a producao alvo usam Postgres)
#    docker-compose.dev.yml sobe um Postgres de desenvolvimento na porta 5433.

# 2) Migrar o schema (aditivo: cria core_*, api_* e as colunas rede/unidade/arquivado_em)
python manage.py migrate

# 3) Etiquetar os dados que ja existiam com a rede padrao (idempotente)
python manage.py tenantizar --slug padrao --nome "Minha Academia" --dry-run   # conferir
python manage.py tenantizar --slug padrao --nome "Minha Academia"

# 4) Arquivos estaticos e checagem
python manage.py collectstatic --noinput
python manage.py check
```

## Verificacao depois de subir

* `pytest tests/test_isolamento.py api/tests/test_api.py` (ou a suite inteira) — **precisa passar**;
* login de um usuario real e navegacao pelas telas principais (a suite `tests/test_caracterizacao.py`
  cobre as rotas, mas nao substitui um olhar humano);
* `/api/v1/estado/` respondendo 200.

## Rollback

1. Volte o codigo para o commit anterior (o container usa volume, entao basta `git checkout` e
   recarregar o uwsgi);
2. **Nao** e necessario reverter o schema: as colunas novas ficam ignoradas pela versao antiga;
3. Se quiser limpar: `python manage.py migrate <app> <migracao_anterior>` por app (as migrations
   novas sao apenas `AddField`).

## Ordem recomendada para producao

1. Homologacao primeiro (`academia-saas` numa porta/tunel separado) — treinar a migracao de dados
   medindo o tempo;
2. Janela de manutencao curta em producao;
3. Migrar, `tenantizar`, subir a versao nova, conferir contagens (alunos, professores, pagamentos,
   agendamentos) contra o backup.
