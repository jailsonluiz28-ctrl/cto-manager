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


def rotulo_permissao(permissao):
    """Traduz o nome técnico da permissão (ex: add_cliente) para algo legível (ex: Criar Clientes)."""
    partes = permissao.codename.split("_", 1)
    if len(partes) != 2:
        return permissao.codename
    acao, modelo = partes
    return f"{ACAO_LABELS.get(acao, acao.capitalize())} {MODELO_LABELS.get(modelo, modelo.capitalize())}"
