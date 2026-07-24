from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from core.models import Plano, CTO, Cliente, Chamado, ContaPagar

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
                descricao=descricao, defaults={"vencimento": date.today().replace(day=min(dia, 28)), "valor": valor}
            )

        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados com sucesso!"))
        self.stdout.write("Logins de teste:")
        self.stdout.write("  admin / admin123  (Administrador)")
        self.stdout.write("  operador1 / operador123  (Operador)")
        self.stdout.write("  tecnico1 / tecnico123  (Técnico)")
