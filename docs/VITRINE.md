# Site público, cadastro self-service e importação (Fase 4)

## Como o cliente entra sozinho (fluxo do PRD 11.1)

```
/ (site) → /planos/ → /cadastro/?plano=<codigo>
      ↓ dados da academia (CNPJ validado, slug verificado ao vivo, duplicidade recusada)
      ↓ escolha: "Testar 14 dias grátis"  ou  "Assinar agora com Pix"
[Provisionamento transacional] Rede + Assinatura + dono + Configuracao + IdentidadeVisual
      ↓ falhou? nada fica pela metade (rollback) e o motivo aparece no formulário
E-mail de boas-vindas → definir a própria senha → painel operando
```

- **Nada de senha por e-mail**: o dono recebe um convite com token de 7 dias e define a senha ele mesmo.
- **CNPJ**: validado por dígitos verificadores, aceitando o **formato alfanumérico** (2026) e recusando CNPJ repetido.
- **Slug**: verificação ao vivo (`/api/slug/`), lista de palavras reservadas e regra de hífen.
- **Trial**: 14 dias (configurável), com avisos em T-7, T-3 e T-1 pela régua de cobrança.
- Site: `/` (institucional, com planos vindos do banco), `/planos/` (comparativo de módulos),
  `/ajuda/` (central de ajuda inicial), `/contato/` (formulário que envia e-mail para o financeiro).
  A landing antiga continua acessível em `/academia/`.

## Importação de alunos e professores (RF-PLT-034)

Em **Alunos → Importar CSV** (`/gestao/importar/`), em dois tempos:

1. **Conferência** (nada é gravado): total de linhas, quantas serão criadas/atualizadas/ignoradas
   e a lista de problemas **por linha** (sem nome, e-mail inválido, repetido no próprio arquivo,
   duplicado na base, limite do pacote).
2. **Confirmação**: grava apenas o que passou; tudo fica na auditoria.

- Colunas aceitas (com sinônimos): `nome`, `email`, `telefone`, `cpf`, `nascimento`, `status`.
  Só `nome` é obrigatório; separador `;` ou `,`; datas em `dd/mm/aaaa`.
- **Respeita o teto do pacote**: o excedente é recusado linha a linha com o motivo, e o teto nunca
  é ultrapassado.
- "Atualizar quem já existe" compara por e-mail e CPF.
- `Alunos → Importar CSV → Baixar modelo` gera o CSV de exemplo pronto para preencher.
- Limite de 5.000 linhas por arquivo (dividir em partes acima disso).

## E-mails do ciclo de vida

- **Boas-vindas** no cadastro (com o link de primeiro acesso e a fatura/Pix quando for o caso).
- **Trial**: T-7, T-3, T-1.
- **Cobrança**: D-3, D0, D+1, D+5, D+10 (bloqueio) e D+30 (suspensão).
- Envio pela configuração de e-mail do projeto (env `EMAIL_*`); os avisos do tenant usam o SMTP
  da própria academia quando ela configura.

## Troca de pacote pelo cliente

Em **Meu plano**: upgrade vale na hora com cobrança proporcional (Pix na tela) e downgrade fica
agendado para a renovação, avisando quando o uso já está acima do novo limite. **Nada é apagado**;
o que acontece é bloqueio de cadastro novo até regularizar.

## O que ficou de fora (e por quê)

- **Login do aluno/professor criado na importação**: hoje a importação traz os cadastros; criar
  logins em massa depende do portal do aluno (Fase 5) e do fluxo de "esqueci minha senha".
- **Verificação de e-mail por link** e **rate limit/captcha no cadastro público**: antes de abrir o
  cadastro ao mundo (hoje o formulário é usado pelo time e em demonstração).
- **Nota fiscal** (RF-PLT-024) segue dependente da decisão contábil (§16.5).
