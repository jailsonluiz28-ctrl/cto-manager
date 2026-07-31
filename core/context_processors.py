def marca_do_sistema(request):
    """Deixa a identidade visual (logo + cor principal) disponível em todo
    template, sem precisar passar isso manualmente em cada view. Se der
    qualquer problema (ex: banco ainda sem migração aplicada), simplesmente
    não mostra marca customizada — nunca quebra a página por causa disso."""
    try:
        from .models import ConfiguracaoEmpresa
        return {"marca": ConfiguracaoEmpresa.obter()}
    except Exception:
        return {"marca": None}
