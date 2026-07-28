from django.contrib import admin
from .models import Plano, CTO, Cliente, Chamado, ContaPagar, ChamadoAnexo, LogAtividade, Pagamento, MovimentacaoReceita, DebitoCongelado, Material, MovimentacaoEstoque, JornadaTrabalho, RegistroPonto, AbonoPonto, LiberacaoExtraPonto


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
    list_display = ("descricao", "vencimento", "valor", "status", "recorrente", "parcela_atual", "total_parcelas")
    list_filter = ("status", "recorrente", "forma_pagamento")


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "mes_referencia", "valor", "data_pagamento", "registrado_por")
    list_filter = ("mes_referencia",)


@admin.register(MovimentacaoReceita)
class MovimentacaoReceitaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "tipo", "valor_anterior", "valor_novo", "criado_em")
    list_filter = ("tipo",)


@admin.register(DebitoCongelado)
class DebitoCongeladoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "data_origem", "negociado", "negociado_em")
    list_filter = ("negociado",)


@admin.register(LogAtividade)
class LogAtividadeAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "usuario", "acao", "detalhes")
    list_filter = ("acao",)
    readonly_fields = ("usuario", "acao", "detalhes", "criado_em")

    def has_add_permission(self, request):
        # O histórico se preenche sozinho (via signals.py) toda vez que algo
        # é criado/editado/excluído no sistema — não faz sentido criar um
        # registro manual aqui, então nem mostramos o botão "Adicionar".
        return False


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("nome", "unidade_medida", "saldo_atual", "ativo")
    list_filter = ("ativo",)


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("material", "tipo", "quantidade", "tecnico", "registrado_por", "criado_em")
    list_filter = ("tipo", "material")


@admin.register(JornadaTrabalho)
class JornadaTrabalhoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "seg_sex_entrada", "seg_sex_saida", "sabado_ativo", "sabado_entrada", "sabado_saida")


@admin.register(RegistroPonto)
class RegistroPontoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "data_hora", "liberado_mais_cedo", "autorizado_por")
    list_filter = ("tipo", "liberado_mais_cedo")


@admin.register(AbonoPonto)
class AbonoPontoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "data", "motivo", "registrado_por")
    list_filter = ("data",)


@admin.register(LiberacaoExtraPonto)
class LiberacaoExtraPontoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "data", "usada", "autorizado_por", "criado_em")
    list_filter = ("usada", "data")
