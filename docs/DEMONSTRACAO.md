# Demonstracao publicada

A demonstracao da fase 8 vive em **https://academia.safestack.com.br/demo/** — mesmo dominio da
producao, caminho diferente, **banco diferente** (`academia_demo`) e **cookie diferente**
(`sessionid_demo`, com caminho `/demo`). Entrar na demonstracao nao derruba nem substitui a sessao da
producao.

## Logins (senha unica `Demo@2026`)

- **plataforma (SafeStack)**: dono@safestack.com.br
- **admin da rede**: rede@demonstracao.com.br
- **gestor da unidade**: unidade@demonstracao.com.br
- **professor**: professor@demonstracao.com.br
- **aluno (PWA)**: aluno@demonstracao.com.br

## Dados da demonstracao

Rede "Rede Demonstracao" com duas unidades (Centro, propria; Zona Norte, franqueada), 13 alunos com
ficha de saude, turma das 19h com 7 agendamentos (5 presencas e 2 faltas), 39 pagamentos em tres
competencias (3 em atraso), 3 cobrancas na regua, 1 treino com 4 exercicios, 2 avaliacoes fisicas
(a evolucao aparece calculada) e 1 lead no funil de captacao.

## Como funciona

- **Container**: `academia_demo_web`, definido em `docker-compose.demo.yml`, somado ao compose de dev
  (`docker compose -f docker-compose.dev.yml -f docker-compose.demo.yml up -d demo`). Publica apenas
  em `127.0.0.1:8004`.
- **Prefixo `/demo`**: configurado em `app/settings_env/demo.py` (`FORCE_SCRIPT_NAME`) e destacado pelo
  uWSGI (`--mount /demo=app.wsgi:application`). Sem o `--mount`, o Django recebe `/demo/` e devolve
  404 — foi o primeiro erro que apareceu.
- **Tunel reverso**: `autossh -R 18084:127.0.0.1:8004 vps-jogo` na maquina i3 (nao ha systemd para
  ele: e um processo de demonstracao).
- **Traefik** (VPS): roteador `academia-demo` com `Host(academia.safestack.com.br) && PathPrefix(/demo)`
  e prioridade 100, apontando para `http://127.0.0.1:18084`. Copia do arquivo anterior fica em
  `/docker/traefik/dynamic.yml.bak-*`.
- **Sem 2FA**: a demonstracao retira o middleware de dois fatores e o `EXIGIR_2FA_PLATAFORMA`. A
  producao mantem os dois.

## Povoar de novo

```bash
cd /home/manoperalta/academia-saas
docker compose -f docker-compose.dev.yml -f docker-compose.demo.yml run --rm -T demo \
  python manage.py shell -c "import scripts.demo_publica"
docker compose -f docker-compose.dev.yml -f docker-compose.demo.yml run --rm -T demo \
  python manage.py shell -c "import scripts.smoke_demo2"   # confere as telas por perfil
```

## Desligar

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.demo.yml stop demo
pkill -f "18084:127.0.0.1:8004"          # derruba o tunel
python3 /root/traefik_demo.py --remover  # (ou devolver o backup do dynamic.yml)
```

Producao nao usa nada disto: `academia_web` e `academia_nginx` seguem servindo
`academia.safestack.com.br` pelo caminho de sempre.
