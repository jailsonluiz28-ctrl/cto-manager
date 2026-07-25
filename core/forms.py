from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Permission
from .models import Cliente, Chamado, ContaPagar, CTO, Plano
from .utils import rotulo_permissao
from accounts.models import User


class BootstrapFormMixin:
    def aplicar_estilo(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs["class"] = "form-select"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "form-control"
                field.widget.attrs["rows"] = 3
            else:
                field.widget.attrs["class"] = "form-control"


class ClienteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "nome", "tipo_pessoa", "cpf_cnpj", "data_nascimento", "telefone", "possui_whatsapp", "status",
            "cep", "logradouro", "numero", "bairro", "cidade", "estado", "complemento",
            "login_pppoe", "senha_pppoe", "plano", "data_ativacao", "dia_vencimento",
            "cto", "porta",
            "propriedade_equipamento", "tipo_equipamento",
            "observacoes",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "data_ativacao": forms.DateInput(attrs={"type": "date"}),
            "senha_pppoe": forms.PasswordInput(render_value=True),
            "observacoes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()
        # Vencimento só nos dias fixos usados pela operação
        self.fields["dia_vencimento"].widget = forms.Select(
            choices=[(5, "5"), (10, "10"), (15, "15"), (20, "20")], attrs={"class": "form-select"}
        )
        # A porta é preenchida dinamicamente via JS de acordo com a CTO escolhida
        # (ver script no template cliente_form.html). Aqui só garantimos que a porta
        # atual do cliente (se estiver editando) sempre apareça como opção válida.
        porta_atual = self.instance.porta if self.instance and self.instance.pk else ""
        opcoes = [("", "Selecione a CTO primeiro")]
        if porta_atual:
            opcoes.append((porta_atual, f"Porta {porta_atual} (atual)"))
        self.fields["porta"] = forms.ChoiceField(
            choices=opcoes, required=False, widget=forms.Select(attrs={"class": "form-select", "id": "id_porta"})
        )


class CTOForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CTO
        fields = ["codigo", "bairro", "endereco", "capacidade", "ruas_atendidas"]
        widgets = {
            "ruas_atendidas": forms.Textarea(attrs={
                "rows": 4, "placeholder": "Uma rua por linha, ex:\nRua Clara\nRua Puebla\nRua das Acácias"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class PlanoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Plano
        fields = ["nome", "velocidade_mb", "valor_mensal", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class ChamadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Chamado
        fields = ["cliente", "tipo", "prioridade", "descricao"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class ContaPagarForm(BootstrapFormMixin, forms.ModelForm):
    parcelas = forms.IntegerField(
        label="Número de parcelas", min_value=1, initial=1, required=False,
        help_text="Só usado se a forma de pagamento for Boleto ou Cartão parcelado.",
    )

    class Meta:
        model = ContaPagar
        fields = ["descricao", "valor", "vencimento", "status", "recorrente", "forma_pagamento"]
        labels = {"valor": "Valor (de cada parcela, se for parcelado)", "vencimento": "Vencimento (1º vencimento, se parcelado)"}
        widgets = {"vencimento": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class UsuarioCreateForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "telefone"]
        labels = {"role": "Perfil"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class PermissaoMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return rotulo_permissao(obj)


MODELOS_GERENCIAVEIS = ["cliente", "cto", "chamado", "plano", "contapagar"]


class UsuarioUpdateForm(BootstrapFormMixin, forms.ModelForm):
    nova_senha = forms.CharField(
        label="Nova senha", required=False, widget=forms.PasswordInput,
        help_text="Deixe em branco para manter a senha atual.",
    )
    permissoes_extra = PermissaoMultipleChoiceField(
        queryset=Permission.objects.filter(content_type__model__in=MODELOS_GERENCIAVEIS).select_related("content_type"),
        required=False, widget=forms.CheckboxSelectMultiple,
        label="Permissões individuais extras (além do que o perfil já libera)",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "telefone", "is_active"]
        labels = {"role": "Perfil", "is_active": "Usuário ativo (pode entrar no sistema)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()
        if self.instance.pk:
            self.fields["permissoes_extra"].initial = self.instance.user_permissions.all()

    def save(self, commit=True):
        usuario = super().save(commit=False)
        nova_senha = self.cleaned_data.get("nova_senha")
        if nova_senha:
            usuario.set_password(nova_senha)
        if commit:
            usuario.save()
            usuario.user_permissions.set(self.cleaned_data.get("permissoes_extra", []))
        return usuario
