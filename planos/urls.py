from django.urls import path

from .views import (

    lista_planos,

    novo_plano,

    editar_plano,

    detalhe_plano,

    excluir_plano,

    plano_json,

)

urlpatterns = [

    path(
        "",
        lista_planos,
        name="lista_planos",
    ),

    path(
        "novo/",
        novo_plano,
        name="novo_plano",
    ),

    path(
        "<int:plano_id>/",
        detalhe_plano,
        name="detalhe_plano",
    ),

    path(
        "<int:plano_id>/editar/",
        editar_plano,
        name="editar_plano",
    ),

    path(
        "<int:plano_id>/excluir/",
        excluir_plano,
        name="excluir_plano",
    ),

    path(
        "api/<int:plano_id>/",
        plano_json,
        name="plano_json",
    ),

]