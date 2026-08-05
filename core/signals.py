"""Auditoria do sistema — registra em LogAtividade quem fez o quê, e a partir
da v85 também O QUE mudou, campo a campo, nos cadastros principais."""

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import User
from .middleware import get_current_user
from .models import (
    Cliente, CTO, Chamado, Plano, LogAtividade,
    ContaPagar, DebitoCongelado, Material, ConfiguracaoEmpresa, Promocao,
    JornadaTrabalho, MovimentacaoEstoque, Pagamento, AbonoPonto, SolicitacaoLiberacaoConfianca,
    LicencaSistema, ConfiguracaoMikrotik,
)

LIMITE_TENTATIVAS = 5
MINUTOS_BLOQUEIO = 15


def _registrar(acao, detalhes=""):
    usuario = get_current_user()
    if not getattr(usuario, "is_authenticated", False):
        usuario = None
    LogAtividade.objects.create(usuario=usuario, acao=acao, detalhes=detalhes)


# ---------------------------------------------------------------------------
# Auditoria campo a campo: guarda o valor de "antes" no pre_save, e no
# post_save compara com o valor novo pra montar uma frase tipo
# "Telefone: (81) 3333-0000 → (81) 99999-8888; Status: Ativo em Dia → Suspenso".
# ---------------------------------------------------------------------------

CAMPOS_SENSIVEIS = {"senha_pppoe", "portal_senha_hash", "password", "senha"}


def _valor_legivel(obj, campo):
    if obj is None:
        return None
    display_fn = getattr(obj, f"get_{campo}_display", None)
    if display_fn:
        try:
            return display_fn()
        except Exception:
            pass
    valor = getattr(obj, campo, None)
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    return str(valor)


def _montar_diff(antigo, novo, campos):
    """campos: lista de (nome_do_campo, rótulo pra mostrar no log)."""
    if antigo is None:
        return ""
    partes = []
    for campo, rotulo in campos:
        if campo in CAMPOS_SENSIVEIS:
            if getattr(antigo, campo, None) != getattr(novo, campo, None):
                partes.append(f"{rotulo}: alterada")
            continue
        v_antigo = _valor_legivel(antigo, campo)
        v_novo = _valor_legivel(novo, campo)
        if v_antigo != v_novo:
            partes.append(f"{rotulo}: {v_antigo} → {v_novo}")
    return "; ".join(partes)


def _carregar_antigo(model, pk):
    if not pk:
        return None
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None


def _nome_padrao(instance):
    return str(instance)


def registrar_auditoria_completa(model, campos, rotulo, nome_fn=_nome_padrao):
    """Liga pre_save/post_save/post_delete pra um model, gerando log de
    criação/edição (com diff campo a campo)/exclusão automaticamente."""

    def pre_save_handler(sender, instance, **kwargs):
        instance._antigo = _carregar_antigo(model, instance.pk)

    def post_save_handler(sender, instance, created, **kwargs):
        nome = nome_fn(instance)
        if created:
            _registrar(f"{rotulo} cadastrado(a)", nome)
        else:
            diff = _montar_diff(getattr(instance, "_antigo", None), instance, campos)
            _registrar(f"{rotulo} editado(a)", f"{nome} — {diff}" if diff else nome)

    def post_delete_handler(sender, instance, **kwargs):
        _registrar(f"{rotulo} excluído(a)", nome_fn(instance))

    pre_save.connect(pre_save_handler, sender=model, weak=False)
    post_save.connect(post_save_handler, sender=model, weak=False)
    post_delete.connect(post_delete_handler, sender=model, weak=False)


def registrar_apenas_criacao(model, rotulo, nome_fn=_nome_padrao):
    """Pra registros que praticamente não são editados depois de criados
    (movimentação de estoque, pagamento, abono...) — só loga a criação."""

    def post_save_handler(sender, instance, created, **kwargs):
        if created:
            _registrar(f"{rotulo} registrado(a)", nome_fn(instance))

    def post_delete_handler(sender, instance, **kwargs):
        _registrar(f"{rotulo} excluído(a)", nome_fn(instance))

    post_save.connect(post_save_handler, sender=model, weak=False)
    post_delete.connect(post_delete_handler, sender=model, weak=False)


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    if user.tentativas_login_falhas or user.bloqueado_ate:
        User.objects.filter(pk=user.pk).update(tentativas_login_falhas=0, bloqueado_ate=None)
    LogAtividade.objects.create(usuario=user, acao="Login no sistema", detalhes="")


