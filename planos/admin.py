from django.contrib import admin
from .models import PlanoInternet


@admin.register(PlanoInternet)
class PlanoInternetAdmin(admin.ModelAdmin):

    list_display = (
        'nome',
        'velocidade',
        'valor',
        'ativo',
    )

    list_display_links = (
        'nome',
    )

    search_fields = (
        'nome',
        'velocidade',
        'descricao',
    )

    list_filter = (
        'ativo',
    )

    ordering = (
        'valor',
        'nome',
    )

    list_editable = (
        'ativo',
    )

    fieldsets = (

        (
            'Informações do Plano',
            {
                'fields': (
                    'nome',
                    'velocidade',
                    'valor',
                )
            }
        ),

        (
            'Configurações',
            {
                'fields': (
                    'ativo',
                    'descricao',
                )
            }
        ),
    )