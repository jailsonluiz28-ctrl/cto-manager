from django.contrib import admin
from .models import CTO


@admin.register(CTO)
class CTOAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'tipo',
        'rua',
        'portas_total',
        'portas_ocupadas',
        'ativa',
    )

    search_fields = (
        'nome',
        'rua',
    )

    list_filter = (
        'tipo',
        'ativa',
    )

    # Campos exibidos ao cadastrar/editar
    fields = (
        'nome',
        'tipo',
        'rua',
        'ativa',
    )

    # Campos somente leitura na lista de detalhes
    readonly_fields = ()