#!/bin/bash

echo "🚀 Iniciando Sistema de Academia..."
echo ""

# Ativar ambiente virtual
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

# Instalar dependências
echo "📥 Instalando dependências..."
pip install -q -r requirements.txt

# Aplicar migrações
echo "🔄 Aplicando migrações..."
python manage.py migrate

# Criar superusuário se não existir
echo "👤 Verificando superusuário..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@academia.com', 'admin123')
    print('✓ Superusuário criado: admin / admin123')
else:
    print('✓ Superusuário já existe: admin / admin123')
EOF

# Criar configuração inicial
echo "⚙️  Verificando configuração..."
python manage.py shell << 'EOF'
from academia.models import Configuracao
if not Configuracao.objects.exists():
    Configuracao.objects.create(
        titulo='FitPro Academia',
        endereco='Rua das Flores',
        numero='123',
        cep='12345-678',
        cnpj='12.345.678/0001-90',
        dias_alerta_vencimento=5,
        mensagem_pagamento_atrasado='Olá! Identificamos que seu pagamento está em atraso. Por favor, regularize sua situação para continuar aproveitando nossos serviços.',
        mensagem_aniversario='Parabéns {nome}! A equipe {academia} deseja um feliz aniversário! 🎉'
    )
    print('✓ Configuração inicial criada')
else:
    print('✓ Configuração já existe')
EOF

echo ""
echo "✅ Sistema pronto!"
echo ""
echo "📋 Credenciais de acesso:"
echo "   Usuário: admin"
echo "   Senha: admin123"
echo ""
echo "🌐 URLs importantes:"
echo "   Landing Page: http://localhost:8000/"
echo "   Dashboard: http://localhost:8000/dashboard/"
echo "   Admin: http://localhost:8000/admin/"
echo ""
echo "🚀 Iniciando servidor..."
echo ""

python manage.py runserver
