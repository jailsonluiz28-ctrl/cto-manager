from django.urls import path

from .views import (
    backup_sistema,
    lista_backups,
    lista_usuarios,
    novo_usuario,
    alterar_status_usuario,
    restaurar_backup,
    editar_usuario,
    excluir_usuario,
)

urlpatterns = [

    path(
        "backup/",
        backup_sistema,
        name="backup_sistema"
    ),

    path(
        "backups/",
        lista_backups,
        name="lista_backups"
    ),

    path(
        "restaurar/",
        restaurar_backup,
        name="restaurar_backup"
    ),

    path(
        "usuarios/",
        lista_usuarios,
        name="usuarios"
    ),

    path(
        "usuarios/novo/",
        novo_usuario,
        name="novo_usuario"
    ),

    path(
        "usuarios/status/<int:user_id>/",
        alterar_status_usuario,
        name="alterar_status_usuario"
    ),

    path(
        "usuarios/editar/<int:user_id>/",
        editar_usuario,
        name="editar_usuario"
    ),

    path(
        "usuarios/excluir/<int:user_id>/",
        excluir_usuario,
        name="excluir_usuario"
    ),
]