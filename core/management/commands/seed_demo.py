from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.utils import timezone
from core.models import (
    Plano, CTO, Cliente, Chamado, ContaPagar, Pagamento, DebitoCongelado,
    Material, MovimentacaoEstoque, RetiradaMaterial, RegistroPonto,
)

User = get_user_model()

MODELOS_OPERADOR = ["cliente", "cto", "chamado", "plano", "contapagar"]
ACOES_OPERADOR = ["view", "add", "change", "delete"]


class Command(BaseCommand):
    help = "Popula o banco com dados de exemplo para testar o sistema"

    def handle(self, *args, **options):
        grupo_admin, _ = Group.objects.get_or_create(name="Administrador")
        grupo_operador, _ = Group.objects.get_or_create(name="Operador")
        grupo_tecnico, _ = Group.objects.get_or_create(name="Técnico")

        # Administrador: todas as permissões do sistema
        grupo_admin.permissions.set(Permission.objects.all())

        # Operador: pode gerenciar clientes, CTOs, chamados, planos e financeiro
        perms_operador = Permission.objects.filter(
            content_type__model__in=MODELOS_OPERADOR,
            codename__regex=r"^(" + "|".join(ACOES_OPERADOR) + ")_",
        )
        grupo_operador.permissions.set(perms_operador)

        # Técnico: só visualizar CTOs e chamados
        perms_tecnico = Permission.objects.filter(
            content_type__model__in=["cto", "chamado"], codename__startswith="view_"
        )
        grupo_tecnico.permissions.set(perms_tecnico)

        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser("admin", "admin@exemplo.com", "admin123", role="admin")
            admin.groups.add(grupo_admin)
            self.stdout.write(self.style.SUCCESS("Usuário admin/admin123 criado"))

        if not User.objects.filter(username="operador1").exists():
            operador = User.objects.create_user("operador1", password="operador123", role="operador", first_name="Operador")
            operador.groups.add(grupo_operador)
            self.stdout.write(self.style.SUCCESS("Usuário operador1/operador123 criado"))

        tecnico, criado = User.objects.get_or_create(
            username="tecnico1", defaults={"role": "tecnico", "first_name": "Carlos", "last_name": "Silva"}
        )
        if criado:
            tecnico.set_password("tecnico123")
            tecnico.save()
            tecnico.groups.add(grupo_tecnico)
            self.stdout.write(self.style.SUCCESS("Usuário tecnico1/tecnico123 criado"))

        planos_dados = [("100 Mega", 100, 79.90), ("400 Mega", 400, 99.90), ("600 Mega", 600, 119.90), ("1 Giga", 1000, 149.90)]
        planos = []
        for nome, vel, valor in planos_dados:
            plano, _ = Plano.objects.get_or_create(nome=nome, defaults={"velocidade_mb": vel, "valor_mensal": valor})
            planos.append(plano)

        bairros = ["Centro", "Janga", "Maranguape", "Pau Amarelo"]
        ruas_exemplo = [
            "Rua Clara\nRua Puebla\nRua das Acácias",
            "Rua do Sol\nRua da Praia",
            "Rua Nova\nRua Firmino Pires",
            "Rua Central\nAvenida Marginal",
        ]
        ctos = []
        for i, bairro in enumerate(bairros, start=1):
            cto, _ = CTO.objects.get_or_create(
                codigo=f"CTO {str(i).zfill(3)}",
                defaults={
                    "bairro": bairro, "endereco": f"Rua Principal, {bairro}", "capacidade": 16 if i % 2 else 8,
                    "ruas_atendidas": ruas_exemplo[(i - 1) % len(ruas_exemplo)],
                },
            )
            ctos.append(cto)

        nomes = ["João Silva Souza", "Maria Souza", "Carlos Lima", "Ana Paula", "Pedro Henrique", "Larissa Nunes", "Diego Santos", "Camila Andrade"]
        clientes = []
        for i, nome in enumerate(nomes):
            status = "inadimplente" if i % 5 == 4 else "ativo"
            cliente, _ = Cliente.objects.get_or_create(
                nome=nome,
                defaults={
                    "cpf_cnpj": f"{100+i:03d}.{200+i:03d}.{300+i:03d}-{10+i:02d}",
                    "telefone": f"(81) 9{8000+i*37:04d}-{1000+i*91:04d}",
                    "logradouro": "Rua Firmino Pires",
                    "numero": str(100 + i),
                    "bairro": ctos[i % len(ctos)].bairro,
                    "cidade": "Paulista",
                    "estado": "PE",
                    "login_pppoe": f"cliente{i+1}",
                    "senha_pppoe": "123456",
                    "plano": planos[i % len(planos)],
                    "cto": ctos[i % len(ctos)],
                    "porta": str((i % 16) + 1).zfill(2),
                    "status": status,
                    "dia_vencimento": (i % 28) + 1,
                    "data_ativacao": date.today() - timedelta(days=i * 20),
                    "data_nascimento": date(1985 + i, ((i * 3) % 12) + 1, ((i * 7) % 27) + 1),
                },
            )
            clientes.append(cliente)

        tipos = ["sem_sinal", "lentidao", "instalacao", "equipamento"]
        prioridades = ["alta", "media", "baixa"]
        for i, cliente in enumerate(clientes):
            # Só 1 a cada 3 chamados já nasce atribuído ao técnico de teste,
            # o resto fica disponível pra testar o "Pegar chamado".
            tecnico_do_chamado = tecnico if i % 3 == 0 else None
            status_inicial = "andamento" if tecnico_do_chamado else "aberto"
            Chamado.objects.get_or_create(
                cliente=cliente,
                tipo=tipos[i % len(tipos)],
                defaults={
                    "prioridade": prioridades[i % len(prioridades)],
                    "status": status_inicial,
                    "tecnico": tecnico_do_chamado,
                    "descricao": "Cliente relata instabilidade na conexão.",
                },
            )

        contas = [
            ("Aluguel do POP - Centro", 20, 3200),
            ("Energia elétrica (torres)", 22, 1850),
            ("Link de internet (upstream)", 25, 8900),
            ("Material de rede (CTOs/cabos)", 18, 2150),
        ]
        for descricao, dia, valor in contas:
            ContaPagar.objects.get_or_create(
                descricao=descricao,
                defaults={"vencimento": date.today().replace(day=min(dia, 28)), "valor": valor, "recorrente": True},
            )

        # Pagamentos de exemplo dos últimos meses (pra alimentar o Fluxo de Caixa)
        hoje = date.today().replace(day=1)
        for i in range(6):
            ano = hoje.year + ((hoje.month - i - 1) // 12)
            mes = ((hoje.month - i - 1) % 12) + 1
            ref = hoje.replace(year=ano, month=mes)
            for cliente in clientes[: max(1, len(clientes) - i)]:
                if cliente.status == "inadimplente" and i == 0:
                    continue
                Pagamento.objects.get_or_create(
                    cliente=cliente, mes_referencia=ref,
                    defaults={"valor": cliente.valor_mensal(), "data_pagamento": ref, "registrado_por": None},
                )

        # Débitos congelados de exemplo (pra demonstração)
        congelados_dados = [
            ("Fatura atrasada - fornecedor XPTO", 3200.00, date(2025, 11, 10), "Cliente antigo, aguardando negociação"),
            ("Multa contratual - rescisão antiga", 1500.00, date(2025, 9, 5), "Aguardando definição jurídica"),
            ("Empréstimo capital de giro", 8000.00, date(2025, 12, 1), "Negociar taxa de juros antes de parcelar"),
        ]
        for descricao, valor, data_origem, obs in congelados_dados:
            DebitoCongelado.objects.get_or_create(
                descricao=descricao, defaults={"valor": valor, "data_origem": data_origem, "observacoes": obs},
            )

        # 2 débitos já negociados de exemplo (mostra o histórico e já gera as contas a pagar)
        negociados_dados = [
            ("Equipamento antigo - fornecedor ABC", 2400.00, date(2025, 8, 15), 600.00, 4),
            ("Dívida com prestador de serviço", 900.00, date(2025, 10, 1), 300.00, 3),
        ]
        for descricao, valor_original, data_origem, valor_parcela, parcelas in negociados_dados:
            debito, criado = DebitoCongelado.objects.get_or_create(
                descricao=descricao,
                defaults={"valor": valor_original, "data_origem": data_origem, "observacoes": "Já negociado"},
            )
            if criado:
                conta = ContaPagar.objects.create(
                    descricao=f"{descricao} (negociado)", valor=valor_parcela,
                    vencimento=date.today().replace(day=10), status="pendente",
                    recorrente=False, forma_pagamento="boleto", parcela_atual=1, total_parcelas=parcelas,
                )
                debito.negociado = True
                debito.negociado_em = timezone.now()
                debito.conta_pagar_gerada = conta
                debito.save()

        # ---------------------------------------------------------------
        # Dados extras de demonstração: mais um técnico, mais um operador,
        # chamados concluídos com tempo registrado, ponto batido, materiais
        # de estoque e retiradas — pra já aparecer preenchido nos relatórios
        # sem precisar cadastrar nada na mão.
        # ---------------------------------------------------------------
        tecnico2, criado = User.objects.get_or_create(
            username="tecnico2", defaults={"role": "tecnico", "first_name": "Roberto", "last_name": "Alves"}
        )
        if criado:
            tecnico2.set_password("tecnico123")
            tecnico2.save()
            tecnico2.groups.add(grupo_tecnico)
            self.stdout.write(self.style.SUCCESS("Usuário tecnico2/tecnico123 criado"))

        operador2, criado = User.objects.get_or_create(
            username="operador2", defaults={"role": "operador", "first_name": "Fernanda", "last_name": "Costa"}
        )
        if criado:
            operador2.set_password("operador123")
            operador2.save()
            operador2.groups.add(grupo_operador)
            self.stdout.write(self.style.SUCCESS("Usuário operador2/operador123 criado"))

        operador1 = User.objects.filter(username="operador1").first()
        tecnicos_demo = [tecnico, tecnico2]
        operadores_demo = [o for o in [operador1, operador2] if o]

        # 5 chamados concluídos (com tempo de atendimento) pra cada técnico
        agora = timezone.now()
        for idx_t, tec in enumerate(tecnicos_demo):
            for i in range(5):
                cliente_c = clientes[(idx_t * 5 + i) % len(clientes)]
                tipo_c = tipos[i % len(tipos)]
                dias_atras = 2 + i * 3
                inicio = agora - timedelta(days=dias_atras, hours=1)
                duracao_min = 25 + (i * 15) + (idx_t * 5)
                fim = inicio + timedelta(minutes=duracao_min)
                Chamado.objects.get_or_create(
                    cliente=cliente_c, tipo=tipo_c, tecnico=tec, status="concluido",
                    defaults={
                        "prioridade": prioridades[i % len(prioridades)],
                        "aberto_por": operadores_demo[i % len(operadores_demo)] if operadores_demo else None,
                        "descricao": "Chamado de exemplo (dados de demonstração).",
                        "observacao_fechamento": "Atendimento concluído com sucesso.",
                        "pego_em": inicio,
                        "atendimento_iniciado_em": inicio,
                        "concluido_em": fim,
                    },
                )

        # Ponto batido nos últimos dias, pra cada técnico (pra "Horas de ponto no mês" aparecer)
        for tec in tecnicos_demo:
            for dias_atras in [2, 4, 6, 8, 10]:
                dia = (agora - timedelta(days=dias_atras)).date()
                if dia.month != agora.month or dia.year != agora.year:
                    continue
                for tipo_p, hora, minuto in [("entrada", 8, 0), ("saida_almoco", 12, 0), ("volta_almoco", 13, 0), ("saida", 17, 0)]:
                    dt = timezone.make_aware(datetime(dia.year, dia.month, dia.day, hora, minuto))
                    RegistroPonto.objects.get_or_create(usuario=tec, tipo=tipo_p, data_hora=dt)

        # Materiais de estoque de exemplo, já com saldo (entrada inicial)
        materiais_dados = [
            ("Cabo de fibra óptica", "m", 100),
            ("Conector SC/APC", "un", 20),
            ("ONU/ONT", "un", 5),
            ("Roteador Wi-Fi", "un", 5),
            ("Bobina de fibra 1km", "rolo", 2),
        ]
        materiais_demo = []
        for nome, unidade, minimo in materiais_dados:
            material, _ = Material.objects.get_or_create(
                nome=nome, defaults={"unidade_medida": unidade, "estoque_minimo": minimo},
            )
            materiais_demo.append(material)
            if not material.movimentacoes.filter(tipo="entrada").exists():
                MovimentacaoEstoque.objects.create(
                    material=material, tipo="entrada", quantidade=minimo * 10,
                    observacao="Compra inicial de exemplo", registrado_por=None,
                )

        # Retiradas de material de exemplo pros técnicos (uma confirmada, uma pendente)
        if not RetiradaMaterial.objects.exists():
            retirada1 = RetiradaMaterial.objects.create(
                tecnico=tecnico, registrado_por=operador1, observacao="Instalação nova - exemplo",
                confirmado=True, confirmado_em=agora - timedelta(days=3),
            )
            MovimentacaoEstoque.objects.create(
                material=materiais_demo[0], tipo="saida", quantidade=50, tecnico=tecnico,
                registrado_por=operador1, retirada=retirada1,
            )
            MovimentacaoEstoque.objects.create(
                material=materiais_demo[1], tipo="saida", quantidade=4, tecnico=tecnico,
                registrado_por=operador1, retirada=retirada1,
            )
            MovimentacaoEstoque.objects.create(
                material=materiais_demo[2], tipo="saida", quantidade=1, tecnico=tecnico,
                registrado_por=operador1, retirada=retirada1,
            )

            retirada2 = RetiradaMaterial.objects.create(
                tecnico=tecnico2, registrado_por=operador1, observacao="Troca de ONU - exemplo",
            )
            MovimentacaoEstoque.objects.create(
                material=materiais_demo[2], tipo="saida", quantidade=1, tecnico=tecnico2,
                registrado_por=operador1, retirada=retirada2,
            )
            MovimentacaoEstoque.objects.create(
                material=materiais_demo[1], tipo="saida", quantidade=2, tecnico=tecnico2,
                registrado_por=operador1, retirada=retirada2,
            )

        # Chamados de exemplo pendentes há alguns dias (pra testar o selo
        # "Cliente há X dias sem suporte"), sem técnico atribuído
        exemplos_pendentes = [
            (clientes[0], "sem_sinal", "alta", 1),
            (clientes[1], "lentidao", "media", 3),
            (clientes[2], "equipamento", "baixa", 5),
        ]
        for cliente_p, tipo_p, prioridade_p, dias_atras_p in exemplos_pendentes:
            chamado_p, criado_p = Chamado.objects.get_or_create(
                cliente=cliente_p, tipo=tipo_p, status="aberto", tecnico=None,
                defaults={
                    "prioridade": prioridade_p,
                    "aberto_por": operador1,
                    "descricao": "Chamado de exemplo pendente há alguns dias (dados de demonstração).",
                },
            )
            if criado_p:
                data_passada = agora - timedelta(days=dias_atras_p, hours=2)
                Chamado.objects.filter(pk=chamado_p.pk).update(criado_em=data_passada)

        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados com sucesso!"))
        self.stdout.write("Logins de teste:")
        self.stdout.write("  admin / admin123  (Administrador)")
        self.stdout.write("  operador1 / operador123  (Operador)")
        self.stdout.write("  operador2 / operador123  (Operador)")
        self.stdout.write("  tecnico1 / tecnico123  (Técnico)")
        self.stdout.write("  tecnico2 / tecnico123  (Técnico)")
