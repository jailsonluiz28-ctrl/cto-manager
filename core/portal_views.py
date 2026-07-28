"""Portal do Cliente — área pública (sem login de funcionário) onde o cliente
da internet consegue ver a fatura do mês, pegar a segunda via, falar no
WhatsApp com a empresa e ver promoções. Login é feito com CPF + senha; a senha
é escolhida pelo próprio cliente no primeiro acesso, depois de confirmar CPF e
data de nascimento (os mesmos dados que já ficam no cadastro dele)."""

from datetime import datetime, date

from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm

from .models import Cliente, Promocao, ConfiguracaoEmpresa, SolicitacaoLiberacaoConfianca
from .utils import normalizar


def _so_digitos(txt):
    return "".join(ch for ch in (txt or "") if ch.isdigit())


def _parse_data(txt):
    """Converte o valor de um <input type=date> (AAAA-MM-DD) pra date. None se inválido."""
    try:
        return datetime.strptime(txt, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_data_partes(request, prefixo="nasc"):
    """Monta a data de nascimento a partir de 3 campos numéricos digitados
    (dia/mês/ano) — mais rápido no celular do que rolar um calendário até
    décadas atrás. None se algum campo estiver vazio ou a data for inválida."""
    try:
        dia = int(request.POST.get(f"{prefixo}_dia", ""))
        mes = int(request.POST.get(f"{prefixo}_mes", ""))
        ano = int(request.POST.get(f"{prefixo}_ano", ""))
        return date(ano, mes, dia)
    except (TypeError, ValueError):
        return None


def _cliente_logado(request):
    cid = request.session.get("portal_cliente_id")
    if not cid:
        return None
    return Cliente.objects.filter(pk=cid).exclude(status="cancelado").first()


def _estilo_tabela_portal():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])


# ---------------------------------------------------------------------------
# LOGIN / PRIMEIRO ACESSO / ESQUECI A SENHA
# ---------------------------------------------------------------------------

def portal_login(request):
    if _cliente_logado(request):
        return redirect("portal_dashboard")

    erro = None
    if request.method == "POST":
        cpf = _so_digitos(request.POST.get("cpf"))
        senha = request.POST.get("senha", "")
        cliente = Cliente.objects.filter(cpf_digitos=cpf).exclude(status="cancelado").first()
        if not cliente or not cliente.portal_senha_hash:
            erro = "CPF não encontrado, ou você ainda não fez o primeiro acesso."
        elif not check_password(senha, cliente.portal_senha_hash):
            erro = "CPF ou senha incorretos."
        else:
            request.session["portal_cliente_id"] = cliente.id
            return redirect("portal_dashboard")

    return render(request, "portal/login.html", {"erro": erro})


def portal_logout(request):
    request.session.pop("portal_cliente_id", None)
    return redirect("portal_login")


def portal_primeiro_acesso(request):
    erro = None
    if request.method == "POST":
        cpf = _so_digitos(request.POST.get("cpf"))
        data_nasc = _parse_data_partes(request)
        cliente = Cliente.objects.filter(cpf_digitos=cpf, data_nascimento=data_nasc).exclude(status="cancelado").first() if data_nasc else None

        if not cliente:
            erro = "Não encontramos um cadastro com esse CPF e data de nascimento. Confira os dados ou fale com a gente."
        elif cliente.portal_senha_hash:
            erro = "Esse CPF já tem senha cadastrada. Use a tela de entrar, ou \"Esqueci minha senha\"."
        else:
            request.session["portal_definir_senha_cliente_id"] = cliente.id
            return redirect("portal_definir_senha")

    return render(request, "portal/primeiro_acesso.html", {"erro": erro})


def portal_esqueci_senha(request):
    erro = None
    if request.method == "POST":
        nome = normalizar(request.POST.get("nome"))
        cpf = _so_digitos(request.POST.get("cpf"))
        data_nasc = _parse_data_partes(request)
        cliente = Cliente.objects.filter(cpf_digitos=cpf, data_nascimento=data_nasc).exclude(status="cancelado").first() if data_nasc else None

        if not cliente or normalizar(cliente.nome) != nome:
            erro = "Não encontramos um cadastro com esse nome, CPF e data de nascimento. Confira os dados ou fale com a gente."
        else:
            request.session["portal_definir_senha_cliente_id"] = cliente.id
            return redirect("portal_definir_senha")

    return render(request, "portal/esqueci_senha.html", {"erro": erro})


def portal_definir_senha(request):
    cliente_id = request.session.get("portal_definir_senha_cliente_id")
    if not cliente_id:
        return redirect("portal_primeiro_acesso")
    cliente = get_object_or_404(Cliente, pk=cliente_id)

    erro = None
    if request.method == "POST":
        senha1 = request.POST.get("senha1", "")
        senha2 = request.POST.get("senha2", "")
        if len(senha1) < 6:
            erro = "A senha precisa ter pelo menos 6 caracteres."
        elif senha1 != senha2:
            erro = "As duas senhas digitadas não são iguais."
        else:
            cliente.portal_senha_hash = make_password(senha1)
            cliente.portal_senha_definida_em = timezone.now()
            cliente.save(update_fields=["portal_senha_hash", "portal_senha_definida_em"])
            del request.session["portal_definir_senha_cliente_id"]
            messages.success(request, "Senha cadastrada! Agora é só entrar com seu CPF e a senha.")
            return redirect("portal_login")

    return render(request, "portal/definir_senha.html", {"cliente": cliente, "erro": erro})


# ---------------------------------------------------------------------------
# ÁREA LOGADA DO CLIENTE
# ---------------------------------------------------------------------------

