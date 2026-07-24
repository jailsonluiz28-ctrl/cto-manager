from datetime import timedelta

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

from .models import Plano, CTO, Cliente, Chamado, ContaPagar, ChamadoAnexo, LogAtividade
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
        messages.success(self.request, "Cliente cadastrado com sucesso!")
        return super().form_valid(form)


class ClienteUpdateView(SomenteOperacaoMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "core/cliente_form.html"
    success_url = reverse_lazy("cliente_list")

    def form_valid(self, form):
        messages.success(self.request, "Dados do cliente atualizados!")
        return super().form_valid(form)


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


# ---------------------------------------------------------------------------
# FINANCEIRO (admin + operador)
# ---------------------------------------------------------------------------

@somente_operacao
def financeiro(request):
    clientes = Cliente.objects.exclude(status="inativo").select_related("plano")
    a_receber = sum((c.valor_mensal() for c in clientes), 0)
    inadimplentes = clientes.filter(status="inadimplente")
    total_inadimplencia = sum((c.valor_mensal() for c in inadimplentes), 0)
    contas_pagar = ContaPagar.objects.all()
    total_pagar = sum((c.valor for c in contas_pagar.exclude(status="pago")), 0)

    context = {
        "clientes": clientes,
        "a_receber": a_receber,
        "inadimplentes": inadimplentes,
        "total_inadimplencia": total_inadimplencia,
        "contas_pagar": contas_pagar,
        "total_pagar": total_pagar,
    }
    return render(request, "core/financeiro.html", context)


@somente_operacao
def conta_pagar_create(request):
    if request.method == "POST":
        form = ContaPagarForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("financeiro")
    else:
        form = ContaPagarForm()
    return render(request, "core/conta_pagar_form.html", {"form": form})


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
