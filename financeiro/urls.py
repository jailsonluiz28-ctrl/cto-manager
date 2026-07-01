from django.urls import path

from .views import (

    lista_mensalidades,

    nova_mensalidade,

    detalhe_mensalidade,

    receber_mensalidade,

    inadimplentes,

    fluxo_caixa,

    dashboard_financeiro,

    exportar_financeiro_pdf,

    exportar_financeiro_excel,

)

urlpatterns = [

    path(
        "",
        lista_mensalidades,
        name="financeiro",
    ),

    path(
        "inadimplentes/",
        inadimplentes,
        name="inadimplentes",
    ),

    path(
        "fluxo/",
        fluxo_caixa,
        name="fluxo_caixa",
    ),

    path(
        "dashboard/",
        dashboard_financeiro,
        name="dashboard_financeiro",
    ),

    path(
        "exportar/pdf/",
        exportar_financeiro_pdf,
        name="financeiro_pdf",
    ),

    path(
        "exportar/excel/",
        exportar_financeiro_excel,
        name="financeiro_excel",
    ),

    path(
        "nova/",
        nova_mensalidade,
        name="nova_mensalidade",
    ),

    path(
        "<int:mensalidade_id>/receber/",
        receber_mensalidade,
        name="receber_mensalidade",
    ),

    path(
        "<int:mensalidade_id>/",
        detalhe_mensalidade,
        name="detalhe_mensalidade",
    ),

]