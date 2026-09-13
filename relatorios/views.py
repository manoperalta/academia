from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from agendamento.models import Agendamento
from financeiro.models import Despesa, Pagamento
from usuarios.models import Usuario


@login_required
def relatorio_geral(request):
    user = request.user

    context = {
        "title": "Relatório de Atividades",
        "today": date.today(),
    }

    if user.is_superuser or user.is_staff:
        # Correção do select_related para usar 'responsavel' ao invés de 'criador'
        agendamentos = (
            Agendamento.objects.filter(aluno=user)
            .select_related("painel", "painel__responsavel")
            .prefetch_related("painel__itens__aula")
        )
    else:
        agendamentos = (
            Agendamento.objects.filter(aluno=user)
            .select_related("painel", "painel__responsavel")
            .prefetch_related("painel__itens__aula")
        )

    historico_aulas = []
    total_aulas = agendamentos.count()

    categorias_stats = {}

    for agendamento in agendamentos:
        painel = agendamento.painel
        # O campo 'aulas' não existe diretamente em Painel, acessamos via itens
        itens = painel.itens.all()
        aulas = [item.aula for item in itens]

        for aula in aulas:
            cat = aula.get_categorias_exercicios_display()
            if cat in categorias_stats:
                categorias_stats[cat] += 1
            else:
                categorias_stats[cat] = 1

        historico_aulas.append(
            {
                "data": painel.data,  # Corrigido de data_painel para data
                "hora_inicio": painel.hora_inicio,  # Corrigido nomes dos campos
                "hora_fim": painel.hora_fim,
                "responsavel": painel.responsavel.get_full_name() or painel.responsavel.username,
                "aulas": aulas,
                "status": agendamento.status,
            }
        )

    pagamento_atual = Pagamento.objects.filter(
        usuario=user, status="pago", data_fim__gte=date.today()
    ).first()
    ultimo_pagamento = Pagamento.objects.filter(usuario=user).order_by("-data_pagamento").first()

    context.update(
        {
            "historico_aulas": historico_aulas,
            "total_aulas": total_aulas,
            "categorias_stats": categorias_stats,
            "pagamento_atual": pagamento_atual,
            "ultimo_pagamento": ultimo_pagamento,
        }
    )

    return render(request, "relatorios/relatorio_geral.html", context)


@login_required
def relatorio_financeiro(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return render(request, "403.html", status=403)
    # Todos os alunos
    usuarios = Usuario.objects.all().select_related("user")

    pagos = []
    devedores = []
    today = date.today()

    for usuario in usuarios:
        # Verifica se tem pagamento ativo
        pgto_ativo = Pagamento.objects.filter(
            usuario=usuario.user, status="pago", data_fim__gte=today
        ).exists()

        # Pega o último status para exibição
        ultimo_pgto = (
            Pagamento.objects.filter(usuario=usuario.user).order_by("-data_pagamento").first()
        )
        status_desc = ultimo_pgto.get_status_display() if ultimo_pgto else "Sem registro"

        dados_usuario = {
            "nome": usuario.nome,
            "email": usuario.email_user,
            "status_financeiro": status_desc,
            "data_fim": ultimo_pgto.data_fim if ultimo_pgto else None,
        }

        if pgto_ativo:
            pagos.append(dados_usuario)
        else:
            devedores.append(dados_usuario)

    context = {
        "title": "Relatório Financeiro",
        "pagos": pagos,
        "devedores": devedores,
        "today": today,
    }
    return render(request, "relatorios/relatorio_financeiro.html", context)


@login_required
def relatorio_usuarios(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return render(request, "403.html", status=403)
    usuarios = Usuario.objects.all().order_by("nome")
    context = {
        "title": "Relatório de Usuários",
        "usuarios": usuarios,
        "today": date.today(),
    }
    return render(request, "relatorios/relatorio_usuarios.html", context)


@login_required
def relatorio_extrato(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return render(request, "403.html", status=403)
    # Entradas (Pagamentos Pagos)
    entradas = Pagamento.objects.filter(status="pago").order_by("-data_pagamento")
    total_entradas = entradas.aggregate(Sum("valor_pago"))["valor_pago__sum"] or 0

    # Saídas (Despesas)
    saidas = Despesa.objects.all().order_by("-data")
    total_saidas = saidas.aggregate(Sum("valor"))["valor__sum"] or 0

    # Pendentes
    pendentes = Pagamento.objects.filter(status="pendente").order_by("-data_pagamento")
    total_pendentes = pendentes.aggregate(Sum("valor_pago"))["valor_pago__sum"] or 0

    saldo = total_entradas - total_saidas

    context = {
        "title": "Relatório Extrato",
        "entradas": entradas,
        "total_entradas": total_entradas,
        "saidas": saidas,
        "total_saidas": total_saidas,
        "pendentes": pendentes,
        "total_pendentes": total_pendentes,
        "saldo": saldo,
        "today": date.today(),
    }
    return render(request, "relatorios/relatorio_extrato.html", context)


@login_required
def relatorio_professor(request):
    """Relatório específico para o professor ver quem agendou suas aulas"""
    if not request.user.is_professor and not (request.user.is_superuser or request.user.is_staff):
        return render(request, "403.html", status=403)  # Ou redirecionar

    # Agendamentos nos painéis onde o professor é responsável
    agendamentos = (
        Agendamento.objects.filter(painel__responsavel=request.user)
        .select_related("aluno", "painel")
        .order_by("-painel__data", "-painel__hora_inicio")
    )

    context = {
        "title": "Relatório de Agendamentos (Por Aluno)",
        "agendamentos": agendamentos,
        "today": date.today(),
    }
    return render(request, "relatorios/relatorio_professor.html", context)


@login_required
def relatorio_aluno(request):
    """Relatório específico para o aluno ver seus agendamentos da semana"""
    hoje = date.today()
    proxima_semana = hoje + timedelta(days=7)

    agendamentos = (
        Agendamento.objects.filter(aluno=request.user, painel__data__range=[hoje, proxima_semana])
        .select_related("painel", "painel__responsavel")
        .order_by("painel__data", "painel__hora_inicio")
    )

    context = {
        "title": "Meus Agendamentos da Semana",
        "agendamentos": agendamentos,
        "hoje": hoje,
        "proxima_semana": proxima_semana,
    }
    return render(request, "relatorios/relatorio_aluno.html", context)
