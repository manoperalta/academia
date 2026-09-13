# Operacao

## Configuracao por ambiente

`app/settings.py` le `DJANGO_ENV` e carrega `app/settings_env/{dev,prod,test}.py`
(padrao: `prod`). Nada de segredo no codigo: tudo por `.env` (ver `.env.example`).

| Variavel | Para que serve |
|---|---|
| `DJANGO_ENV` | `dev`, `test` ou (padrao) `prod` |
| `DJANGO_SECRET_KEY` | chave criptografica — **obrigatoria em producao** |
| `DJANGO_DEBUG` | `1` liga o debug (em `prod.py` e forcado `False`) |
| `DJANGO_DEBUG_TOKEN` | token que libera as paginas de debug no laboratorio |
| `DATABASE_URL` | `postgres://usuario:senha@host:5432/banco` (sem ela, SQLite local) |
| `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` | dominios servidos atras do Traefik |
| `DJANGO_EMAIL_*` | SMTP de saida (em dev vai para o console) |

## Saude e diagnostico

* `GET /api/v1/estado/` — versao da API e recursos (200 mesmo anonimo).
* `GET /api/v1/sessao/` — rede, unidade e escopos da credencial usada.
* Logs: cada linha carrega `rede=<id>` (filtro `core.logging_filters.FiltroRede`), o que permite
  separar cliente por cliente.
* Auditoria: `/api/v1/auditoria/` (escopo `auditoria:read`) — toda escrita por API fica registrada.

## Backup

* Banco: `pg_dump` diario + retencao de 30 dias; **restauracao testada mensalmente**.
* Midia: snapshot do volume `media/` (nomespaco por rede e o proximo passo).
* Backup grande vai para o Drive e sai do disco da VPS.

## Cuidados conhecidos

1. **`DJANGO_SECRET_KEY`** deve estar definida em producao: sem ela o projeto usa a chave insegura
   de fallback e os logs avisam (`app/settings_env/prod.py`).
2. Credenciais de terceiros (SMTP, WhatsApp, gateway) estao em texto no banco — cifrar e o
   proximo item de seguranca.
3. `docker restart` **nao** rele `.env`: ao mudar variavel, recrie o container (`docker compose up -d`).
4. Nunca subir com `DEBUG=1` exposto: o middleware de debug libera apenas com `DJANGO_DEBUG_TOKEN`.