@receiver(user_login_failed)
def log_login_falho(sender, credentials, request=None, **kwargs):
    """Conta as tentativas erradas e bloqueia a conta temporariamente depois
    de várias seguidas — e sempre deixa registrado na Auditoria, mesmo pra
    usuário que nem existe (pra dar pra perceber tentativa de invasão)."""
    username = (credentials or {}).get("username", "")
    usuario = User.objects.filter(username=username).first()
    if not usuario:
        LogAtividade.objects.create(
            usuario=None, acao="Tentativa de login falhou",
            detalhes=f'Usuário "{username}" não existe no sistema',
        )
        return

    tentativas = usuario.tentativas_login_falhas + 1
    bloqueado_ate = usuario.bloqueado_ate
    aviso_bloqueio = ""
    if tentativas >= LIMITE_TENTATIVAS:
        bloqueado_ate = timezone.now() + timedelta(minutes=MINUTOS_BLOQUEIO)
        aviso_bloqueio = f" — CONTA BLOQUEADA por {MINUTOS_BLOQUEIO} minutos"
    User.objects.filter(pk=usuario.pk).update(tentativas_login_falhas=tentativas, bloqueado_ate=bloqueado_ate)
    LogAtividade.objects.create(
        usuario=None, acao="Tentativa de login falhou",
        detalhes=f"{usuario.username} — tentativa {tentativas}/{LIMITE_TENTATIVAS}{aviso_bloqueio}",
    )


# ---------------- CLIENTE ----------------
registrar_auditoria_completa(
    Cliente,
    [
        ("nome", "Nome"), ("status", "Status"), ("tipo_pessoa", "Tipo de pessoa"),
        ("cpf_cnpj", "CPF/CNPJ"), ("data_nascimento", "Data de nascimento"),
        ("telefone", "Telefone"), ("possui_whatsapp", "Possui WhatsApp"),
        ("cep", "CEP"), ("logradouro", "Endereço"), ("numero", "Número"),
        ("bairro", "Bairro"), ("cidade", "Cidade"), ("estado", "Estado"), ("complemento", "Complemento"),
        ("login_pppoe", "Login PPPoE"), ("senha_pppoe", "Senha PPPoE"),
        ("plano", "Plano"), ("data_ativacao", "Data de ativação"), ("dia_vencimento", "Dia de vencimento"),
        ("cto", "CTO"), ("porta", "Porta"),
        ("propriedade_equipamento", "Propriedade do equipamento"), ("tipo_equipamento", "Tipo de equipamento"),
        ("observacoes", "Observações"),
    ],
    "Cliente", nome_fn=lambda i: i.nome,
)

# ---------------- CTO ----------------
registrar_auditoria_completa(
    CTO,
    [("codigo", "Código"), ("bairro", "Bairro"), ("endereco", "Endereço"),
     ("capacidade", "Capacidade"), ("ruas_atendidas", "Ruas atendidas")],
    "CTO", nome_fn=lambda i: i.codigo,
)

# ---------------- CHAMADO ----------------
registrar_auditoria_completa(
    Chamado,
    [("tipo", "Tipo"), ("prioridade", "Prioridade"), ("status", "Status"), ("tecnico", "Técnico"),
     ("descricao", "Observação"), ("observacao_fechamento", "Observação de fechamento")],
    "Chamado", nome_fn=lambda i: f"#{i.id} - {i.cliente.nome}",
)

# ---------------- PLANO ----------------
registrar_auditoria_completa(
    Plano,
    [("nome", "Nome"), ("velocidade_mb", "Velocidade"), ("valor_mensal", "Valor mensal"), ("ativo", "Ativo")],
    "Plano", nome_fn=lambda i: i.nome,
)

# ---------------- CONTAS A PAGAR ----------------
registrar_auditoria_completa(
    ContaPagar,
    [("descricao", "Descrição"), ("vencimento", "Vencimento"), ("valor", "Valor"), ("status", "Status"),
     ("recorrente", "Fixo mensal"), ("forma_pagamento", "Forma de pagamento"),
     ("parcela_atual", "Parcela atual"), ("total_parcelas", "Total de parcelas")],
    "Conta a pagar", nome_fn=lambda i: i.descricao,
)

