from django.contrib import admin
from .models import Plano, CTO, Cliente, Chamado, ContaPagar, ChamadoAnexo, LogAtividade


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ("nome", "velocidade_mb", "valor_mensal", "ativo")


@admin.register(CTO)
class CTOAdmin(admin.ModelAdmin):
    list_display = ("codigo", "bairro", "capacidade", "portas_ocupadas", "percentual_ocupacao")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "plano", "cto", "status", "telefone")
    list_filter = ("status", "plano", "cto")
    search_fields = ("nome", "cpf_cnpj", "telefone")


class ChamadoAnexoInline(admin.TabularInline):
    model = ChamadoAnexo
    extra = 0


@admin.register(Chamado)
class ChamadoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "tipo", "prioridade", "status", "tecnico")
    list_filter = ("status", "prioridade", "tipo")
    inlines = [ChamadoAnexoInline]


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = ("descricao", "vencimento", "valor", "status")
    list_filter = ("status",)


@admin.register(LogAtividade)
class LogAtividadeAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "usuario", "acao", "detalhes")
    list_filter = ("acao",)
    readonly_fields = ("usuario", "acao", "detalhes", "criado_em")
