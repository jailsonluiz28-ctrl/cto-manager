from django.urls import path

from .views import (
    novo_cliente,
    lista_clientes,
    detalhe_cliente,
    portas_disponiveis,
    exportar_clientes_pdf,
    editar_cliente,
    excluir_cliente,
    historico_movimentacoes,
)

urlpatterns = [
    path(
        '',
        lista_clientes,
        name='lista_clientes'
    ),

    path(
        'novo/',
        novo_cliente,
        name='novo_cliente'
    ),

    path(
        '<int:cliente_id>/',
        detalhe_cliente,
        name='detalhe_cliente'
    ),

    path(
        '<int:cliente_id>/editar/',
        editar_cliente,
        name='editar_cliente'
    ),

    path(
        '<int:cliente_id>/excluir/',
        excluir_cliente,
        name='excluir_cliente'
    ),

    path(
        'portas/<int:cto_id>/',
        portas_disponiveis,
        name='portas_disponiveis'
    ),

    path(
        'exportar/pdf/',
        exportar_clientes_pdf,
        name='exportar_clientes_pdf'
    ),

    path(
        'historico/',
        historico_movimentacoes,
        name='historico'
    ),
]