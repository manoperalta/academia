# Sistema de Gerenciamento de Academia - Projeto Completo

## 🎯 Sobre o Projeto

Sistema completo de gerenciamento de academia desenvolvido em Django com:
- ✅ Dashboard administrativo com gráficos financeiros e aniversariantes
- ✅ Landing page moderna com animações e efeitos visuais
- ✅ Gestão de alunos, professores e aulas
- ✅ Sistema de pagamentos e planos
- ✅ Notificações personalizáveis por e-mail
- ✅ Relatórios e estatísticas em tempo real

## 🚀 Instalação Rápida

### 1. Extrair o Projeto
```bash
unzip projeto_academia_completo.zip
cd projeto_academia_completo
```

### 2. Criar Ambiente Virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install django pillow python-dateutil
```

### 4. Aplicar Migrações
```bash
python manage.py migrate
```

### 5. Criar Superusuário
```bash
python manage.py createsuperuser
```

### 6. Executar o Servidor
```bash
python manage.py runserver
```

### 7. Acessar o Sistema
- **Landing Page**: http://localhost:8000/
- **Admin**: http://localhost:8000/admin/
- **Dashboard**: http://localhost:8000/dashboard/

## 📋 Configurações Importantes

### Configurar E-mail (settings.py)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'seu-email@gmail.com'
EMAIL_HOST_PASSWORD = 'sua-senha-app'
DEFAULT_FROM_EMAIL = 'seu-email@gmail.com'
```

### Configurar Academia
1. Acesse: http://localhost:8000/admin/academia/configuracao/
2. Configure:
   - Nome da academia
   - Endereço e dados
   - Dias de alerta de vencimento (padrão: 5)
   - Mensagem de pagamento atrasado
   - Mensagem de aniversário

### Upload de Logo e Favicon
1. Acesse: http://localhost:8000/admin/academia/identidadevisual/
2. Faça upload do logotipo e favicon

## 🎨 Nova Landing Page

A landing page foi completamente redesenhada com:

### Recursos Visuais
- ✨ Animações suaves ao scroll (AOS)
- 🎨 Gradientes modernos inspirados no GitHub
- 🌊 Background animado com orbs flutuantes
- 💫 Cards flutuantes com estatísticas
- 📱 Design totalmente responsivo

### Seções
1. **Hero Section** - Apresentação principal com CTA
2. **Features** - 6 recursos principais com ícones
3. **Stats** - Estatísticas animadas com contadores
4. **CTA Final** - Chamada para ação
5. **Footer** - Rodapé minimalista

### Imagens Incluídas
- `hero-gym.webp` - Imagem principal do hero
- `team-gym.webp` - Imagem de equipe
- `training.jpg` - Imagem de treino

Localização: `/static/images/landing/`

## 📊 Dashboard Administrativo

### Gráfico Financeiro
- **Verde**: Usuários em dia
- **Amarelo**: Alerta (próximo ao vencimento)
- **Vermelho**: Atrasados

**Interatividade**: Clique na área vermelha para abrir modal de notificação

### Aniversariantes do Dia
- Lista de aniversariantes
- Botão para enviar mensagem personalizada
- Placeholders: `{academia}` e `{nome}`

## 🔧 Estrutura do Projeto

```
projeto_academia_completo/
├── academia/           # App principal (configurações)
├── dashboard/          # Dashboard administrativo
├── usuarios/           # Gestão de usuários
├── financeiro/         # Pagamentos e planos
├── professores/        # Gestão de professores
├── aulas/              # Gestão de aulas
├── painel/             # Painel de aulas
├── agendamento/        # Sistema de agendamento
├── notificacoes/       # Sistema de notificações
├── relatorios/         # Relatórios
├── accounts/           # Autenticação
├── static/             # Arquivos estáticos
│   └── images/
│       └── landing/    # Imagens da landing page
├── templates/          # Templates globais
├── db.sqlite3          # Banco de dados
└── manage.py
```

## 🎯 Funcionalidades Principais

### 1. Dashboard Administrativo
- Gráfico circular de situação financeira
- Contador de aniversariantes do dia
- Envio de notificações personalizadas
- Cards de gestão rápida

### 2. Gestão de Usuários
- Cadastro de alunos
- Perfis com foto
- Status (Ativo/Inativo)
- Histórico de pagamentos

### 3. Sistema Financeiro
- Planos personalizáveis (semanal, mensal, semestral, anual)
- Controle de pagamentos
- Integração com gateway (PagBank)
- Alertas de vencimento

### 4. Gestão de Professores
- Cadastro de professores
- Status de aprovação
- Vinculação com aulas

### 5. Sistema de Aulas
- Criação de aulas
- Agendamento
- Painéis de horários

### 6. Notificações
- E-mail para usuários atrasados
- E-mail para aniversariantes
- Mensagens personalizáveis

## 🌐 URLs Principais

```
/                           # Landing page
/login/                     # Login
/register/                  # Registro
/dashboard/                 # Dashboard principal
/admin/                     # Django Admin
/usuarios/                  # Lista de usuários
/professores/               # Lista de professores
/aulas/                     # Lista de aulas
/financeiro/pagamentos/     # Pagamentos
/relatorios/                # Relatórios
/notificacoes/              # Criar notificação
```

## 🎨 Personalização

### Cores da Landing Page
Edite as variáveis CSS em `landing_page.html`:
```css
:root {
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    --accent-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}
```

### Trocar Imagens
Substitua os arquivos em `/static/images/landing/`:
- `hero-gym.webp` - Imagem principal
- `team-gym.webp` - Imagem de equipe
- `training.jpg` - Imagem de treino

## 📱 Responsividade

O sistema é totalmente responsivo e funciona em:
- 📱 Mobile (smartphones)
- 📱 Tablet
- 💻 Desktop
- 🖥️ Telas grandes

## 🔒 Segurança

- Autenticação obrigatória
- Permissões por tipo de usuário
- CSRF protection
- Validação de dados

## 📝 Notas Importantes

1. **Banco de Dados**: O projeto inclui `db.sqlite3` com dados de exemplo
2. **Imagens**: As imagens da landing page estão incluídas
3. **Migrations**: Todas as migrations já foram aplicadas
4. **Configurações**: Configure o e-mail antes de usar notificações

## 🆘 Problemas Comuns

### Erro ao enviar e-mail
- Verifique as configurações de SMTP
- Use senha de app do Gmail (não a senha normal)

### Imagens não aparecem
- Execute: `python manage.py collectstatic`
- Verifique se `DEBUG = True` em desenvolvimento

### Erro de migração
```bash
python manage.py migrate --run-syncdb
```

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs do Django
2. Consulte a documentação oficial: https://docs.djangoproject.com/
3. Revise os arquivos de configuração

## 🎉 Pronto!

Seu sistema de academia está pronto para uso. Acesse a landing page e explore todas as funcionalidades!

**Desenvolvido com ❤️ usando Django**
