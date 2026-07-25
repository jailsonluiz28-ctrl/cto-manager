import json
from datetime import date, timedelta

import openpyxl
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from django.db import models
from django.db.models import Sum, Q

from .models import Plano, CTO, Cliente, Chamado, ContaPagar, ChamadoAnexo, LogAtividade, Pagamento, MovimentacaoReceita
from .forms import ClienteForm, ChamadoForm, ContaPagarForm, CTOForm, PlanoForm, UsuarioCreateForm, UsuarioUpdateForm
from .decorators import somente_operacao
from .mixins import SomenteAdminMixin, SomenteOperacaoMixin
from django.contrib.auth.models import Group, Permission
from .utils import normalizar, rotulo_permissao, MODELO_LABELS, ACAO_LABELS
from accounts.models import User


def _somente_tecnico(user):
    return user.is_authenticated and user.role == "tecnico"


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    if request.user.role == "tecnico":
        return redirect("meus_chamados")

    clientes = Cliente.objects.all()
    ctos = CTO.objects.all()
    total_portas = sum(c.capacidade for c in ctos) or 0
    portas_ocupadas = sum(c.portas_ocupadas() for c in ctos) or 0

    context = {
        "total_ctos": ctos.count(),
        "total_clientes": clientes.count(),
        "ctos_ocupadas": sum(1 for c in ctos if c.portas_ocupadas() > 0),
        "ctos_lotadas": [c for c in ctos if c.esta_lotada()],
        "total_portas": total_portas,
        "portas_ocupadas": portas_ocupadas,
        "portas_livres": total_portas - portas_ocupadas,
        "rede_livre_pct": round(((total_portas - portas_ocupadas) / total_portas) * 100, 1) if total_portas else 0,
        "rede_ocupada_pct": round((portas_ocupadas / total_portas) * 100, 1) if total_portas else 0,
        "clientes_recentes": clientes.select_related("plano", "cto")[:5],
        "chamados_abertos": Chamado.objects.exclude(status__in=["concluido", "cancelado"]).count(),
        "chamados_em_atendimento": Chamado.objects.filter(status="andamento").count(),
        "inadimplentes": clientes.filter(status="inadimplente").count(),
    }

    if request.user.role == "admin":
        context["logs_recentes"] = LogAtividade.objects.select_related("usuario")[:15]

    return render(request, "core/dashboard.html", context)


@login_required
def cliente_busca_json(request):
    """Busca livre de cliente por nome, login PPPoE, rua, telefone ou CPF —
    usada pelo campo de busca ao abrir um chamado."""
    termo = request.GET.get("q", "").strip()
    if len(termo) < 2:
        return JsonResponse({"resultados": []})

    alvo = normalizar(termo)
    candidatos = Cliente.objects.exclude(status="inativo").select_related("cto")[:500]
    encontrados = []
    for c in candidatos:
        campos = [c.nome, c.login_pppoe, c.logradouro, c.telefone, c.cpf_cnpj]
        if any(alvo in normalizar(campo) for campo in campos if campo):
            encontrados.append({
                "id": c.id,
                "nome": c.nome,
                "detalhe": f"{c.telefone or '—'} · {c.endereco_completo()}",
            })
        if len(encontrados) >= 15:
            break
    return JsonResponse({"resultados": encontrados})


# ---------------------------------------------------------------------------
# CLIENTES (admin + operador)
# ---------------------------------------------------------------------------

class ClienteListView(SomenteOperacaoMixin, ListView):
    model = Cliente
    template_name = "core/cliente_list.html"
    context_object_name = "clientes"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("plano", "cto")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        busca = self.request.GET.get("q")
        if busca:
            alvo = normalizar(busca)
            ids_encontrados = [
                c.id for c in qs
                if alvo in normalizar(c.nome)
                or alvo in normalizar(c.cpf_cnpj)
                or alvo in normalizar(c.telefone)
                or alvo in normalizar(c.bairro)
                or alvo in normalizar(c.cto.codigo if c.cto else "")
            ]
            qs = qs.filter(id__in=ids_encontrados)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["busca"] = self.request.GET.get("q", "")
        context["status_filtro"] = self.request.GET.get("status", "")
        context["status_choices"] = Cliente.STATUS_CHOICES
        return context


