import unicodedata


def normalizar(texto):
    """Remove acentos e caixa alta/baixa para permitir busca livre de formatação."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


ACAO_LABELS = {"add": "Criar", "change": "Editar", "delete": "Excluir", "view": "Visualizar"}
MODELO_LABELS = {
    "cliente": "Clientes", "cto": "CTOs", "chamado": "Chamados", "plano": "Planos",
    "contapagar": "Contas a Pagar", "logatividade": "Histórico", "user": "Usuários",
    "chamadoanexo": "Anexos de Chamado",
}


def _formatar_numero(valor):
    """Remove casas decimais desnecessárias e usa vírgula (padrão brasileiro).
    Ex: 15.00 -> "15" | 4.5 -> "4,5" | 4.53 -> "4,53" """
    valor = float(valor)
    if valor == int(valor):
        texto = str(int(valor))
    else:
        texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def formatar_quantidade_material(valor, unidade_medida, unidade_display):
    """Formata a quantidade de um material pro estoque, sem vírgula quando é
    número redondo e convertendo metros pra km automaticamente acima de 1000m
    (ex: 4500 metros -> "4,5 km", 980 metros continua "980 metros")."""
    valor = float(valor)
    if unidade_medida == "m" and valor >= 1000:
        return f"{_formatar_numero(valor / 1000)} km"
    if unidade_medida == "m":
        return f"{_formatar_numero(valor)} metros"
    return f"{_formatar_numero(valor)} {unidade_display}"


def rotulo_permissao(permissao):
    """Traduz o nome técnico da permissão (ex: add_cliente) para algo legível (ex: Criar Clientes)."""
    partes = permissao.codename.split("_", 1)
    if len(partes) != 2:
        return permissao.codename
    acao, modelo = partes
    return f"{ACAO_LABELS.get(acao, acao.capitalize())} {MODELO_LABELS.get(modelo, modelo.capitalize())}"


# ---------------------------------------------------------------------------
# PONTO
# ---------------------------------------------------------------------------
ORDEM_PONTO = ["entrada", "saida_almoco", "volta_almoco", "saida"]


def proximo_tipo_ponto(usuario, data=None):
    """Devolve qual é o próximo tipo de batida que essa pessoa precisa fazer hoje
    — olhando o ÚLTIMO registro do dia (não só se cada tipo já existe), pra
    suportar mais de um ciclo de ponto no mesmo dia (ex: chamado de volta numa
    emergência depois de já ter saído). Se já bateu o ciclo inteiro (saída) e
    não tem uma liberação extra pendente, devolve None."""
    from django.utils import timezone
    from .models import RegistroPonto, LiberacaoExtraPonto

    data = data or timezone.localdate()
    ultimo = RegistroPonto.objects.filter(usuario=usuario, data_hora__date=data).order_by("-data_hora").first()
    if not ultimo:
        return "entrada"
    if ultimo.tipo == "entrada" and ultimo.eh_chamada_de_volta:
        # Chamado de volta (emergência) não passa por almoço — é direto Entrada -> Saída
        return "saida"
    idx = ORDEM_PONTO.index(ultimo.tipo)
    if idx < len(ORDEM_PONTO) - 1:
        return ORDEM_PONTO[idx + 1]
    if LiberacaoExtraPonto.objects.filter(usuario=usuario, data=data, usada=False).exists():
        return "entrada"
    return None


def tem_entrada_hoje(usuario, data=None):
    """Verifica se a pessoa já bateu o ponto de entrada hoje — usado pra bloquear
    o técnico de pegar chamados novos se ele esqueceu de bater o ponto."""
    from django.utils import timezone
    from .models import RegistroPonto

    data = data or timezone.localdate()
    return RegistroPonto.objects.filter(usuario=usuario, data_hora__date=data, tipo="entrada").exists()


def esta_em_expediente(usuario, data=None):
    """True se o ÚLTIMO registro de hoje não for uma saída — ou seja, a pessoa
    está "no expediente" (dentro de um ciclo entrada->saída) e pode usar o
    resto do sistema. Cobre naturalmente o caso de mais de um ciclo no mesmo dia
    (liberação extra): depois de bater entrada de novo, volta a ficar True."""
    from django.utils import timezone
    from .models import RegistroPonto

    data = data or timezone.localdate()
    ultimo = RegistroPonto.objects.filter(usuario=usuario, data_hora__date=data).order_by("-data_hora").first()
    if not ultimo:
        return False
    return ultimo.tipo != "saida"


def resumo_ponto_dia(usuario, data):
    """Monta o resumo do dia: quais batidas foram feitas, quantas horas foram
    trabalhadas, quantas eram esperadas e a diferença (hora extra ou falta).
    Suporta mais de um ciclo de ponto no mesmo dia (ex: liberação extra depois
    de já ter saído) — soma as horas de todos os ciclos fechados no dia.
    Se o dia foi abonado pelo Administrador (ex: atestado médico), as horas
    esperadas viram 0 — o funcionário não fica devendo hora nenhuma nesse dia."""
    from .models import RegistroPonto, JornadaTrabalho, AbonoPonto

    todos = list(RegistroPonto.objects.filter(usuario=usuario, data_hora__date=data).order_by("data_hora"))
    registros = {}
    for r in todos:
        registros[r.tipo] = r  # fica com o registro mais recente de cada tipo

    horas_trabalhadas = 0.0
    horas_chamada_de_volta = 0.0
    inicio_turno = None
    turno_eh_chamada = False
    for r in todos:
        if r.tipo in ("entrada", "volta_almoco"):
            inicio_turno = r.data_hora
            if r.tipo == "entrada":
                turno_eh_chamada = r.eh_chamada_de_volta
        elif r.tipo in ("saida_almoco", "saida") and inicio_turno:
            horas = (r.data_hora - inicio_turno).total_seconds() / 3600
            horas_trabalhadas += horas
            if turno_eh_chamada:
                horas_chamada_de_volta += horas
            inicio_turno = None
            turno_eh_chamada = False

    jornada, _ = JornadaTrabalho.objects.get_or_create(usuario=usuario)
    abono = AbonoPonto.objects.filter(usuario=usuario, data=data).first()
    horas_esperadas = 0.0 if abono else jornada.carga_horaria_dia(data)
    return {
        "data": data,
        "registros": registros,
        "todos_registros": todos,
        "horas_trabalhadas": round(horas_trabalhadas, 2),
        "horas_chamada_de_volta": round(horas_chamada_de_volta, 2),
        "horas_esperadas": horas_esperadas,
        "diferenca": round(horas_trabalhadas - horas_esperadas, 2),
        "liberado_mais_cedo": any(r.liberado_mais_cedo for r in todos),
        "abono": abono,
        "completo": (todos and todos[-1].tipo == "saida") or horas_esperadas == 0,
    }
