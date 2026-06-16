from django.urls import path

from .views import (
    lista_ctos,
    detalhe_cto,
    exportar_ctos_excel,
    exportar_ctos_pdf,
    nova_cto,
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
        '<int:cto_id>/',
        detalhe_cto,
        name='detalhe_cto'
    ),

    path(
        'exportar/excel/',
        exportar_ctos_excel,
        name='exportar_ctos_excel'
    ),

    path(
        'exportar/pdf/',
        exportar_ctos_pdf,
        name='exportar_ctos_pdf'
    ),
]