from django.urls import path

from .views import (
    lista_ctos,
    detalhe_cto,
    exportar_ctos_pdf,
    exportar_ctos_excel,
    nova_cto,
    editar_cto,
    excluir_cto,
)

urlpatterns = [

    path(
        '',
        lista_ctos,
        name='lista_ctos'
    ),

    path(
        'nova/',
        nova_cto,
        name='nova_cto'
    ),

    path(
        '<int:cto_id>/editar/',
        editar_cto,
        name='editar_cto'
    ),

    path(
        '<int:cto_id>/excluir/',
        excluir_cto,
        name='excluir_cto'
    ),

    path(
        '<int:cto_id>/',
        detalhe_cto,
        name='detalhe_cto'
    ),

    path(
        'exportar/pdf/',
        exportar_ctos_pdf,
        name='exportar_ctos_pdf'
    ),

    path(
        'exportar/excel/',
        exportar_ctos_excel,
        name='exportar_ctos_excel'
    ),

]