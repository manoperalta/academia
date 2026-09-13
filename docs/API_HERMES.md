# API REST: administracao remota (Hermes e integracoes)

Base: `https://<host>/api/v1/` · Documentacao viva: `/api/docs/` (Swagger) e `/api/redoc/`

## 1. Criar um token com escopo

No painel (ou no admin, por enquanto), crie o token escolhendo **rede**, **unidade** (opcional) e
**escopos**. O segredo aparece **uma unica vez**, no formato `prefixo.segredo`.

Escopos disponiveis em `api/escopos.py` (ex.: `alunos:read`, `alunos:write`, `financeiro:write`,
`aulas:write`, `auditoria:read`, `plataforma:write`).

## 2. Usar

```bash
TOKEN="abc123def456.SEGREDO_AQUI"

# quem sou eu nesta chamada (rede, unidade, escopos)
curl -s -H "Authorization: Token $TOKEN" https://academia.exemplo/api/v1/sessao/

# estado da instalacao (versao, recursos) -- nao exige token
curl -s https://academia.exemplo/api/v1/estado/

# listar alunos da unidade do token (paginado)
curl -s -H "Authorization: Token $TOKEN" \
  "https://academia.exemplo/api/v1/alunos/?page_size=50&ordering=-id"

# buscar por nome/e-mail
curl -s -H "Authorization: Token $TOKEN" \
  "https://academia.exemplo/api/v1/alunos/?search=maria"

# criar aluno
curl -s -X POST -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
  -d '{"nome":"Maria","telefone_user":"51999999999"}' \
  https://academia.exemplo/api/v1/alunos/

# arquivar (soft delete) e restaurar
curl -s -X DELETE -H "Authorization: Token $TOKEN" https://academia.exemplo/api/v1/alunos/123/
curl -s -X POST   -H "Authorization: Token $TOKEN" https://academia.exemplo/api/v1/alunos/123/restaurar/

# auditoria da rede (quem fez o que)
curl -s -H "Authorization: Token $TOKEN" \
  "https://academia.exemplo/api/v1/auditoria/?acao=criar&page_size=20"
```

## 3. Erros (RFC 7807) com codigo estavel

```json
{
  "type": "https://academia.safestack.com.br/erros/escopo_insuficiente",
  "title": "Acesso negado",
  "status": 403,
  "detail": "Token sem o escopo 'alunos:write'. Escopos deste token: ['alunos:read'].",
  "codigo": "escopo_insuficiente"
}
```

Codigos: `escopo_insuficiente`, `nao_autenticado`, `dados_invalidos`, `limite_pacote_atingido`,
`academia_bloqueada`, `nao_encontrado`, `erro_interno`. **Erro previsivel nunca vira 500.**

## 4. Regras de uso por agente (o que o Hermes precisa respeitar)

1. **Token por finalidade**, com o menor escopo possivel (ex.: um token so de cobranca).
2. **Nada de acao externa sem confirmacao**: disparo de mensagem em massa, emissao de cobranca,
   suspensao de academia e alteracao de preco exigem confirmacao explicita do dono.
3. **Idempotencia**: repetir a mesma chamada de criacao nao pode duplicar dado (por token de
   idempotencia -- ver §20.4 do PRD; hoje o `POST` duplica por desenho).
4. **Lote**: preferir varias chamadas pequenas com relatorio do que uma gigante; conferir o
   resultado item a item.
5. **Auditoria sempre ligada**: toda escrita por API grava `RegistroAuditoria` com o token, a
   operacao e o resumo do que mudou.

## 5. Isolamento (nao ignore)

O token carrega a rede (e a unidade). **O cliente nao escolhe a rede no corpo da requisicao**:
`rede` e `unidade` sao campos somente leitura, sempre herdados do token. Tentar acessar um id de
outra rede devolve **404** -- nao "403 com o dado".