# ---------------- DÉBITO CONGELADO ----------------
registrar_auditoria_completa(
    DebitoCongelado,
    [("descricao", "Descrição"), ("valor", "Valor"), ("data_origem", "Data de origem"),
     ("observacoes", "Observações"), ("negociado", "Negociado")],
    "Débito congelado", nome_fn=lambda i: i.descricao,
)

# ---------------- MATERIAL (Estoque) ----------------
registrar_auditoria_completa(
    Material,
    [("nome", "Nome"), ("unidade_medida", "Unidade de medida"),
     ("estoque_minimo", "Estoque mínimo"), ("ativo", "Ativo")],
    "Material", nome_fn=lambda i: i.nome,
)

# ---------------- USUÁRIOS (equipe) ----------------
registrar_auditoria_completa(
    User,
    [("username", "Usuário"), ("first_name", "Nome"), ("last_name", "Sobrenome"),
     ("role", "Perfil"), ("telefone", "Telefone"), ("is_active", "Ativo"), ("password", "Senha")],
    "Usuário", nome_fn=lambda i: i.get_full_name() or i.username,
)

# ---------------- CONFIGURAÇÃO DO PORTAL DO CLIENTE ----------------
registrar_auditoria_completa(
    ConfiguracaoEmpresa,
    [("nome_fantasia", "Nome da empresa"), ("whatsapp_numero", "WhatsApp"),
     ("mensagem_boas_vindas", "Mensagem de boas-vindas"), ("cor_primaria", "Cor principal"), ("logo", "Logo")],
    "Configuração do Portal", nome_fn=lambda i: i.nome_fantasia or "Configuração do Portal",
)

# ---------------- PROMOÇÕES (Portal do Cliente) ----------------
registrar_auditoria_completa(
    Promocao,
    [("titulo", "Título"), ("descricao", "Descrição"), ("ativa", "Ativa")],
    "Promoção", nome_fn=lambda i: i.titulo,
)

# ---------------- LICENÇA DO SISTEMA (aluguel) ----------------
registrar_auditoria_completa(
    LicencaSistema,
    [("nome_contratante", "Contratante"), ("data_vencimento", "Vencimento"),
     ("dias_carencia", "Carência (dias)"), ("bloqueado_manualmente", "Bloqueado manualmente")],
    "Licença do sistema", nome_fn=lambda i: i.nome_contratante or "Licença do Sistema",
)

# ---------------- CONFIGURAÇÃO DO MIKROTIK ----------------
registrar_auditoria_completa(
    ConfiguracaoMikrotik,
    [("ativo", "Ativo"), ("host", "Endereço"), ("porta", "Porta"), ("usuario", "Usuário"), ("senha", "Senha"), ("usar_ssl", "Usa SSL")],
    "Configuração do Mikrotik", nome_fn=lambda i: f"Mikrotik ({i.host})" if i.host else "Configuração do Mikrotik",
)

# ---------------- JORNADA DE TRABALHO (Ponto) ----------------
registrar_auditoria_completa(
    JornadaTrabalho,
    [("seg_sex_entrada", "Entrada seg-sex"), ("seg_sex_saida_almoco", "Saída almoço"),
     ("seg_sex_volta_almoco", "Volta almoço"), ("seg_sex_saida", "Saída seg-sex"),
     ("sabado_ativo", "Trabalha sábado"), ("sabado_entrada", "Entrada sábado"),
     ("sabado_saida", "Saída sábado"), ("tolerancia_minutos", "Tolerância (min)")],
    "Jornada de trabalho", nome_fn=lambda i: str(i.usuario),
)

# ---------------- Registros que só fazem sentido "criados" (raramente editados) ----------------
registrar_apenas_criacao(
    MovimentacaoEstoque, "Movimentação de estoque",
    nome_fn=lambda i: f"{i.get_tipo_display()} - {i.material.nome} ({i.quantidade})",
)
registrar_apenas_criacao(
    Pagamento, "Pagamento",
    nome_fn=lambda i: f"{i.cliente.nome} - R$ {i.valor} ({i.mes_referencia.strftime('%m/%Y')})",
)
registrar_apenas_criacao(
    AbonoPonto, "Abono de ponto",
    nome_fn=lambda i: f"{i.usuario} - {i.data.strftime('%d/%m/%Y')}",
)
registrar_apenas_criacao(
    SolicitacaoLiberacaoConfianca, "Pedido de liberação de confiança",
    nome_fn=lambda i: i.cliente.nome,
)
