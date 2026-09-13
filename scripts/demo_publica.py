"""Povoa a DEMONSTRACAO com uma rede completa e logins prontos para clicar.

    docker compose -f docker-compose.dev.yml -f docker-compose.demo.yml \
        run --rm -T demo python manage.py shell -c "import scripts.demo_publica"

Roda em banco separado (`academia_demo`) e sob o prefixo `/demo`. Se a rede da demonstracao ja
existe, ele APAGA so o que ele mesmo criou (rede, unidades e os logins @demonstracao.com.br) e
refaz -- nunca toca em outra rede.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from agendamento.models import Agendamento
from aulas.models import Aulas
from cobranca.models import CobrancaRecorrente
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from painel.models import Painel, PainelItem
from plataforma.models import Assinatura, Pacote
from professores.models import Professor
from relacionamento.models import Lead
from treinos.models import AvaliacaoFisica, ExercicioDoTreino, Treino
from usuarios.models import FichaSaude, Usuario

SENHA = "Demo@2026"
SLUG = "demonstracao"
DOMINIO = "demonstracao.com.br"
hoje = timezone.localdate()
ModeloDeUsuario = get_user_model()


def criar_login(nome: str, email: str, **extras):
    return ModeloDeUsuario.objects.create_user(
        username=email,
        email=email,
        password=SENHA,
        first_name=nome.split()[0],
        last_name=nome.split()[-1],
        **extras,
    )


def limpar() -> None:
    """Apaga apenas o que esta demonstracao criou."""
    rede = Rede.todos.filter(slug=SLUG).first()
    if rede:
        Agendamento.todos.filter(rede=rede).delete()
        CobrancaRecorrente.objects.filter(rede=rede).delete()
        Lead.objects.filter(rede=rede).delete()
        AvaliacaoFisica.objects.filter(rede=rede).delete()
        Treino.objects.filter(rede=rede).delete()
        FichaSaude.objects.filter(rede=rede).delete()
        Pagamento.objects.filter(rede=rede).delete()
        Usuario.todos.filter(rede=rede).delete()
        Professor.objects.filter(rede=rede).delete()
        Aulas.objects.filter(rede=rede).delete()
        Assinatura.objects.filter(rede=rede).delete()
        Painel.objects.filter(rede=rede).delete()
        Unidade.objects.filter(rede=rede).delete()
        rede.delete()
        print("[limpeza] rede de demonstracao anterior removida")
    ModeloDeUsuario.objects.filter(email__endswith=f"@{DOMINIO}").delete()
    ModeloDeUsuario.objects.filter(email="dono@safestack.com.br").delete()


def povoar() -> None:
    limpar()
    call_command("seed_plataforma", verbosity=0)

    rede = Rede.todos.create(
        nome="Rede Demonstracao",
        slug=SLUG,
        status="ativo",
        email_responsavel=f"contato@{DOMINIO}",
        telefone="(51) 99999-0000",
    )
    centro = Unidade.objects.create(
        rede=rede,
        nome="Demonstracao Centro",
        codigo="centro",
        tipo="propria",
        status="ativa",
        cidade="Montenegro",
        uf="RS",
    )
    norte = Unidade.objects.create(
        rede=rede,
        nome="Demonstracao Zona Norte",
        codigo="norte",
        tipo="franqueada",
        status="ativa",
        cidade="Montenegro",
        uf="RS",
    )
    pacote = Pacote.objects.filter(codigo="ouro").first() or Pacote.objects.first()
    Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo="mensal",
        inicio=hoje,
        renovacao_em=hoje + timedelta(days=30),
    )
    print(f"[plataforma] assinatura no pacote {pacote.nome if pacote else 'padrao'}")

    criar_login("Dono SafeStack", "dono@safestack.com.br", is_staff=True, is_superuser=True)
    login_rede = criar_login("Administrador da Rede", f"rede@{DOMINIO}")
    login_unidade = criar_login("Administrador da Unidade", f"unidade@{DOMINIO}")
    login_professor = criar_login("Professor Demonstracao", f"professor@{DOMINIO}")
    login_aluno = criar_login("Aluno Demonstracao", f"aluno@{DOMINIO}")
    VinculoUsuario.todos.create(usuario=login_rede, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    VinculoUsuario.todos.create(
        usuario=login_unidade, rede=rede, unidade=centro, papel=Papel.GESTOR_UNIDADE, ativo=True
    )
    VinculoUsuario.todos.create(
        usuario=login_professor, rede=rede, unidade=centro, papel=Papel.PROFESSOR, ativo=True
    )
    VinculoUsuario.todos.create(
        usuario=login_aluno, rede=rede, unidade=centro, papel=Papel.ALUNO, ativo=True
    )
    print("[acessos] 1 login da plataforma + 4 da operacao")

    professor = Professor.objects.create(
        rede=rede,
        unidade=centro,
        user=login_professor,
        nome="Professor Demonstracao",
        email_prof=f"professor@{DOMINIO}",
        telefone_prof="(51) 98888-1111",
        status_prof="Ativo",
    )
    nomes = [
        "Ana Souza",
        "Bruno Lima",
        "Carla Dias",
        "Diego Rocha",
        "Elisa Prado",
        "Felipe Nunes",
        "Gabriela Reis",
        "Heitor Alves",
        "Isabela Costa",
        "Joao Pedro",
        "Karina Melo",
        "Lucas Freitas",
    ]
    for indice, nome in enumerate(nomes):
        email = f"aluno{indice + 1}@{DOMINIO}"
        login = criar_login(nome, email)
        perfil = Usuario.todos.create(
            rede=rede,
            unidade=centro if indice % 2 == 0 else norte,
            user=login,
            nome=nome,
            status_user="Ativo",
            email_user=email,
            cpf_cnpj_user=f"900000000{indice:02d}",
        )
        FichaSaude.objects.create(
            rede=rede,
            unidade=centro,
            usuario=perfil,
            altura=Decimal("1.75"),
            peso=Decimal("78.50"),
            restricoes="coluna" if indice == 3 else "",
            obs="Ficha criada para a demonstracao.",
        )
    # o aluno que loga no PWA tambem e uma ficha de aluno (a que tem treino e avaliacao)
    aluno = Usuario.todos.create(
        rede=rede, unidade=centro, user=login_aluno, nome="Aluno Demonstracao",
        status_user="Ativo", email_user=f"aluno@{DOMINIO}",
    )
    FichaSaude.objects.create(
        rede=rede, unidade=centro, usuario=aluno, altura=Decimal("1.74"), peso=Decimal("79.80"),
        restricoes="", obs="Aluno de demonstracao (login do PWA).",
    )
    print(f"[alunos] {Usuario.todos.filter(rede=rede).count()} alunos com ficha de saude")

    mensal = Plano.objects.create(
        rede=rede, unidade=centro, nome="Mensal Musculacao", tipo="mensal", valor=Decimal("189.00")
    )
    anual = Plano.objects.create(
        rede=rede, unidade=norte, nome="Anual Treino+", tipo="anual", valor=Decimal("1890.00")
    )
    for indice, perfil in enumerate(Usuario.todos.filter(rede=rede)):
        for meses_atras in (2, 1, 0):
            inicio = hoje.replace(day=1) - timedelta(days=meses_atras * 30)
            atrasado = indice % 5 == 0 and meses_atras == 0
            Pagamento.objects.create(
                rede=rede,
                unidade=perfil.unidade,
                usuario=perfil.user,
                plano=mensal if perfil.unidade_id == centro.pk else anual,
                valor_pago=Decimal("189.00"),
                data_inicio=inicio,
                data_fim=inicio + timedelta(days=30),
                data_pagamento=None
                if atrasado
                else timezone.now() - timedelta(days=meses_atras * 30),
                status="pendente" if atrasado else "pago",
            )
    vencidos = Pagamento.objects.filter(rede=rede).exclude(status="pago").count()
    print(
        f"[financeiro] {Pagamento.objects.filter(rede=rede).count()} pagamentos, {vencidos} em atraso"
    )

    aula = Aulas.objects.create(
        rede=rede,
        unidade=centro,
        nome="Treino funcional",
        descricao="Circuito de forca e condicionamento.",
        professor=login_professor,
        categorias_exercicios="funcional",
    )
    grade = Painel.objects.create(
        rede=rede,
        unidade=centro,
        nome="Turma das 19h",
        data=hoje,
        hora_inicio=time(19, 0),
        hora_fim=time(20, 0),
        responsavel=login_professor,
        numero_de_user=12,
    )
    PainelItem.objects.create(rede=rede, unidade=centro, painel=grade, aula=aula, ordem=1)
    for indice, perfil in enumerate(Usuario.todos.filter(rede=rede)[:7]):
        Agendamento.objects.create(
            rede=rede,
            unidade=centro,
            painel=grade,
            aluno=perfil.user,
            data_agendamento=timezone.make_aware(datetime.combine(hoje, time(19, 0))),
            status="Concluido" if indice < 5 else "Faltou",
        )
    print(f"[agenda] turma das 19h com {Agendamento.objects.filter(painel=grade).count()} alunos")

    treino = Treino.objects.create(
        rede=rede,
        unidade=centro,
        aluno=aluno,
        professor=professor,
        nome="Treino A - adaptacao",
        objetivo="condicionamento",
        inicio=hoje - timedelta(days=20),
        situacao="ativo",
    )
    for ordem, (nome_exercicio, series, repeticoes, carga) in enumerate(
        [
            ("Agachamento livre", 4, "12", "40"),
            ("Supino reto", 4, "10", "30"),
            ("Remada curvada", 3, "12", "25"),
            ("Prancha", 3, "40s", "0"),
        ],
        start=1,
    ):
        ExercicioDoTreino.objects.create(
            treino=treino,
            aula=aula,
            nome=nome_exercicio,
            series=series,
            repeticoes=repeticoes,
            carga_sugerida=Decimal(carga),
            descanso_segundos=60,
            ordem=ordem,
        )
    for dias, peso, gordura, muscular, medidas, obs in [
        (
            30,
            "82.40",
            "24.10",
            "58.20",
            {"cintura": "92", "quadril": "101", "braco": "33"},
            "Primeira avaliacao da demonstracao.",
        ),
        (
            0,
            "79.80",
            "21.80",
            "59.60",
            {"cintura": "88", "quadril": "98", "braco": "34"},
            "Segunda avaliacao: queda de peso e de cintura.",
        ),
    ]:
        AvaliacaoFisica.objects.create(
            rede=rede,
            unidade=centro,
            aluno=aluno,
            avaliador=professor,
            data=hoje - timedelta(days=dias),
            peso=Decimal(peso),
            altura=Decimal("1.74"),
            percentual_de_gordura=Decimal(gordura),
            massa_muscular=Decimal(muscular),
            medidas=medidas,
            observacoes=obs,
        )
    print("[treinos] 1 treino com 4 exercicios e 2 avaliacoes (evolucao pronta)")

    Lead.objects.create(
        rede=rede,
        unidade=centro,
        nome="Interessado Demonstracao",
        telefone="(51) 97777-2222",
        email=f"lead@{DOMINIO}",
        origem="indicacao",
        interesse="Musculacao",
        situacao="novo",
        valor_estimado=Decimal("189.00"),
        observacoes="Fez aula experimental e pediu proposta.",
    )
    for perfil in Usuario.todos.filter(rede=rede):
        if Pagamento.objects.filter(rede=rede, usuario=perfil.user).exclude(status="pago").exists():
            CobrancaRecorrente.objects.create(
                rede=rede,
                unidade=perfil.unidade,
                aluno=perfil,
                competencia=hoje.replace(day=1),
                valor=Decimal("189.00"),
                vencimento=hoje - timedelta(days=12),
                situacao="enviada",
            )
    print(f"[cobranca] {CobrancaRecorrente.objects.filter(rede=rede).count()} cobrancas na regua")

    print()
    print("=" * 64)
    print("DEMONSTRACAO PRONTA")
    print("=" * 64)
    print(f"Rede......: {rede.nome} (slug {rede.slug})")
    print(f"Unidades..: {centro.nome} | {norte.nome}")
    print(
        f"Alunos....: {Usuario.todos.filter(rede=rede).count()} | "
        f"Pagamentos: {Pagamento.objects.filter(rede=rede).count()} ({vencidos} em atraso) | "
        f"Agendamentos: {Agendamento.objects.count()}"
    )
    print()
    print(f"LOGINS (senha unica: {SENHA})")
    print("  plataforma (SafeStack)..: dono@safestack.com.br")
    print(f"  admin da rede...........: rede@{DOMINIO}")
    print(f"  gestor da unidade.......: unidade@{DOMINIO}")
    print(f"  professor...............: professor@{DOMINIO}")
    print(f"  aluno (PWA).............: aluno@{DOMINIO}")
    print("=" * 64)


povoar()
