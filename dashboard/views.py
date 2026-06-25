from django.shortcuts import render
from django.db.models import Q, F
from django.contrib.auth.decorators import login_required
from django.db import models
import unicodedata
import os
import shutil

from django.conf import settings
from django.http import FileResponse
from django.contrib.admin.views.decorators import staff_member_required

from ctos.models import CTO
from clientes.models import (
    Cliente,
    HistoricoMovimentacao
)


def remover_acentos(texto):
    """
    Remove acentos e deixa tudo minúsculo.
    Exemplo:
    João -> joao
    Ávila -> avila
    """
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower()


@login_required
def home(request):

    total_ctos = CTO.objects.count()

    total_clientes = Cliente.objects.count()

    ctos_ocupadas = CTO.objects.filter(
        portas_ocupadas__gt=0
    ).count()

    portas_livres = 0
    portas_totais = 0

    for cto in CTO.objects.all():

        portas_totais += cto.portas_total

        portas_livres += (
            cto.portas_total - cto.portas_ocupadas
        )

    portas_ocupadas_total = (
        portas_totais - portas_livres
    )

    if portas_totais > 0:

        percentual_ocupado = round(
            (portas_ocupadas_total / portas_totais) * 100,
            1
        )

        percentual_livre = round(
            (portas_livres / portas_totais) * 100,
            1
        )

    else:

        percentual_ocupado = 0

        percentual_livre = 0


    ctos_lotadas = CTO.objects.filter(
        portas_ocupadas=models.F('portas_total')
    )

    quantidade_ctos_lotadas = ctos_lotadas.count()

    ultimas_movimentacoes = (
        HistoricoMovimentacao.objects
        .all()
        .order_by('-data')[:10]
    )

    ctos_uma_vaga = 0

    ctos_disponiveis = 0

    for cto in CTO.objects.all():

        vagas = (
            cto.portas_total
            -
            cto.portas_ocupadas
        )

        if vagas == 1:

            ctos_uma_vaga += 1

        elif vagas > 1:

            ctos_disponiveis += 1

    busca = request.GET.get('busca', '').strip()

    cto_encontrada = None
    ctos_encontradas = []
    mapas_ctos = []
    total_vagas_rua = 0

    clientes_cto = []

    portas_livres_cto = None

    mapa_portas = []

    clientes_encontrados = []

    if busca:

        busca_normalizada = remover_acentos(busca)

        #
        # BUSCA DE CLIENTES
        #
        if not request.user.groups.filter(
            name='Tecnico'
        ).exists():

            todos_clientes = Cliente.objects.select_related(
                'cto'
            ).all()

            for cliente in todos_clientes:

                nome_normalizado = remover_acentos(
                    cliente.nome
                )

                if busca_normalizada in nome_normalizado:

                    clientes_encontrados.append(
                        cliente
                    )

        #
        # BUSCA DE CTOs
        #
        todas_ctos = CTO.objects.all()

        for cto in todas_ctos:

            nome_cto = remover_acentos(
                cto.nome
            )

            rua_cto = remover_acentos(
                cto.rua
            )

            if (
                busca_normalizada in nome_cto
                or
                busca_normalizada in rua_cto
            ):

                ctos_encontradas.append(
                    cto
                )

        #
        # DETALHES DA PRIMEIRA CTO
        #
        if ctos_encontradas:

            cto_encontrada = ctos_encontradas[0]

            clientes_cto = Cliente.objects.filter(
                cto=cto_encontrada
            ).order_by('porta')

            for cto in ctos_encontradas:

                clientes_da_cto = Cliente.objects.filter(
                    cto=cto
                )

                vagas_livres = (
                    cto.portas_total
                    -
                    cto.portas_ocupadas
                )

                total_vagas_rua += vagas_livres

                portas = []

                for numero in range(
                    1,
                    cto.portas_total + 1
                ):

                    ocupada = clientes_da_cto.filter(
                        porta=numero
                    ).exists()

                    portas.append({
                        'numero': numero,
                        'ocupada': ocupada
                    })

                clientes_detalhes = []

                for numero in range(
                    1,
                    cto.portas_total + 1
                ):

                    cliente = clientes_da_cto.filter(
                        porta=numero
                    ).first()

                    if cliente:

                        clientes_detalhes.append({
                            'porta': numero,
                            'cliente': cliente.nome,
                            'ocupada': True
                        })

                    else:

                        clientes_detalhes.append({
                            'porta': numero,
                            'cliente': 'Livre',
                            'ocupada': False
                        })

                mapas_ctos.append({
                    'cto': cto,
                    'vagas_livres': vagas_livres,
                    'portas': portas,
                    'clientes': clientes_detalhes
                })

            portas_livres_cto = (
                cto_encontrada.portas_total
                -
                cto_encontrada.portas_ocupadas
            )

            for numero in range(
                1,
                cto_encontrada.portas_total + 1
            ):

                cliente_porta = clientes_cto.filter(
                    porta=numero
                ).first()

                if cliente_porta:

                    mapa_portas.append({
                        "numero": numero,
                        "status": "ocupada",
                        "cliente": cliente_porta.nome,
                    })

                else:

                    mapa_portas.append({
                        "numero": numero,
                        "status": "livre",
                        "cliente": None,
                    })

    return render(
        request,
        'dashboard/home.html',
        {
            'total_ctos': total_ctos,

            'total_clientes': total_clientes,

            'ctos_ocupadas': ctos_ocupadas,

            'portas_livres': portas_livres,

            'percentual_ocupado': percentual_ocupado,

            'percentual_livre': percentual_livre,

            'quantidade_ctos_lotadas': quantidade_ctos_lotadas,

            'ctos_uma_vaga': ctos_uma_vaga,

            'ctos_disponiveis': ctos_disponiveis,

            'ctos_lotadas': ctos_lotadas,

            'cto_encontrada': cto_encontrada,

            'ctos_encontradas': ctos_encontradas,

            'mapas_ctos': mapas_ctos,

            'total_vagas_rua': total_vagas_rua,

            'clientes_cto': clientes_cto,

            'portas_livres_cto': portas_livres_cto,

            'mapa_portas': mapa_portas,

            'clientes_encontrados': clientes_encontrados,

            'busca': busca,

            'eh_admin': request.user.groups.filter(
                name='Administrador'
            ).exists(),

            'eh_operador': request.user.groups.filter(
                name='Operador'
            ).exists(),

            'eh_tecnico': request.user.groups.filter(
                name='Tecnico'
            ).exists(),

            'ultimas_movimentacoes': ultimas_movimentacoes,
        }
    )


@staff_member_required
def gerar_backup(request):

    banco = settings.BASE_DIR / 'db.sqlite3'

    pasta_backup = settings.BASE_DIR / 'backups'

    os.makedirs(
        pasta_backup,
        exist_ok=True
    )

    from datetime import datetime

    nome_arquivo = (
        f'backup_'
        f'{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        '.sqlite3'
    )

    destino = pasta_backup / nome_arquivo

    shutil.copy2(
        banco,
        destino
    )

    return FileResponse(
        open(destino, 'rb'),
        as_attachment=True,
        filename=nome_arquivo
    )


@login_required
def lista_ctos_lotadas(request):

    ctos_lotadas = CTO.objects.filter(
        portas_ocupadas=models.F('portas_total')
    )

    return render(
        request,
        'dashboard/ctos_lotadas.html',
        {
            'ctos_lotadas': ctos_lotadas
        }
    )