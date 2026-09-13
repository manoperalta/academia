# 🏋️ Sistema de Gerenciamento de Academia - FitPro

Sistema completo de gerenciamento de academia desenvolvido em Django com interface moderna e funcionalidades avançadas.

## ✨ Funcionalidades

### 🎨 Landing Page Moderna
- Design inspirado no GitHub com animações suaves
- Background animado com orbs flutuantes
- Seções de features, estatísticas e CTA
- 100% responsivo

### 📊 Dashboard Administrativo
- **Gráfico Financeiro Circular**: Visualização de pagamentos (em dia, alerta, atrasados)
- **Aniversariantes do Dia**: Lista e envio de mensagens personalizadas
- **Notificações por E-mail**: Envio automático para usuários atrasados
- **Estatísticas em Tempo Real**: Métricas importantes do negócio

### 👥 Gestão Completa
- Cadastro de alunos e professores
- Sistema de pagamentos e planos
- Agendamento de aulas
- Relatórios detalhados
- Notificações personalizáveis

## 🚀 Instalação Rápida (Método 1 - Recomendado)

### Linux/Mac
```bash
# 1. Extrair o projeto
unzip projeto_academia_funcional.zip
cd projeto_academia_funcional

# 2. Executar script de inicialização
./start.sh
```

### Windows
```bash
# 1. Extrair o projeto
# 2. Abrir terminal no diretório
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## 📦 Instalação Manual (Método 2)

### 1. Criar Ambiente Virtual
```bash
python3 -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 3. Aplicar Migrações
```bash
python manage.py migrate
```

### 4. Criar Superusuário
```bash
python manage.py createsuperuser
```

### 5. Executar Servidor
```bash
python manage.py runserver
```

## 🔑 Credenciais Padrão

Se você usou o script `start.sh`, as credenciais já foram criadas:

- **Usuário**: admin
- **Senha**: admin123

## 🌐 URLs Importantes

Após iniciar o servidor, acesse:

- **Landing Page**: http://localhost:8000/
- **Dashboard**: http://localhost:8000/dashboard/
- **Admin Django**: http://localhost:8000/admin/
- **Login**: http://localhost:8000/login/
- **Registro**: http://localhost:8000/register/

## 📋 Estrutura do Projeto

```
projeto_academia_funcional/
├── academia/              # Configurações da academia
├── accounts/              # Autenticação e usuários
├── agendamento/           # Sistema de agendamento
├── aulas/                 # Gestão de aulas
├── dashboard/             # Dashboard administrativo
├── financeiro/            # Pagamentos e planos
├── notificacoes/          # Sistema de notificações
├── painel/                # Painel de horários
├── professores/           # Gestão de professores
├── relatorios/            # Relatórios
├── usuarios/              # Gestão de alunos
├── static/                # Arquivos estáticos
│   └── images/
│       └── landing/       # Imagens da landing page
├── templates/             # Templates globais
├── db.sqlite3             # Banco de dados
├── manage.py              # Gerenciador Django
├── requirements.txt       # Dependências
├── start.sh               # Script de inicialização
└── README.md              # Este arquivo
```

## ⚙️ Configurações

### Configurar Academia

1. Acesse: http://localhost:8000/admin/academia/configuracao/
2. Configure:
   - Nome da academia
   - Endereço completo
   - CNPJ
   - **Dias de alerta de vencimento** (padrão: 5 dias)
   - **Mensagem de pagamento atrasado**
   - **Mensagem de aniversário** (use `{nome}` e `{academia}`)

### Configurar E-mail

Edite `app/settings.py`:

```python
# Para desenvolvimento (console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Para produção (SMTP - Gmail)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "seu-email@gmail.com"
EMAIL_HOST_PASSWORD = "sua-senha-app"  # Use senha de app do Gmail
DEFAULT_FROM_EMAIL = "seu-email@gmail.com"
```

### Upload de Logo

1. Acesse: http://localhost:8000/admin/academia/identidadevisual/
2. Faça upload do logotipo e favicon

## 📊 Como Usar o Dashboard

### Gráfico Financeiro

O gráfico circular mostra 3 categorias:

- 🟢 **Verde (Em Dia)**: Pagamentos válidos
- 🟡 **Amarelo (Alerta)**: Vencendo em breve (configurável)
- 🔴 **Vermelho (Atrasados)**: Pagamentos vencidos

**Interação**: Clique na área vermelha para abrir modal e enviar notificação aos atrasados.

### Aniversariantes do Dia

- Exibe quantidade e lista de aniversariantes
- Botão para enviar mensagem personalizada
- Mensagem configurável em `/admin/academia/configuracao/`

## 🎨 Landing Page

### Recursos Visuais

- ✨ Animações AOS (Animate On Scroll)
- 🎨 Gradientes modernos
- 🌊 Background com orbs flutuantes
- 💫 Cards com hover effects
- 📱 Design responsivo

### Personalizar Cores

Edite `academia/templates/academia/landing_page.html`:

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

## 🔧 Dependências

- Django 4.2.0
- Pillow 10.4.0 (processamento de imagens)
- python-dateutil 2.9.0 (manipulação de datas)
- requests 2.32.3 (integração PagBank)

## 🐛 Solução de Problemas

### Erro: No module named 'django'
```bash
# Certifique-se de ativar o ambiente virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### Erro: No module named 'requests'
```bash
pip install -r requirements.txt
```

### Imagens não aparecem
```bash
# Verifique se DEBUG = True em settings.py
# Em produção, execute:
python manage.py collectstatic
```

### Erro ao enviar e-mail
- Configure corretamente o SMTP em `settings.py`
- Use senha de app do Gmail (não a senha normal)
- Para testes, use `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'`

### Erro de migração
```bash
python manage.py migrate --run-syncdb
```

## 📱 Responsividade

O sistema funciona perfeitamente em:
- 📱 Smartphones (iOS/Android)
- 📱 Tablets
- 💻 Notebooks
- 🖥️ Desktops

## 🔒 Segurança

- ✅ Autenticação obrigatória
- ✅ Permissões por tipo de usuário
- ✅ CSRF protection
- ✅ Validação de dados
- ✅ Senhas criptografadas

## 📝 Tipos de Usuário

### 1. Admin/Staff
- Acesso total ao sistema
- Dashboard com estatísticas
- Gestão de usuários e pagamentos
- Envio de notificações

### 2. Professor
- Dashboard específico
- Visualização de aulas
- Gestão de painéis

### 3. Aluno
- Dashboard do aluno
- Visualização de treinos
- Status de pagamento

## 🎯 Próximos Passos

Após instalar:

1. ✅ Acesse o admin e configure a academia
2. ✅ Faça upload do logo
3. ✅ Configure o e-mail (se necessário)
4. ✅ Cadastre alguns alunos de teste
5. ✅ Cadastre pagamentos
6. ✅ Teste o dashboard e gráficos
7. ✅ Personalize a landing page

## 📞 Suporte

Para dúvidas:
1. Verifique os logs do Django
2. Consulte a documentação: https://docs.djangoproject.com/
3. Revise os arquivos de configuração

## 📄 Licença

Este projeto é fornecido "como está" para fins educacionais e comerciais.

## 🎉 Pronto!

Seu sistema de academia está **100% funcional**!

Acesse http://localhost:8000/ e explore todas as funcionalidades.

---

**Desenvolvido com ❤️ usando Django**