class ClienteCreateView(SomenteOperacaoMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "core/cliente_form.html"
    success_url = reverse_lazy("cliente_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        MovimentacaoReceita.objects.create(
            cliente=self.object, tipo="novo_cliente",
            valor_anterior=0, valor_novo=self.object.valor_mensal(),
            criado_por=self.request.user,
        )
        messages.success(self.request, "Cliente cadastrado com sucesso!")
        return response


class ClienteUpdateView(SomenteOperacaoMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "core/cliente_form.html"
    success_url = reverse_lazy("cliente_list")

    def form_valid(self, form):
        cliente_antigo = Cliente.objects.get(pk=self.object.pk)
        valor_antigo = cliente_antigo.valor_mensal()
        plano_antigo_id = cliente_antigo.plano_id

        response = super().form_valid(form)

        valor_novo = self.object.valor_mensal()
        if self.object.plano_id != plano_antigo_id and valor_novo != valor_antigo:
            tipo = "upgrade" if valor_novo > valor_antigo else "downgrade"
            MovimentacaoReceita.objects.create(
                cliente=self.object, tipo=tipo,
                valor_anterior=valor_antigo, valor_novo=valor_novo,
                criado_por=self.request.user,
            )
        messages.success(self.request, "Dados do cliente atualizados!")
        return response


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        nome = cliente.nome
        cliente.delete()
        messages.success(request, f"Cliente \"{nome}\" foi excluído permanentemente do sistema.")
        return redirect("cliente_list")
    return render(request, "core/cliente_confirm_delete.html", {"cliente": cliente})


@login_required
def cto_portas_livres(request, pk):
    cto = get_object_or_404(CTO, pk=pk)
    livres = cto.portas_disponiveis()
    cliente_id = request.GET.get("cliente_id")
    if cliente_id:
        try:
            cliente = Cliente.objects.get(pk=cliente_id, cto_id=pk)
            if cliente.porta and cliente.porta not in livres:
                livres = sorted(livres + [cliente.porta])
        except Cliente.DoesNotExist:
            pass
    return JsonResponse({"portas": livres})


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def cliente_cancelar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo_cancelamento", "").strip()
        if not motivo:
            messages.error(request, "É obrigatório informar o motivo do cancelamento.")
            return redirect("cliente_cancelar", pk=pk)

        valor_anterior = cliente.valor_mensal()
        cliente.status = "cancelado"
        cliente.motivo_cancelamento = motivo
        cliente.data_cancelamento = timezone.now().date()
        cliente.save()

        MovimentacaoReceita.objects.create(
            cliente=cliente, tipo="cancelamento",
            valor_anterior=valor_anterior, valor_novo=0,
            criado_por=request.user,
        )
        messages.success(request, f"Cliente \"{cliente.nome}\" marcado como cancelado.")
        return redirect("cliente_list")
    return render(request, "core/cliente_cancelar.html", {"cliente": cliente})


class ClienteCanceladosListView(SomenteOperacaoMixin, ListView):
    model = Cliente
    template_name = "core/cliente_cancelados.html"
    context_object_name = "clientes"

    def get_queryset(self):
        return Cliente.objects.filter(status="cancelado").select_related("plano", "cto").order_by("-data_cancelamento")


# ---------------------------------------------------------------------------
# CTOs (leitura: qualquer perfil logado / escrita: admin+operador)
# ---------------------------------------------------------------------------

class CTOListView(LoginRequiredMixin, ListView):
    model = CTO
    template_name = "core/cto_list.html"
    context_object_name = "ctos"

    def get_queryset(self):
        qs = super().get_queryset()
        busca = self.request.GET.get("q")
        if busca:
            alvo = normalizar(busca)
            ids_encontrados = [
                c.id for c in qs
                if alvo in normalizar(c.codigo) or alvo in normalizar(c.bairro) or alvo in normalizar(c.endereco)
                or any(alvo in normalizar(r) for r in c.lista_ruas())
            ]
            qs = qs.filter(id__in=ids_encontrados)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["busca"] = self.request.GET.get("q", "")
        return context


class CTODetailView(LoginRequiredMixin, DetailView):
    model = CTO
    context_object_name = "cto"

    def get_template_names(self):
        if self.request.user.role == "tecnico":
            return ["core/cto_detail_tecnico.html"]
        return ["core/cto_detail.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clientes_conectados"] = self.object.clientes.exclude(status="inativo")
        return context


class CTOCreateView(SomenteOperacaoMixin, CreateView):
    model = CTO
    form_class = CTOForm
    template_name = "core/cto_form.html"
    success_url = reverse_lazy("cto_list")

    def form_valid(self, form):
        messages.success(self.request, "CTO cadastrada com sucesso!")
        return super().form_valid(form)


class CTOUpdateView(SomenteOperacaoMixin, UpdateView):
    model = CTO
    form_class = CTOForm
    template_name = "core/cto_form.html"
    success_url = reverse_lazy("cto_list")

    def form_valid(self, form):
        messages.success(self.request, "CTO atualizada com sucesso!")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# PLANOS (admin + operador)
# ---------------------------------------------------------------------------

class PlanoListView(SomenteOperacaoMixin, ListView):
    model = Plano
    template_name = "core/plano_list.html"
    context_object_name = "planos"


class PlanoCreateView(SomenteOperacaoMixin, CreateView):
    model = Plano
    form_class = PlanoForm
    template_name = "core/plano_form.html"
    success_url = reverse_lazy("plano_list")

    def form_valid(self, form):
        messages.success(self.request, "Plano cadastrado com sucesso!")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# CHAMADOS — visão admin/operador (gestão completa)
# ---------------------------------------------------------------------------

class ChamadoListView(SomenteOperacaoMixin, ListView):
    model = Chamado
    template_name = "core/chamado_list.html"
    context_object_name = "chamados"

    def get_queryset(self):
        qs = super().get_queryset().exclude(status="concluido").select_related("cliente", "tecnico")
        status = self.request.GET.get("status")
        tecnico_id = self.request.GET.get("tecnico")
        if status:
            qs = qs.filter(status=status)
        if tecnico_id:
            qs = qs.filter(tecnico_id=tecnico_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tecnicos"] = User.objects.filter(role="tecnico")
        context["status_choices"] = [c for c in Chamado.STATUS_CHOICES if c[0] != "concluido"]
        context["prioridade_choices"] = Chamado.PRIORIDADE_CHOICES
        return context


class ChamadoCreateView(SomenteOperacaoMixin, CreateView):
    model = Chamado
    form_class = ChamadoForm
    template_name = "core/chamado_form.html"
    success_url = reverse_lazy("chamado_list")

    def get_initial(self):
        initial = super().get_initial()
        cliente_id = self.request.GET.get("cliente")
        if cliente_id:
            initial["cliente"] = cliente_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente_id = self.request.GET.get("cliente")
        if cliente_id:
            context["cliente_pre_selecionado"] = Cliente.objects.filter(pk=cliente_id).first()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        chamado = self.object

        limite = timezone.now() - timedelta(days=30)
        anterior = (
            Chamado.objects.filter(cliente=chamado.cliente, criado_em__gte=limite)
            .exclude(pk=chamado.pk)
            .order_by("-criado_em")
            .first()
        )
        if anterior:
            chamado.eh_retorno = True
            chamado.tecnico_ultimo_atendimento = anterior.tecnico
            chamado.prioridade = "extrema"
            chamado.save()
            messages.warning(
                self.request,
                f"Atenção: {chamado.cliente.nome} já abriu um chamado nos últimos 30 dias "
                f"(atendido por {anterior.tecnico or 'ninguém ainda'}). "
                f"Marcado automaticamente como RETORNO com prioridade Extrema.",
            )
        return response


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def reatribuir_chamado(request, pk):
    chamado = get_object_or_404(Chamado, pk=pk)
    if request.method == "POST":
        tecnico_id = request.POST.get("tecnico")
        chamado.tecnico_id = tecnico_id or None
        chamado.save()
    return redirect("chamado_list")


RANK_PRIORIDADE = {"extrema": 4, "alta": 3, "media": 2, "baixa": 1}


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def alterar_prioridade_chamado(request, pk):
    chamado = get_object_or_404(Chamado, pk=pk)
    if request.method == "POST":
        nova = request.POST.get("prioridade", chamado.prioridade)
        justificativa = request.POST.get("justificativa", "").strip()
        antiga = chamado.prioridade

        if nova != antiga:
            reducao = RANK_PRIORIDADE.get(nova, 0) < RANK_PRIORIDADE.get(antiga, 0)
            if reducao and not justificativa:
                messages.error(request, "É necessário justificar quando a prioridade é reduzida.")
                return redirect("chamado_list")

            chamado.prioridade = nova
            chamado.save()

            detalhes = f"Chamado #{chamado.id} ({chamado.cliente.nome}): {antiga} → {nova}"
            if justificativa:
                detalhes += f" — Justificativa: {justificativa}"
            LogAtividade.objects.create(usuario=request.user, acao="Prioridade do chamado alterada", detalhes=detalhes)
    return redirect("chamado_list")


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def cancelar_chamado(request, pk):
    chamado = get_object_or_404(Chamado, pk=pk)
    chamado.status = "cancelado"
    chamado.save()
    messages.success(request, f"Chamado #{chamado.id} cancelado.")
    return redirect("chamado_list")


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def voltar_chamado_aberto(request, pk):
    """Usado quando algo aconteceu com o técnico e o chamado precisa ser reaberto
    pra outro pegar."""
    chamado = get_object_or_404(Chamado, pk=pk)
    chamado.status = "aberto"
    chamado.tecnico = None
    chamado.pego_em = None
    chamado.save()
    messages.success(request, f"Chamado #{chamado.id} voltou para Aberto e está disponível de novo.")
    return redirect("chamado_list")


@user_passes_test(lambda u: u.is_authenticated and u.role in ("admin", "operador"))
def finalizar_chamado_operador(request, pk):
    """O operador finaliza um chamado no lugar do técnico (ex: técnico com problema)."""
    chamado = get_object_or_404(Chamado, pk=pk)
    if request.method == "POST":
        observacao = request.POST.get("observacao_fechamento", "").strip()
        if not observacao:
            messages.error(request, "Descreva o motivo antes de finalizar o chamado.")
            return redirect("finalizar_chamado_operador", pk=pk)
        chamado.observacao_fechamento = observacao
        chamado.status = "concluido"
        chamado.concluido_em = timezone.now()
        chamado.finalizado_por = request.user
        if not chamado.pego_em:
            chamado.pego_em = chamado.concluido_em
        chamado.save()
        if chamado.tecnico and chamado.tecnico != request.user:
            messages.success(
                request,
                f"Chamado #{chamado.id} finalizado por você — era o chamado do técnico "
                f"{chamado.tecnico.get_full_name() or chamado.tecnico.username}.",
            )
        else:
            messages.success(request, f"Chamado #{chamado.id} finalizado por você.")
        return redirect("chamado_list")
    return render(request, "core/chamado_finalizar_operador.html", {"chamado": chamado})


class ChamadoFinalizadosListView(SomenteOperacaoMixin, ListView):
    model = Chamado
    template_name = "core/chamado_finalizados.html"
    context_object_name = "chamados"

    def get_queryset(self):
        return Chamado.objects.filter(status="concluido").select_related("cliente", "tecnico")


# ---------------------------------------------------------------------------
# ÁREA DO TÉCNICO
# ---------------------------------------------------------------------------

@login_required
def meus_chamados(request):
    chamados = (
        Chamado.objects.filter(tecnico=request.user)
        .exclude(status__in=["cancelado", "concluido"])
        .select_related("cliente")
    )
    context = {
        "chamados": chamados,
        "abertos": chamados.filter(status="aberto").count(),
        "andamento": chamados.filter(status="andamento").count(),
        "concluidos": Chamado.objects.filter(tecnico=request.user, status="concluido").count(),
    }
    return render(request, "core/meus_chamados.html", context)


@user_passes_test(_somente_tecnico)
def chamados_disponiveis(request):
    """Lista todos os chamados em aberto. Os já assumidos por um técnico aparecem
    destacados/bloqueados, para nenhum outro técnico pegar o mesmo chamado."""
    chamados = (
        Chamado.objects.filter(status__in=["aberto", "andamento"])
        .exclude(status="cancelado")
        .select_related("cliente", "tecnico")
    )
    return render(request, "core/chamados_disponiveis.html", {"chamados": chamados})


@user_passes_test(_somente_tecnico)
def pegar_chamado(request, pk):
    chamado = get_object_or_404(Chamado, pk=pk)

    ja_tem_ativo = Chamado.objects.filter(
        tecnico=request.user, status__in=["aberto", "andamento"]
    ).exclude(pk=pk).exists()
    if ja_tem_ativo:
        messages.warning(request, "Você já tem um chamado em atendimento. Finalize-o antes de pegar outro.")
        return redirect("chamados_disponiveis")

    if chamado.tecnico_id is None:
        chamado.tecnico = request.user
        chamado.status = "andamento"
        chamado.pego_em = timezone.now()
        chamado.save()
        messages.success(request, f"Chamado #{chamado.id} atribuído a você.")
        return redirect("meus_chamados")
    else:
        messages.warning(request, "Esse chamado já foi assumido por outro técnico.")
    return redirect("chamados_disponiveis")


@login_required
def avancar_chamado(request, pk):
    """Usado só para o passo 'Iniciar atendimento' (aberto -> andamento).
    Para concluir, o técnico precisa passar pela tela de finalizar_chamado."""
    chamado = get_object_or_404(Chamado, pk=pk, tecnico=request.user)
    if chamado.status == "aberto":
        chamado.status = "andamento"
        chamado.save()
    return redirect("meus_chamados")


@login_required
def finalizar_chamado(request, pk):
    chamado = get_object_or_404(Chamado, pk=pk, tecnico=request.user)
    if request.method == "POST":
        observacao = request.POST.get("observacao_fechamento", "").strip()
        if not observacao:
            messages.error(request, "Descreva o que foi feito antes de concluir o chamado.")
            return redirect("finalizar_chamado", pk=pk)

        chamado.observacao_fechamento = observacao
        chamado.status = "concluido"
        chamado.concluido_em = timezone.now()
        chamado.finalizado_por = request.user
        chamado.save()

        for foto in request.FILES.getlist("fotos"):
            ChamadoAnexo.objects.create(chamado=chamado, imagem=foto)

        messages.success(request, f"Chamado #{chamado.id} concluído com sucesso!")
        return redirect("meus_chamados")

    return render(request, "core/chamado_finalizar.html", {"chamado": chamado})


def garantir_contas_recorrentes(ano_alvo, mes_alvo):
    """Garante que as contas fixas e parceladas já tenham uma cópia criada até o mês
    que está sendo visualizado na tela (não só até a data real de hoje)."""
    alvo = date(ano_alvo, mes_alvo, 1)
    raizes = ContaPagar.objects.filter(gerada_de__isnull=True).filter(Q(recorrente=True) | Q(total_parcelas__gt=1))

    for raiz in raizes:
        serie = list(ContaPagar.objects.filter(Q(pk=raiz.pk) | Q(gerada_de=raiz)).order_by("vencimento"))
        ultima = serie[-1]
        quantidade_existente = len(serie)
        seguranca = 0

        while ultima.vencimento.replace(day=1) < alvo and seguranca < 36:
            if not raiz.recorrente and quantidade_existente >= raiz.total_parcelas:
                break  # já geramos todas as parcelas dessa série, não cria mais

            mes_p = ultima.vencimento.month % 12 + 1
            ano_p = ultima.vencimento.year + (1 if ultima.vencimento.month == 12 else 0)
            dia_p = min(ultima.vencimento.day, 28)
            nova_data = date(ano_p, mes_p, dia_p)

            ultima = ContaPagar.objects.create(
                descricao=raiz.descricao, valor=ultima.valor, vencimento=nova_data,
                status="pendente", recorrente=raiz.recorrente, forma_pagamento=raiz.forma_pagamento,
                parcela_atual=(quantidade_existente + 1) if not raiz.recorrente else 1,
                total_parcelas=raiz.total_parcelas,
                gerada_de=raiz,
            )
            quantidade_existente += 1
            seguranca += 1


def _redirect_financeiro(request, aba="pagar"):
    mes = request.POST.get("mes") or request.GET.get("mes")
    ano = request.POST.get("ano") or request.GET.get("ano")
    url = "/financeiro/"
    if mes and ano:
        url += f"?mes={mes}&ano={ano}"
    return redirect(url + f"#{aba}")


# ---------------------------------------------------------------------------
# FINANCEIRO (admin + operador)
# ---------------------------------------------------------------------------

@somente_operacao
def financeiro(request):
    hoje = timezone.now().date()
    ano = int(request.GET.get("ano", hoje.year))
    mes = int(request.GET.get("mes", hoje.month))
    mes_ref = date(ano, mes, 1)

    garantir_contas_recorrentes(ano, mes)

    clientes = Cliente.objects.exclude(status="inativo").select_related("plano")
    esperado_mes = sum((c.valor_mensal() for c in clientes), 0)

    pagamentos_mes = Pagamento.objects.filter(mes_referencia=mes_ref)
    ids_pagos = set(pagamentos_mes.values_list("cliente_id", flat=True))
    recebido_mes = pagamentos_mes.aggregate(total=Sum("valor"))["total"] or 0
    falta_receber_mes = esperado_mes - recebido_mes

    clientes_status = []
    for c in clientes:
        eh_instalacao = (
            c.data_ativacao and c.data_ativacao.year == ano and c.data_ativacao.month == mes
        )
        clientes_status.append({"cliente": c, "pago": c.id in ids_pagos, "eh_instalacao": eh_instalacao and c.id not in ids_pagos})

    total_clientes_mes = clientes.count()
    pagos_count = len(ids_pagos)
    faltam_count = total_clientes_mes - pagos_count

    inadimplentes = clientes.filter(status="inadimplente")
    total_inadimplencia = sum((c.valor_mensal() for c in inadimplentes), 0)
    contas_pagar = ContaPagar.objects.filter(vencimento__year=ano, vencimento__month=mes)
    total_pagar = sum((c.valor for c in contas_pagar.exclude(status="pago")), 0)

    # Movimentação de receita do mês selecionado: quem entrou, quem cancelou, quem trocou de plano
    movs_mes = MovimentacaoReceita.objects.filter(criado_em__year=ano, criado_em__month=mes).select_related("cliente")
    novos = movs_mes.filter(tipo="novo_cliente")
    cancelamentos = movs_mes.filter(tipo="cancelamento")
    upgrades = movs_mes.filter(tipo="upgrade")
    downgrades = movs_mes.filter(tipo="downgrade")

    receita_nova = sum((m.valor_novo for m in novos), 0)
    receita_perdida = sum((m.valor_anterior for m in cancelamentos), 0)
    ajuste_planos = sum((m.diferenca() for m in upgrades), 0) + sum((m.diferenca() for m in downgrades), 0)
    saldo_mes = receita_nova - receita_perdida + ajuste_planos
    percentual_saldo = (saldo_mes / esperado_mes * 100) if esperado_mes else 0
    percentual_perdido = (receita_perdida / esperado_mes * 100) if esperado_mes else 0
    percentual_novo = (receita_nova / esperado_mes * 100) if esperado_mes else 0

    # Fluxo de caixa dos últimos 6 meses: entradas (pagamentos) x saídas (contas)
    base_mes = hoje.replace(day=1)
    meses_labels, entradas, saidas = [], [], []
    for i in range(5, -1, -1):
        ano_i = base_mes.year + ((base_mes.month - i - 1) // 12)
        mes_i = ((base_mes.month - i - 1) % 12) + 1
        ref = base_mes.replace(year=ano_i, month=mes_i)
        entrada_mes = Pagamento.objects.filter(mes_referencia=ref).aggregate(total=Sum("valor"))["total"] or 0
        saida_mes = ContaPagar.objects.filter(vencimento__year=ref.year, vencimento__month=ref.month).aggregate(
            total=Sum("valor")
        )["total"] or 0
        meses_labels.append(MESES_PT[mes_i][:3])
        entradas.append(float(entrada_mes))
        saidas.append(float(saida_mes))

    context = {
        "clientes_status": clientes_status,
        "mes_ref": mes_ref,
        "mes": mes,
        "ano": ano,
        "meses_opcoes": [(i, MESES_PT[i]) for i in range(1, 13)],
        "anos_opcoes": list(range(hoje.year - 1, hoje.year + 2)),
        "esperado_mes": esperado_mes,
        "recebido_mes": recebido_mes,
        "falta_receber_mes": falta_receber_mes,
        "total_clientes_mes": total_clientes_mes,
        "pagos_count": pagos_count,
        "faltam_count": faltam_count,
        "inadimplentes": inadimplentes,
        "total_inadimplencia": total_inadimplencia,
        "contas_pagar": contas_pagar,
        "total_pagar": total_pagar,
        "meses_labels": json.dumps(meses_labels),
        "entradas": json.dumps(entradas),
        "saidas": json.dumps(saidas),
        "novos_count": novos.count(),
        "cancelamentos_count": cancelamentos.count(),
        "receita_nova": receita_nova,
        "receita_perdida": receita_perdida,
        "ajuste_planos": ajuste_planos,
        "saldo_mes": saldo_mes,
        "percentual_saldo": percentual_saldo,
        "percentual_perdido": percentual_perdido,
        "percentual_novo": percentual_novo,
    }
    return render(request, "core/financeiro.html", context)


@somente_operacao
def registrar_pagamento(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    hoje = timezone.now().date()
    ano = int(request.POST.get("ano", hoje.year))
    mes = int(request.POST.get("mes", hoje.month))
    mes_ref = date(ano, mes, 1)

    Pagamento.objects.update_or_create(
        cliente=cliente, mes_referencia=mes_ref,
        defaults={"valor": cliente.valor_mensal(), "data_pagamento": hoje, "registrado_por": request.user},
    )
    if cliente.status == "inadimplente":
        cliente.status = "ativo"
        cliente.save()
    messages.success(request, f"Pagamento de {cliente.nome} registrado para {MESES_PT[mes]}/{ano}.")
    return redirect(f"/financeiro/?mes={mes}&ano={ano}")


@somente_operacao
def conta_pagar_create(request):
    if request.method == "POST":
        form = ContaPagarForm(request.POST)
        if form.is_valid():
            conta = form.save(commit=False)
            parcelas = form.cleaned_data.get("parcelas") or 1

            if not conta.recorrente and conta.forma_pagamento in ("boleto", "cartao") and parcelas > 1:
                conta.total_parcelas = parcelas
                conta.parcela_atual = 1
            else:
                conta.total_parcelas = 1
                conta.parcela_atual = 1
            conta.save()

            messages.success(request, "Conta a pagar cadastrada com sucesso!")
            return _redirect_financeiro(request)
    else:
        form = ContaPagarForm()
    return render(request, "core/conta_pagar_form.html", {
        "form": form, "mes": request.GET.get("mes"), "ano": request.GET.get("ano"),
    })


@somente_operacao
def conta_pagar_update(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    if request.method == "POST":
        form = ContaPagarForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta a pagar atualizada!")
            return _redirect_financeiro(request)
    else:
        form = ContaPagarForm(instance=conta)
    return render(request, "core/conta_pagar_form.html", {
        "form": form, "object": conta, "mes": request.GET.get("mes"), "ano": request.GET.get("ano"),
    })


@somente_operacao
def conta_pagar_delete(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    if request.method == "POST":
        descricao = conta.descricao
        if conta.recorrente or conta.total_parcelas > 1:
            raiz = conta.gerada_de or conta
            serie = ContaPagar.objects.filter(Q(pk=raiz.pk) | Q(gerada_de=raiz))
            qtd = serie.count()
            serie.delete()
            messages.success(request, f"\"{descricao}\" excluída — {qtd} ocorrência(s) removida(s) (a série inteira, não só esse mês).")
        else:
            conta.delete()
            messages.success(request, f"Conta \"{descricao}\" excluída.")
        return _redirect_financeiro(request)
    return render(request, "core/conta_pagar_confirm_delete.html", {
        "conta": conta, "mes": request.GET.get("mes"), "ano": request.GET.get("ano"),
    })


@somente_operacao
def conta_pagar_marcar_pago(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    conta.status = "pago"
    conta.save()
    messages.success(request, f"Conta \"{conta.descricao}\" marcada como paga.")
    return _redirect_financeiro(request)


@somente_operacao
def conta_pagar_desmarcar_pago(request, pk):
    conta = get_object_or_404(ContaPagar, pk=pk)
    conta.status = "pendente"
    conta.save()
    messages.success(request, f"Pagamento de \"{conta.descricao}\" desfeito — voltou para Pendente.")
    return _redirect_financeiro(request)


@somente_operacao
def financeiro_export_excel(request):
    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "A Receber"
    ws1.append(["Cliente", "Plano", "Valor", "Pago este mês?"])
    for c in Cliente.objects.exclude(status="inativo").select_related("plano"):
        ws1.append([c.nome, str(c.plano) if c.plano else "", float(c.valor_mensal()), "Sim" if c.pago_mes_atual() else "Não"])

    ws2 = wb.create_sheet("Contas a Pagar")
    ws2.append(["Descrição", "Vencimento", "Valor", "Status"])
    for c in ContaPagar.objects.all():
        ws2.append([c.descricao, c.vencimento.strftime("%d/%m/%Y"), float(c.valor), c.get_status_display()])

    ws3 = wb.create_sheet("Inadimplentes")
    ws3.append(["Cliente", "Telefone", "Valor em atraso"])
    for c in Cliente.objects.filter(status="inadimplente"):
        ws3.append([c.nome, c.telefone, float(c.valor_mensal())])

    for ws in (ws1, ws2, ws3):
        for i in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(i)].width = 22

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="financeiro.xlsx"'
    wb.save(response)
    return response


@somente_operacao
def financeiro_export_pdf(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="financeiro.pdf"'
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph("Relatório Financeiro - CTO Manager Pro", estilos["Title"]), Spacer(1, 12)]

    elementos.append(Paragraph("A Receber", estilos["Heading2"]))
    dados1 = [["Cliente", "Plano", "Valor", "Pago este mês?"]]
    for c in Cliente.objects.exclude(status="inativo").select_related("plano"):
        dados1.append([c.nome, str(c.plano) if c.plano else "-", f"R$ {c.valor_mensal():.2f}", "Sim" if c.pago_mes_atual() else "Não"])
    t1 = Table(dados1, repeatRows=1)
    t1.setStyle(_estilo_tabela_pdf())
    elementos += [t1, Spacer(1, 16)]

    elementos.append(Paragraph("Contas a Pagar", estilos["Heading2"]))
    dados2 = [["Descrição", "Vencimento", "Valor", "Status"]]
    for c in ContaPagar.objects.all():
        dados2.append([c.descricao, c.vencimento.strftime("%d/%m/%Y"), f"R$ {c.valor:.2f}", c.get_status_display()])
    t2 = Table(dados2, repeatRows=1)
    t2.setStyle(_estilo_tabela_pdf())
    elementos += [t2, Spacer(1, 16)]

    elementos.append(Paragraph("Inadimplentes", estilos["Heading2"]))
    dados3 = [["Cliente", "Telefone", "Valor em atraso"]]
    for c in Cliente.objects.filter(status="inadimplente"):
        dados3.append([c.nome, c.telefone, f"R$ {c.valor_mensal():.2f}"])
    t3 = Table(dados3, repeatRows=1)
    t3.setStyle(_estilo_tabela_pdf())
    elementos.append(t3)

    doc.build(elementos)
    return response


# ---------------------------------------------------------------------------
# RELATÓRIOS (somente admin)
# ---------------------------------------------------------------------------

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def relatorio_tecnicos(request):
    hoje = timezone.now()
    ano = int(request.GET.get("ano", hoje.year))
    mes = int(request.GET.get("mes", hoje.month))

    tecnicos = User.objects.filter(role="tecnico")
    dados = []
    for t in tecnicos:
        chamados_tecnico = Chamado.objects.filter(tecnico=t)
        chamados_mes = chamados_tecnico.filter(criado_em__year=ano, criado_em__month=mes)
        dados.append({
            "tecnico": t,
            "concluidos_mes": chamados_mes.filter(status="concluido").count(),
            "concluidos_total": chamados_tecnico.filter(status="concluido").count(),
            "em_andamento": chamados_tecnico.filter(status="andamento").count(),
            "cancelados": chamados_tecnico.filter(status="cancelado").count(),
        })

    meses = [(i, MESES_PT[i]) for i in range(1, 13)]
    anos = list(range(hoje.year - 2, hoje.year + 1))

    context = {
        "dados": dados, "mes_selecionado": mes, "ano_selecionado": ano,
        "meses": meses, "anos": anos, "nome_mes": MESES_PT[mes],
    }
    return render(request, "core/relatorio_tecnicos.html", context)


# ---------------------------------------------------------------------------
# EXPORTAÇÃO: EXCEL E PDF (admin + operador)
# ---------------------------------------------------------------------------

def _estilo_tabela_pdf():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ])


@somente_operacao
def cliente_export_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clientes"
    cabecalho = ["Nome", "CPF/CNPJ", "Telefone", "Plano", "CTO", "Porta", "Status", "Mensalidade", "Bairro", "Cidade"]
    ws.append(cabecalho)
    for c in Cliente.objects.select_related("plano", "cto").all():
        ws.append([
            c.nome, c.cpf_cnpj, c.telefone,
            str(c.plano) if c.plano else "", str(c.cto) if c.cto else "", c.porta,
            c.get_status_display(), float(c.valor_mensal()), c.bairro, c.cidade,
        ])
    for i in range(1, len(cabecalho) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="clientes.xlsx"'
    wb.save(response)
    return response


@somente_operacao
def cliente_export_pdf(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="clientes.pdf"'
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph("Relatório de Clientes - CTO Manager Pro", estilos["Title"]), Spacer(1, 12)]

    dados = [["Nome", "Telefone", "Plano", "CTO/Porta", "Status", "Mensalidade"]]
    for c in Cliente.objects.select_related("plano", "cto").all():
        dados.append([
            c.nome, c.telefone, str(c.plano) if c.plano else "-",
            f"{c.cto or '-'} / {c.porta or '-'}", c.get_status_display(), f"R$ {c.valor_mensal():.2f}",
        ])
    tabela = Table(dados, repeatRows=1)
    tabela.setStyle(_estilo_tabela_pdf())
    elementos.append(tabela)
    doc.build(elementos)
    return response


@somente_operacao
def cto_export_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CTOs"
    cabecalho = ["Código", "Bairro", "Endereço", "Capacidade", "Portas Ocupadas", "Portas Livres", "% Ocupação"]
    ws.append(cabecalho)
    for cto in CTO.objects.all():
        ws.append([
            cto.codigo, cto.bairro, cto.endereco, cto.capacidade,
            cto.portas_ocupadas(), cto.portas_livres(), cto.percentual_ocupacao(),
        ])
    for i in range(1, len(cabecalho) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 20

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="ctos.xlsx"'
    wb.save(response)
    return response


@somente_operacao
def cto_export_pdf(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="ctos.pdf"'
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph("Relatório de CTOs - CTO Manager Pro", estilos["Title"]), Spacer(1, 12)]

    dados = [["Código", "Bairro", "Capacidade", "Ocupadas", "Livres", "% Ocupação"]]
    for cto in CTO.objects.all():
        dados.append([
            cto.codigo, cto.bairro, cto.capacidade,
            cto.portas_ocupadas(), cto.portas_livres(), f"{cto.percentual_ocupacao()}%",
        ])
    tabela = Table(dados, repeatRows=1)
    tabela.setStyle(_estilo_tabela_pdf())
    elementos.append(tabela)
    doc.build(elementos)
    return response


# ---------------------------------------------------------------------------
# USUÁRIOS (somente admin) — criar funcionários e definir o perfil de cada um
# ---------------------------------------------------------------------------

class UsuarioListView(SomenteAdminMixin, ListView):
    model = User
    template_name = "core/usuario_list.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        return User.objects.all().order_by("first_name", "username")


class UsuarioCreateView(SomenteAdminMixin, CreateView):
    model = User
    form_class = UsuarioCreateForm
    template_name = "core/usuario_form.html"
    success_url = reverse_lazy("usuario_list")

    def form_valid(self, form):
        messages.success(self.request, "Usuário cadastrado com sucesso!")
        return super().form_valid(form)


class UsuarioUpdateView(SomenteAdminMixin, UpdateView):
    model = User
    form_class = UsuarioUpdateForm
    template_name = "core/usuario_form.html"
    success_url = reverse_lazy("usuario_list")

    def form_valid(self, form):
        messages.success(self.request, "Usuário atualizado com sucesso!")
        return super().form_valid(form)


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def usuario_delete(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    admins_ativos = User.objects.filter(role="admin", is_active=True).count()
    if usuario.role == "admin" and admins_ativos <= 1:
        messages.error(request, "Não é possível excluir o único administrador ativo do sistema.")
        return redirect("usuario_list")

    if request.method == "POST":
        nome = usuario.get_full_name() or usuario.username
        usuario.delete()
        messages.success(request, f"Usuário \"{nome}\" excluído do sistema.")
        return redirect("usuario_list")
    return render(request, "core/usuario_confirm_delete.html", {"usuario": usuario})


# ---------------------------------------------------------------------------
# GRUPOS E PERMISSÕES (somente admin)
# ---------------------------------------------------------------------------

MODELOS_PERMISSAO = ["cliente", "cto", "chamado", "plano", "contapagar", "user"]
ACOES_PERMISSAO = ["view", "add", "change", "delete"]


def _matriz_permissoes(grupo):
    ativas = set(grupo.permissions.filter(content_type__model__in=MODELOS_PERMISSAO).values_list("codename", flat=True))
    linhas = []
    for modelo in MODELOS_PERMISSAO:
        celulas = []
        for acao in ACOES_PERMISSAO:
            codename = f"{acao}_{modelo}"
            perm = Permission.objects.filter(codename=codename, content_type__model=modelo).first()
            celulas.append({
                "acao_label": ACAO_LABELS[acao],
                "perm_id": perm.id if perm else None,
                "ativo": codename in ativas,
            })
        linhas.append({"modelo_label": MODELO_LABELS.get(modelo, modelo.capitalize()), "celulas": celulas})
    return linhas


@user_passes_test(lambda u: u.is_authenticated and u.role == "admin")
def grupos_permissoes(request):
    if request.method == "POST":
        grupo_id = request.POST.get("grupo_id")
        grupo = get_object_or_404(Group, pk=grupo_id)
        ids_selecionados = request.POST.getlist("permissoes")
        grupo.permissions.set(ids_selecionados)
        messages.success(request, f'Permissões do grupo "{grupo.name}" atualizadas!')
        return redirect("grupos_permissoes")

    grupos = Group.objects.all().order_by("name")
    dados_grupos = [{"grupo": g, "linhas": _matriz_permissoes(g)} for g in grupos]
    return render(request, "core/grupos_permissoes.html", {"dados_grupos": dados_grupos})
