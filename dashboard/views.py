from django.shortcuts import render
from django.db.models import Q
import unicodedata

from ctos.models import CTO
from clientes.models import Cliente


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


def home(request):

    total_ctos = CTO.objects.count()

    total_clientes = Cliente.objects.count()

    ctos_ocupadas = CTO.objects.filter(
        portas_ocupadas__gt=0
    ).count()

    portas_livres = 0

    for cto in CTO.objects.all():
        portas_livres += (
            cto.portas_total - cto.portas_ocupadas
        )

    busca = request.GET.get('busca', '').strip()

    cto_encontrada = None
    ctos_encontradas = []

    clientes_cto = []

    portas_livres_cto = None

    mapa_portas = []

    clientes_encontrados = []

    if busca:

        busca_normalizada = remover_acentos(busca)

        #
        # BUSCA DE CLIENTES
        #
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

            'cto_encontrada': cto_encontrada,

            'ctos_encontradas': ctos_encontradas,

            'clientes_cto': clientes_cto,

            'portas_livres_cto': portas_livres_cto,

            'mapa_portas': mapa_portas,

            'clientes_encontrados': clientes_encontrados,

            'busca': busca,
        }
    )