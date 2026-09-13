# Segurança, privacidade e operação (Fase 5)

## Acesso

- **Login em `/entrar/`** com rate limit: e-mail e IP contam falhas (15 min de janela) e o bloqueio
  é progressivo — 3 falhas → 1 min, 5 → 5 min, 10 → 30 min. Cada tentativa fica registrada.
- **2FA (TOTP)** com app autenticador (Google Authenticator, Authy, 1Password): 6 dígitos, janela de
  30s com tolerância de ±1. **8 códigos de recuperação** de uso único, guardados em hash.
  - **Dono/equipe da academia**: opcional, recomendado.
  - **Equipe da SafeStack**: **obrigatório** — sem o fator ativo, o painel da plataforma redireciona
    para a ativação.
  - A sessão vale 12h depois de confirmar o código.
- Sessão segura (`Secure`, `HttpOnly`, `SameSite`) atrás do proxy com `SECURE_PROXY_SSL_HEADER`.

## Mídia isolada por cliente (RNF-010)

- Arquivos vivem em `media/redes/<slug-do-cliente>/...`; **nada é servido sem sessão**.
- Toda entrega passa por `/midia/<caminho>`, que confere se o arquivo pertence a um cliente do
  usuário logado; caminho com `..` é recusado e quem não tem vínculo recebe 404.
- Atrás do nginx, respondemos com `X-Accel-Redirect` (o nginx entrega o arquivo, o Python só autoriza).
  Basta manter `/media/` **fora** do `location` público do nginx.
- Comando para arrumar a casa: `python manage.py namespace_midia` (simula) e `--aplicar` (move e
  reescreve os caminhos no banco).

## Domínio próprio e subdomínio (RF-PLT-050…052)

- Todo cliente já atende em `https://<slug>.dominio-base/gestao/` (resolução por **Host**, antes de
  sessão e vínculo).
- Domínio próprio: o cliente cadastra em **Meu painel → Domínio e endereço**; o sistema mostra os
  registros (A, TXT `_academia-verificacao`, CNAME opcional) e a alternativa do arquivo
  `/.well-known/academia-verificacao.txt`.
- A verificação tenta TXT (com `dnspython`, se instalado) e depois HTTP; o resultado aparece em
  linguagem de cliente ("Aguardando propagação do DNS…").
- Depois de verificado, o certificado é emitido; **se a emissão falhar, o painel da plataforma tem
  "reemitir TLS"** — o proxy não repete o pedido sozinho após erro de validação ACME (a origem do
  "sua conexão não é particular").
- `python manage.py verificar_dominios --emitir` (cron diário) reconfere e reemite.

## Observabilidade (RNF-008)

- Log com contexto em cada linha: `rede=<id> user=<usuario>` (filtro aplicado ao handler existente).
- Métricas por cliente/hora: requisições, 4xx, 5xx, tempo médio e pior tempo (`MetricaTenant`).
- Erros 5xx guardados com rota, tipo, mensagem e trecho de traceback (`ErroTenant`), **deduplicados
  por 5 minutos** para não inundar a lista.
- Alertas: 5xx acima do limiar por cliente, backup ausente/falho/sem verificação e pedidos de
  titular vencidos. Página pública simples em `/status/`.
- Cron sugerido: `agregar_metricas` de hora em hora.

## Backup e restauração (RNF-005)

- `backup_banco`: usa `pg_dump` quando disponível, senão faz o dump lógico (JSON gzipado) — sempre com
  **sha256** e registro em `RegistroBackup`.
- `verificar_backup`: conferência por restauração de teste (arquivo, hash e conteúdo legível);
  o comando de backup já verifica em seguida.
- `exportar_tenant <slug>`: **restauração pontual de um cliente** (JSON com todas as tabelas dele),
  sem afetar os demais.
- Retenção: 7 diários + 4 semanais (`--retencao-valendo` aplica de verdade).
- Backups grandes devem ir para o Drive e sair da VPS (regra da infraestrutura).

## LGPD (RNF-006)

- Papéis: a **academia é controladora**, a SafeStack é **operadora** — está na página `/privacidade/`.
- **Exportar titular**: ZIP com `dados.json` (cadastro, pagamentos, agendamentos, ficha) + CSV.
- **Anonimizar titular**: exige digitar `ANONIMIZAR`; limpa dados pessoais e a ficha, desativa o
  login e **preserva os pagamentos** pelo prazo fiscal, com registro na auditoria.
- **Pedidos de titular**: registro com prazo legal de 15 dias, controle de atraso e resposta.
- **Dado sensível**: a ficha de saúde só é acessível a quem tem permissão por papel e **toda leitura
  é registrada** (`AcessoDadoSensivel`) — inclusive nunca aparece no acesso de suporte.
- **Retenção**: `seed_governanca` cria as regras (tentativas de login 180d, erros 90d, métricas 400d,
  acessos a dado sensível e pedidos 5 anos, pagamentos conservados por obrigação fiscal) e
  `aplicar_retencao` mostra (ou executa com `--aplicar`) o expurgo.
