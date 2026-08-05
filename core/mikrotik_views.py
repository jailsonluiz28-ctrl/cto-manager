"""Views da integração com Mikrotik: tela de configuração (host/usuário/senha
+ testar conexão) e as ações disparadas manualmente por cliente (sincronizar
velocidade/status, bloquear, liberar)."""

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Cliente, ConfiguracaoMikrotik, LogAtividade
from .mikrotik_utils import testar_conexao, sincronizar_cliente, bloquear_cliente, liberar_cliente, MikrotikErro


def _somente_admin(u):
    return u.is_authenticated and u.role == "admin"


def _registrar(usuario, acao, detalhes=""):
    LogAtividade.objects.create(usuario=usuario, acao=acao, detalhes=detalhes)


@user_passes_test(_somente_admin)
def configuracao_mikrotik_editar(request):
    config = ConfiguracaoMikrotik.obter()
    if request.method == "POST":
        # Salva sempre os dados digitados primeiro — tanto pra "Salvar" quanto
        # pra "Testar conexão", assim o teste usa o que a pessoa acabou de
        # digitar, não uma configuração antiga que ainda não tinha sido salva.
        config.ativo = request.POST.get("ativo") == "on"
        config.host = request.POST.get("host", "").strip()
        try:
            config.porta = int(request.POST.get("porta", 8728))
        except (TypeError, ValueError):
            config.porta = 8728
        config.usuario = request.POST.get("usuario", "admin").strip() or "admin"
        nova_senha = request.POST.get("senha", "")
        if nova_senha:
            config.senha = nova_senha
        config.usar_ssl = request.POST.get("usar_ssl") == "on"
        config.save()

        if request.POST.get("acao") == "testar":
            try:
                mensagem = testar_conexao()
                config.ultimo_teste_ok = True
                config.ultimo_teste_mensagem = mensagem
            except MikrotikErro as e:
                config.ultimo_teste_ok = False
                config.ultimo_teste_mensagem = str(e)
            config.ultimo_teste_em = timezone.now()
            config.save()
            if config.ultimo_teste_ok:
                messages.success(request, config.ultimo_teste_mensagem)
            else:
                messages.error(request, config.ultimo_teste_mensagem)
        else:
            messages.success(request, "Configuração do Mikrotik salva!")
        return redirect("configuracao_mikrotik_editar")

    return render(request, "core/configuracao_mikrotik_form.html", {"config": config})


@user_passes_test(_somente_admin)
def cliente_mikrotik_sincronizar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    try:
        mensagem = sincronizar_cliente(cliente)
        messages.success(request, f"{cliente.nome}: {mensagem}")
        _registrar(request.user, "Mikrotik - Sincronizado", f"{cliente.nome} — {mensagem}")
    except MikrotikErro as e:
        messages.error(request, f"{cliente.nome}: {e}")
        _registrar(request.user, "Mikrotik - Sincronização falhou", f"{cliente.nome} — {e}")
    return redirect(request.META.get("HTTP_REFERER") or "cliente_list")


@user_passes_test(_somente_admin)
def cliente_mikrotik_bloquear(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    try:
        mensagem = bloquear_cliente(cliente)
        messages.success(request, f"{cliente.nome}: {mensagem}")
        _registrar(request.user, "Mikrotik - Cliente bloqueado", f"{cliente.nome} — {mensagem}")
    except MikrotikErro as e:
        messages.error(request, f"{cliente.nome}: {e}")
        _registrar(request.user, "Mikrotik - Bloqueio falhou", f"{cliente.nome} — {e}")
    return redirect(request.META.get("HTTP_REFERER") or "cliente_list")


@user_passes_test(_somente_admin)
def cliente_mikrotik_liberar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    try:
        mensagem = liberar_cliente(cliente)
        messages.success(request, f"{cliente.nome}: {mensagem}")
        _registrar(request.user, "Mikrotik - Cliente liberado", f"{cliente.nome} — {mensagem}")
    except MikrotikErro as e:
        messages.error(request, f"{cliente.nome}: {e}")
        _registrar(request.user, "Mikrotik - Liberação falhou", f"{cliente.nome} — {e}")
    return redirect(request.META.get("HTTP_REFERER") or "cliente_list")
