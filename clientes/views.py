from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.http import (
    JsonResponse,
    HttpResponse
)

from django.db.models import Q

from .forms import ClienteForm
from .models import Cliente
from ctos.models import CTO

import openpyxl

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

from datetime import datetime

from django.contrib.auth.decorators import login_required


@login_required
def lista_clientes(request):

    busca = request.GET.get('busca', '').strip()

    clientes = Cliente.objects.select_related(
        'cto'
    ).all()

    if busca:

        clientes = clientes.filter(
            Q(nome__icontains=busca) |
            Q(cto__nome__icontains=busca) |
            Q(cto__rua__icontains=busca)
        )

    return render(
        request,
        'clientes/lista_clientes.html',
        {
            'clientes': clientes,
            'busca': busca,
        }
    )


@login_required
def detalhe_cliente(request, cliente_id):

    cliente = get_object_or_404(
        Cliente.objects.select_related('cto'),
        id=cliente_id
    )

    return render(
        request,
        'clientes/detalhe_cliente.html',
        {
            'cliente': cliente,
        }
    )


@login_required
def novo_cliente(request):

    if request.method == 'POST':

        form = ClienteForm(request.POST)

        if form.is_valid():

            form.save()

            return redirect('/clientes/')

    else:

        form = ClienteForm()

    return render(
        request,
        'clientes/novo_cliente.html',
        {
            'form': form
        }
    )


@login_required
def portas_disponiveis(request, cto_id):

    try:

        cto = CTO.objects.get(id=cto_id)

        portas_ocupadas = Cliente.objects.filter(
            cto=cto
        ).values_list(
            'porta',
            flat=True
        )

        portas = []

        for numero in range(
            1,
            cto.portas_total + 1
        ):

            if numero not in portas_ocupadas:

                portas.append({
                    'numero': numero,
                    'texto': f'Porta {numero}'
                })

        return JsonResponse({
            'portas': portas
        })

    except CTO.DoesNotExist:

        return JsonResponse({
            'portas': []
        })


@login_required
def exportar_clientes_excel(request):

    workbook = openpyxl.Workbook()

    worksheet = workbook.active

    worksheet.title = 'Clientes'

    worksheet.append([
        'Cliente',
        'CTO',
        'Porta',
    ])

    clientes = Cliente.objects.select_related(
        'cto'
    ).all()

    for cliente in clientes:

        worksheet.append([
            cliente.nome,
            cliente.cto.nome,
            cliente.porta,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    response['Content-Disposition'] = (
        'attachment; filename=clientes.xlsx'
    )

    workbook.save(response)

    return response


@login_required
def exportar_clientes_pdf(request):

    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'attachment; filename=clientes.pdf'
    )

    documento = SimpleDocTemplate(
        response,
        pagesize=letter
    )

    elementos = []

    estilos = getSampleStyleSheet()

    elementos.append(
        Paragraph(
            "<b>RELATÓRIO DE CLIENTES</b>",
            estilos['Title']
        )
    )

    elementos.append(
        Paragraph(
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            estilos['Normal']
        )
    )

    elementos.append(Spacer(1, 20))

    dados = [
        ['Cliente', 'CTO', 'Porta']
    ]

    clientes = Cliente.objects.select_related(
        'cto'
    ).all()

    for cliente in clientes:

        dados.append([
            cliente.nome,
            cliente.cto.nome,
            str(cliente.porta),
        ])

    tabela = Table(
        dados,
        colWidths=[220, 220, 80]
    )

    tabela.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ])
    )

    elementos.append(tabela)

    documento.build(elementos)

    return response