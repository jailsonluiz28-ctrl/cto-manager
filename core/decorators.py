from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def somente_operacao(view_func):
    """Bloqueia técnicos de acessarem telas administrativas/operacionais."""
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role == "tecnico":
            messages.warning(request, "Essa área não está disponível para o perfil de técnico.")
            return redirect("meus_chamados")
        return view_func(request, *args, **kwargs)
    return wrapped


def somente_admin(view_func):
    """Bloqueia quem não é Administrador (Operador e Técnico não entram) — usado nas
    telas financeiras, que agora são exclusivas do Administrador."""
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != "admin":
            messages.warning(request, "Essa área é exclusiva do Administrador.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapped
