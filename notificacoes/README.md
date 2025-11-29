# Sistema de Notificações por E-mail

## Configuração

### 1. Configurar SMTP no Django Admin

Acesse: `/admin/notificacoes/configuracaoemail/`

Configure os seguintes campos:
- **Servidor SMTP (Host)**: Ex: `smtp.gmail.com`, `smtp-mail.outlook.com`
- **Porta**: `587` (TLS) ou `465` (SSL)
- **Usuário/Email**: Seu e-mail completo
- **Senha**: Senha do e-mail ou senha de aplicativo
- **Usar TLS**: Marque se usar porta 587
- **Usar SSL**: Marque se usar porta 465
- **Nome do Remetente**: Nome que aparecerá no e-mail
- **Email do Remetente**: E-mail que aparecerá como remetente
- **Configuração Ativa**: Marque para ativar

### 2. Exemplo de Configuração Gmail

- Host: `smtp.gmail.com`
- Porta: `587`
- Usar TLS: ✓
- Username: `seu-email@gmail.com`
- Senha: Use uma "Senha de App" (não a senha normal)
  - Gere em: https://myaccount.google.com/apppasswords

## Uso

### Criar Notificação via Dashboard

1. Acesse o Dashboard Admin
2. Clique em "Criar Notificação" no card de Notificações
3. Preencha:
   - **Assunto**: Título do e-mail
   - **Mensagem**: Corpo do e-mail
   - **Enviar para todos**: Marque para enviar a todos os usuários ativos
   - **Destinatários**: Ou informe e-mails específicos separados por vírgula
4. Clique em "Enviar Notificação"

### Gerenciar Notificações no Admin

Acesse: `/admin/notificacoes/notificacao/`

Você pode:
- Ver histórico de notificações enviadas
- Ver status (Pendente, Enviado, Falha)
- Ver logs de erro
- Reenviar notificações que falharam (selecione e use a action "Enviar notificações selecionadas")

## Estrutura

- **ConfiguracaoEmail**: Modelo singleton para configurações SMTP
- **Notificacao**: Registro de cada notificação com status e log
- **NotificacaoForm**: Formulário com opção de enviar para todos
- **criar_notificacao**: View para criar e enviar notificações

## Segurança

- Apenas administradores e staff podem criar notificações
- Senhas são armazenadas em texto plano no banco (considere usar variáveis de ambiente em produção)
- Recomenda-se usar senhas de aplicativo ao invés de senhas principais
