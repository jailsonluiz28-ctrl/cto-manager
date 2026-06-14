from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'cto',
        'porta',
    )

    search_fields = (
        'nome',
    )

    list_filter = (
        'cto',
    )

    fields = (
        'nome',
        'cto',
        'porta',
    )

    ordering = (
        'nome',
    )

    list_per_page = 20