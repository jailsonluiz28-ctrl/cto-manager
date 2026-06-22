from django.conf import settings

from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import (
    User,
    Group
)

from clientes.models import HistoricoMovimentacao

from django.shortcuts import (
    render,
    redirect
)

from django.http import FileResponse

from datetime import datetime

import os
import shutil


@login_required
def backup_sistema(request):

    os.makedirs(
        settings.BACKUP_DIR,
        exist_ok=True
    )

    data = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    nome_backup = (
        f"backup_cto_manager_{data}.sqlite3"
    )

    destino = (
        settings.BACKUP_DIR / nome_backup
    )

    banco = settings.BASE_DIR / "db.sqlite3"

    shutil.copy2(
        banco,
        destino
    )

    HistoricoMovimentacao.objects.create(
        usuario=request.user.username,
        cliente_nome="-",
        cto_nome="-",
        porta=0,
        acao="BACKUP GERADO",
        observacao=nome_backup
    )

    return FileResponse(
        open(destino, "rb"),
        as_attachment=True,
        filename=nome_backup
    )


@login_required
def lista_backups(request):

    os.makedirs(
        settings.BACKUP_DIR,
        exist_ok=True
    )

    arquivos = []

    for arquivo in os.listdir(
        settings.BACKUP_DIR
    ):

        arquivos.append(
            arquivo
        )

    arquivos.sort(
        reverse=True
    )

    return render(
        request,
        "sistema/backups.html",
        {
            "arquivos": arquivos
        }
    )


@login_required
def lista_usuarios(request):

    if not request.user.is_superuser:
        return redirect("/")

    usuarios = User.objects.all().order_by(
        'username'
    )

    return render(
        request,
        'sistema/usuarios.html',
        {
            'usuarios': usuarios
        }
    )


@login_required
def novo_usuario(request):

    if not request.user.is_superuser:
        return redirect("/")

    if request.method == "POST":

        username = request.POST.get(
            "username"
        )

        senha = request.POST.get(
            "senha"
        )

        email = request.POST.get(
            "email"
        )

        grupo_nome = request.POST.get(
            "grupo"
        )

        usuario = User.objects.create_user(
            username=username,
            password=senha,
            email=email
        )

        if grupo_nome:

            grupo = Group.objects.get(
                name=grupo_nome
            )

            usuario.groups.add(
                grupo
            )

            if grupo_nome == "Administrador":

                usuario.is_staff = True
                usuario.is_superuser = True

                usuario.save()

        HistoricoMovimentacao.objects.create(
            usuario=request.user.username,
            cliente_nome=username,
            cto_nome="-",
            porta=0,
            acao="USUÁRIO CRIADO",
            observacao=f"Grupo: {grupo_nome}"
        )

        return redirect(
            "/sistema/usuarios/"
        )

    return render(
        request,
        "sistema/novo_usuario.html"
    )


@login_required
def alterar_status_usuario(
    request,
    user_id
):

    if not request.user.is_superuser:
        return redirect("/")

    usuario = User.objects.get(
        id=user_id
    )

    # Impede desativar o próprio usuário
    if usuario == request.user:

        return redirect(
            "/sistema/usuarios/"
        )

    # Impede desativar o último administrador ativo
    if (
        usuario.is_superuser
        and
        usuario.is_active
    ):

        admins_ativos = User.objects.filter(
            is_superuser=True,
            is_active=True
        ).count()

        if admins_ativos <= 1:

            return redirect(
                "/sistema/usuarios/"
            )

    novo_status = (
        not usuario.is_active
    )

    usuario.is_active = novo_status

    usuario.save()

    HistoricoMovimentacao.objects.create(
        usuario=request.user.username,
        cliente_nome=usuario.username,
        cto_nome="-",
        porta=0,
        acao=(
            "USUÁRIO ATIVADO"
            if novo_status
            else "USUÁRIO DESATIVADO"
        ),
        observacao=""
    )

    return redirect(
        "/sistema/usuarios/"
    )


@login_required
def restaurar_backup(request):

    # Apenas administrador pode restaurar
    if not request.user.is_superuser:

        return redirect("/")

    arquivo = request.GET.get(
        "arquivo"
    )

    confirmado = False

    if request.method == "POST":

        confirmado = True

    return render(
        request,
        "sistema/restaurar_backup.html",
        {
            "arquivo": arquivo,
            "confirmado": confirmado,
        }
    )


@login_required
def editar_usuario(
    request,
    user_id
):

    if not request.user.is_superuser:
        return redirect("/")

    usuario = User.objects.get(
        id=user_id
    )

    if request.method == "POST":

        usuario.username = request.POST.get(
            "username"
        )

        usuario.email = request.POST.get(
            "email"
        )

        grupo_nome = request.POST.get(
            "grupo"
        )

        senha = request.POST.get(
            "senha"
        )

        usuario.groups.clear()

        if grupo_nome:

            grupo = Group.objects.get(
                name=grupo_nome
            )

            usuario.groups.add(
                grupo
            )

            if grupo_nome == "Administrador":

                usuario.is_staff = True
                usuario.is_superuser = True

            else:

                usuario.is_staff = False
                usuario.is_superuser = False

        if senha:

            usuario.set_password(
                senha
            )

        usuario.save()

        HistoricoMovimentacao.objects.create(
            usuario=request.user.username,
            cliente_nome=usuario.username,
            cto_nome="-",
            porta=0,
            acao="USUÁRIO EDITADO",
            observacao=f"Grupo: {grupo_nome}"
        )

        return redirect(
            "/sistema/usuarios/"
        )

    grupos = Group.objects.all()

    return render(
        request,
        "sistema/editar_usuario.html",
        {
            "usuario_obj": usuario,
            "grupos": grupos,
        }
    )


@login_required
def excluir_usuario(
    request,
    user_id
):

    if not request.user.is_superuser:
        return redirect("/")

    usuario = User.objects.get(
        id=user_id
    )

    # Não permite excluir a si mesmo
    if usuario == request.user:

        return redirect(
            "/sistema/usuarios/"
        )

    # Não permite excluir o último administrador
    if usuario.is_superuser:

        admins = User.objects.filter(
            is_superuser=True
        ).count()

        if admins <= 1:

            return redirect(
                "/sistema/usuarios/"
            )

    if request.method == "POST":

        HistoricoMovimentacao.objects.create(
            usuario=request.user.username,
            cliente_nome=usuario.username,
            cto_nome="-",
            porta=0,
            acao="USUÁRIO EXCLUÍDO",
            observacao=""
        )

        usuario.delete()

        return redirect(
            "/sistema/usuarios/"
        )

    return render(
        request,
        "sistema/excluir_usuario.html",
        {
            "usuario_obj": usuario
        }
    )