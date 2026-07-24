from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("clientes/", views.ClienteListView.as_view(), name="cliente_list"),
    path("clientes/buscar-json/", views.cliente_busca_json, name="cliente_busca_json"),
    path("clientes/novo/", views.ClienteCreateView.as_view(), name="cliente_create"),
    path("clientes/<int:pk>/editar/", views.ClienteUpdateView.as_view(), name="cliente_update"),
    path("clientes/<int:pk>/excluir/", views.cliente_delete, name="cliente_delete"),
    path("clientes/exportar/excel/", views.cliente_export_excel, name="cliente_export_excel"),
    path("clientes/exportar/pdf/", views.cliente_export_pdf, name="cliente_export_pdf"),

    path("ctos/", views.CTOListView.as_view(), name="cto_list"),
    path("ctos/nova/", views.CTOCreateView.as_view(), name="cto_create"),
    path("ctos/exportar/excel/", views.cto_export_excel, name="cto_export_excel"),
    path("ctos/exportar/pdf/", views.cto_export_pdf, name="cto_export_pdf"),
    path("ctos/<int:pk>/", views.CTODetailView.as_view(), name="cto_detail"),
    path("ctos/<int:pk>/editar/", views.CTOUpdateView.as_view(), name="cto_update"),
    path("ctos/<int:pk>/portas-livres/", views.cto_portas_livres, name="cto_portas_livres"),

    path("planos/", views.PlanoListView.as_view(), name="plano_list"),
    path("planos/novo/", views.PlanoCreateView.as_view(), name="plano_create"),

    path("chamados/", views.ChamadoListView.as_view(), name="chamado_list"),
    path("chamados/finalizados/", views.ChamadoFinalizadosListView.as_view(), name="chamado_finalizados"),
    path("chamados/novo/", views.ChamadoCreateView.as_view(), name="chamado_create"),
    path("chamados/<int:pk>/reatribuir/", views.reatribuir_chamado, name="reatribuir_chamado"),
    path("chamados/<int:pk>/prioridade/", views.alterar_prioridade_chamado, name="alterar_prioridade_chamado"),
    path("chamados/<int:pk>/cancelar/", views.cancelar_chamado, name="cancelar_chamado"),
    path("chamados/<int:pk>/voltar-aberto/", views.voltar_chamado_aberto, name="voltar_chamado_aberto"),
    path("chamados/<int:pk>/finalizar-operador/", views.finalizar_chamado_operador, name="finalizar_chamado_operador"),

    path("meus-chamados/", views.meus_chamados, name="meus_chamados"),
    path("chamados-disponiveis/", views.chamados_disponiveis, name="chamados_disponiveis"),
    path("chamados-disponiveis/<int:pk>/pegar/", views.pegar_chamado, name="pegar_chamado"),
    path("meus-chamados/<int:pk>/avancar/", views.avancar_chamado, name="avancar_chamado"),
    path("meus-chamados/<int:pk>/finalizar/", views.finalizar_chamado, name="finalizar_chamado"),

    path("financeiro/", views.financeiro, name="financeiro"),
    path("financeiro/contas-pagar/nova/", views.conta_pagar_create, name="conta_pagar_create"),

    path("relatorios/tecnicos/", views.relatorio_tecnicos, name="relatorio_tecnicos"),

    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_list"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_create"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_update"),
    path("usuarios/<int:pk>/excluir/", views.usuario_delete, name="usuario_delete"),

    path("grupos-permissoes/", views.grupos_permissoes, name="grupos_permissoes"),
]
