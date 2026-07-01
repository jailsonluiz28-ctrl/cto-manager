from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.contrib.auth.decorators import login_required

from django.db.models import Q, Sum, Count
from django.utils import timezone

from .models import Mensalidade

from .forms import MensalidadeForm

import openpyxl

from django.http import HttpResponse

from reportlab.lib.pagesizes import letter

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


@login_required
def lista_mensalidades(request):

    busca = request.GET.get(
        "busca",
        ""
    ).strip()

    mensalidades = Mensalidade.objects.select_related(
        "cliente"
    )

    if busca:

        mensalidades = mensalidades.filter(

            Q(cliente__nome__icontains=busca)

        )

    return render(

        request,

        "financeiro/lista_mensalidades.html",

        {

            "mensalidades": mensalidades,

            "busca": busca,

        }

    )


@login_required
def nova_mensalidade(request):

    if request.method == "POST":

        form = MensalidadeForm(request.POST)

        if form.is_valid():

            form.save()

            return redirect("/financeiro/")

    else:

        form = MensalidadeForm()

    return render(

        request,

        "financeiro/nova_mensalidade.html",

        {

            "form": form

        }

    )


@login_required
def detalhe_mensalidade(

    request,

    mensalidade_id

):

    mensalidade = get_object_or_404(

        Mensalidade,

        id=mensalidade_id

    )

    return render(

        request,

        "financeiro/detalhe_mensalidade.html",

        {

            "mensalidade": mensalidade

        }

    )


from datetime import date


@login_required
def receber_mensalidade(request, mensalidade_id):

    mensalidade = get_object_or_404(
        Mensalidade,
        id=mensalidade_id
    )

    if request.method == "POST":

        mensalidade.status = "PAGO"

        mensalidade.data_pagamento = request.POST.get(
            "data_pagamento"
        )

        mensalidade.forma_pagamento = request.POST.get(
            "forma_pagamento"
        )

        mensalidade.observacao = request.POST.get(
            "observacao"
        )

        mensalidade.save()

        return redirect("/financeiro/")

    return render(

        request,

        "financeiro/receber_mensalidade.html",

        {

            "mensalidade": mensalidade,

            "hoje": date.today(),

        }

    )


@login_required
def inadimplentes(request):

    hoje = timezone.now().date()

    mensalidades = Mensalidade.objects.filter(

        status="ABERTO",

        vencimento__lt=hoje

    ).select_related(

        "cliente"

    ).order_by(

        "vencimento"

    )

    return render(

        request,

        "financeiro/inadimplentes.html",

        {

            "mensalidades": mensalidades,

            "hoje": hoje,

        }

    )


@login_required
def fluxo_caixa(request):

    recebidas = Mensalidade.objects.filter(
        status="PAGO"
    )

    total_recebido = recebidas.aggregate(
        total=Sum("valor")
    )["total"] or 0

    em_aberto = Mensalidade.objects.filter(
        status="ABERTO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    atrasadas = Mensalidade.objects.filter(
        status="ATRASADO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    canceladas = Mensalidade.objects.filter(
        status="CANCELADO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    return render(

        request,

        "financeiro/fluxo_caixa.html",

        {

            "total_recebido": total_recebido,

            "em_aberto": em_aberto,

            "atrasadas": atrasadas,

            "canceladas": canceladas,

        }

    )


@login_required
def dashboard_financeiro(request):

    hoje = timezone.now().date()

    mensalidades = Mensalidade.objects.all()

    total_recebido = mensalidades.filter(
        status="PAGO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    total_aberto = mensalidades.filter(
        status="ABERTO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    total_atrasado = mensalidades.filter(
        status="ATRASADO"
    ).aggregate(
        total=Sum("valor")
    )["total"] or 0

    quantidade_pagas = mensalidades.filter(
        status="PAGO"
    ).count()

    quantidade_abertas = mensalidades.filter(
        status="ABERTO"
    ).count()

    quantidade_atrasadas = mensalidades.filter(
        status="ATRASADO"
    ).count()

    return render(
        request,
        "financeiro/dashboard_financeiro.html",
        {
            "hoje": hoje,
            "total_recebido": total_recebido,
            "total_aberto": total_aberto,
            "total_atrasado": total_atrasado,
            "quantidade_pagas": quantidade_pagas,
            "quantidade_abertas": quantidade_abertas,
            "quantidade_atrasadas": quantidade_atrasadas,
        }
    )


@login_required
def exportar_financeiro_excel(request):

    workbook = openpyxl.Workbook()

    sheet = workbook.active

    sheet.title = "Financeiro"

    sheet.append([
        "Cliente",
        "Competência",
        "Vencimento",
        "Valor",
        "Status"
    ])

    mensalidades = Mensalidade.objects.select_related(
        "cliente"
    )

    for m in mensalidades:

        sheet.append([

            m.cliente.nome,

            m.competencia.strftime("%m/%Y"),

            m.vencimento.strftime("%d/%m/%Y"),

            float(m.valor),

            m.get_status_display(),

        ])

    response = HttpResponse(

        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    )

    response["Content-Disposition"] = "attachment; filename=financeiro.xlsx"

    workbook.save(response)

    return response


@login_required
def exportar_financeiro_pdf(request):

    response = HttpResponse(
        content_type="application/pdf"
    )

    response["Content-Disposition"] = "attachment; filename=financeiro.pdf"

    documento = SimpleDocTemplate(
        response,
        pagesize=letter
    )

    elementos = []

    estilos = getSampleStyleSheet()

    elementos.append(
        Paragraph(
            "<b>RELATÓRIO FINANCEIRO</b>",
            estilos["Title"]
        )
    )

    elementos.append(Spacer(1,20))

    dados = [

        [

            "Cliente",

            "Competência",

            "Valor",

            "Status"

        ]

    ]

    mensalidades = Mensalidade.objects.select_related(
        "cliente"
    )

    for m in mensalidades:

        dados.append([

            m.cliente.nome,

            m.competencia.strftime("%m/%Y"),

            f"R$ {m.valor}",

            m.get_status_display(),

        ])

    tabela = Table(dados)

    tabela.setStyle(TableStyle([

        ("BACKGROUND",(0,0),(-1,0),colors.grey),

        ("TEXTCOLOR",(0,0),(-1,0),colors.white),

        ("GRID",(0,0),(-1,-1),1,colors.black),

        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),

        ("ALIGN",(0,0),(-1,-1),"CENTER"),

    ]))

    elementos.append(tabela)

    documento.build(elementos)

    return response