import threading

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


class CurrentUserMiddleware:
    """Guarda o usuário da requisição atual para os sinais de auditoria conseguirem
    registrar 'quem fez o quê', mesmo dentro de signals que não recebem o request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, "user", None)
        response = self.get_response(request)
        _thread_locals.user = None
        return response


class LicencaMiddleware:
    """Se a licença do sistema estiver vencida (ou bloqueada manualmente),
    trava o acesso de TODO MUNDO — equipe e Portal do Cliente — mostrando uma
    tela de "sistema bloqueado". Só quem tem conta de superusuário (o dono do
    sistema, não o cliente que alugou) consegue passar por essa trava, pra
    poder entrar e renovar a licença."""

    CAMINHOS_LIBERADOS = ("/static/", "/media/", "/sw.js", "/login/", "/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_superuser", False):
            return self.get_response(request)

        caminho = request.path
        if any(caminho.startswith(c) for c in self.CAMINHOS_LIBERADOS):
            return self.get_response(request)

        try:
            from .models import LicencaSistema
            licenca = LicencaSistema.obter()
            bloqueado = licenca.esta_bloqueado()
        except Exception:
            bloqueado = False  # nunca deixa um problema na checagem de licença travar o sistema à toa

        if bloqueado:
            from django.shortcuts import render
            return render(request, "core/sistema_bloqueado.html", {"licenca": licenca}, status=403)

        return self.get_response(request)


class PontoObrigatorioMiddleware:
    """Trava o acesso de Operador e Técnico ao resto do sistema enquanto eles não
    baterem o ponto de entrada. Depois que baterem a saída final do dia, ficam
    travados de novo até baterem o ponto no dia seguinte. O Administrador nunca
    é afetado por essa trava."""

    CAMINHOS_LIBERADOS = ("/ponto/", "/logout/", "/sw.js", "/static/", "/media/", "/portal/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "role", None) in ("operador", "tecnico"):
            caminho = request.path
            liberado = any(caminho.startswith(c) for c in self.CAMINHOS_LIBERADOS)
            if not liberado:
                from django.shortcuts import redirect
                from django.contrib import messages
                from .utils import esta_em_expediente

                if not esta_em_expediente(user):
                    messages.warning(request, "Bata o ponto de entrada para acessar o sistema.")
                    return redirect("ponto_bater")
        return self.get_response(request)