def portal_dashboard(request):
    cliente = _cliente_logado(request)
    if not cliente:
        return redirect("portal_login")

    config = ConfiguracaoEmpresa.obter()
    promocoes = Promocao.objects.filter(ativa=True)
    hoje = timezone.now().date()
    solicitacao_pendente = cliente.solicitacoes_liberacao.filter(atendida=False).exists()

    return render(request, "portal/dashboard.html", {
        "cliente": cliente,
        "config": config,
        "promocoes": promocoes,
        "pago": cliente.pago_mes_atual(),
        "mes_ref": hoje,
        "solicitacao_pendente": solicitacao_pendente,
    })


def portal_pedir_liberacao(request):
    cliente = _cliente_logado(request)
    if not cliente:
        return redirect("portal_login")
    if request.method == "POST":
        if not cliente.solicitacoes_liberacao.filter(atendida=False).exists():
            SolicitacaoLiberacaoConfianca.objects.create(cliente=cliente)
        messages.success(request, "Pedido enviado! Nossa equipe vai avaliar e entrar em contato.")
    return redirect("portal_dashboard")


def portal_segunda_via_pdf(request):
    cliente = _cliente_logado(request)
    if not cliente:
        return redirect("portal_login")

    config = ConfiguracaoEmpresa.obter()
    hoje = timezone.now().date()
    pago = cliente.pago_mes_atual()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="fatura_{hoje.strftime("%m_%Y")}.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm)
    estilos = getSampleStyleSheet()
    E = []

    nome_empresa = config.nome_fantasia or "Segunda via de fatura"
    E.append(Paragraph(nome_empresa, estilos["Title"]))
    E.append(Spacer(1, 4))
    E.append(Paragraph(f"Fatura de {hoje.strftime('%m/%Y')}", estilos["Heading2"]))
    E.append(Spacer(1, 14))

    dados = [
        ["Cliente", cliente.nome],
        ["Plano", cliente.plano.nome if cliente.plano else "—"],
        ["Valor mensal", f"R$ {cliente.valor_mensal():.2f}"],
        ["Vencimento", f"Dia {cliente.dia_vencimento}"],
        ["Situação", "Pago" if pago else "Em aberto"],
    ]
    t = Table(dados, colWidths=[5 * cm, 10 * cm])
    t.setStyle(_estilo_tabela_portal())
    E.append(t)
    E.append(Spacer(1, 20))

    if not pago:
        E.append(Paragraph(
            "Pagamento via boleto/Pix em breve por aqui — por enquanto, fale com a gente pelo WhatsApp pra "
            "combinar o pagamento.", estilos["Normal"],
        ))

    doc.build(E)
    return response


# ---------------------------------------------------------------------------
# ADMINISTRAÇÃO DO PORTAL (Promoções e Configuração da Empresa) — só Admin
# ---------------------------------------------------------------------------

@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def promocao_list(request):
    promocoes = Promocao.objects.all()
    return render(request, "core/promocao_list.html", {"promocoes": promocoes})


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def promocao_create(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        ativa = request.POST.get("ativa") == "on"
        imagem = request.FILES.get("imagem")
        if not titulo:
            messages.error(request, "Digite um título pra promoção.")
        else:
            Promocao.objects.create(
                titulo=titulo, descricao=descricao, ativa=ativa, imagem=imagem, criado_por=request.user,
            )
            messages.success(request, "Promoção cadastrada! Já aparece no Portal do Cliente.")
            return redirect("promocao_list")
    return render(request, "core/promocao_form.html", {})


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def promocao_toggle(request, pk):
    promocao = get_object_or_404(Promocao, pk=pk)
    promocao.ativa = not promocao.ativa
    promocao.save(update_fields=["ativa"])
    return redirect("promocao_list")


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def promocao_delete(request, pk):
    promocao = get_object_or_404(Promocao, pk=pk)
    if request.method == "POST":
        promocao.delete()
        messages.success(request, "Promoção excluída.")
        return redirect("promocao_list")
    return render(request, "core/promocao_confirm_delete.html", {"promocao": promocao})


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def solicitacao_liberacao_list(request):
    solicitacoes = SolicitacaoLiberacaoConfianca.objects.select_related("cliente", "atendida_por")
    return render(request, "core/solicitacao_liberacao_list.html", {"solicitacoes": solicitacoes})


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def solicitacao_liberacao_atender(request, pk):
    solicitacao = get_object_or_404(SolicitacaoLiberacaoConfianca, pk=pk)
    if request.method == "POST":
        solicitacao.atendida = True
        solicitacao.atendida_por = request.user
        solicitacao.atendida_em = timezone.now()
        solicitacao.observacao_admin = request.POST.get("observacao_admin", "").strip()
        solicitacao.save()
        messages.success(request, "Solicitação marcada como atendida.")
    return redirect("solicitacao_liberacao_list")


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def configuracao_empresa_editar(request):
    config = ConfiguracaoEmpresa.obter()
    if request.method == "POST":
        config.nome_fantasia = request.POST.get("nome_fantasia", "").strip()
        numero = _so_digitos(request.POST.get("whatsapp_numero"))
        if numero and not numero.startswith("55"):
            numero = "55" + numero
        config.whatsapp_numero = numero
        config.mensagem_boas_vindas = request.POST.get("mensagem_boas_vindas", "").strip()
        config.save()
        messages.success(request, "Configuração do Portal do Cliente atualizada!")
        return redirect("configuracao_empresa_editar")
    return render(request, "core/configuracao_empresa_form.html", {"config": config})
