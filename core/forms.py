from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Permission
from .models import Cliente, Chamado, ContaPagar, CTO, Plano, DebitoCongelado, Material, JornadaTrabalho, RegistroPonto, AbonoPonto
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
        fields = ["descricao", "valor", "vencimento", "status", "recorrente", "forma_pagamento", "nota_fiscal"]
        labels = {
            "valor": "Valor (de cada parcela, se for parcelado)",
            "vencimento": "Vencimento (1º vencimento, se parcelado)",
            "nota_fiscal": "Nota fiscal / documento (PDF)",
        }
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


class DebitoCongeladoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DebitoCongelado
        fields = ["descricao", "valor", "data_origem", "observacoes"]
        labels = {"data_origem": "De quando é essa dívida (opcional)"}
        widgets = {
            "data_origem": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class NegociarDebitoForm(BootstrapFormMixin, forms.Form):
    valor_parcela = forms.DecimalField(label="Valor de cada parcela", max_digits=10, decimal_places=2)
    parcelas = forms.IntegerField(label="Em quantas vezes", min_value=1, initial=1)
    primeiro_vencimento = forms.DateField(label="1º vencimento", widget=forms.DateInput(attrs={"type": "date"}))
    forma_pagamento = forms.ChoiceField(
        label="Forma de pagamento",
        choices=[("boleto", "Boleto"), ("cartao", "Cartão"), ("avista", "À vista, em uma vez só")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


# ---------------------------------------------------------------------------
# ESTOQUE DE MATERIAL
# ---------------------------------------------------------------------------
class MaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = ["nome", "categoria", "unidade_medida", "estoque_minimo", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class EntradaEstoqueForm(BootstrapFormMixin, forms.Form):
    material = forms.ModelChoiceField(label="Material", queryset=Material.objects.filter(ativo=True))
    quantidade = forms.DecimalField(label="Quantidade comprada", max_digits=10, decimal_places=2, min_value=0.01)
    observacao = forms.CharField(label="Observação (opcional)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class SaidaEstoqueForm(BootstrapFormMixin, forms.Form):
    material = forms.ModelChoiceField(label="Material", queryset=Material.objects.filter(ativo=True))
    quantidade = forms.DecimalField(label="Quantidade retirada", max_digits=10, decimal_places=2, min_value=0.01)
    tecnico = forms.ModelChoiceField(
        label="Liberado para (técnico)", queryset=User.objects.filter(role="tecnico"), required=False,
    )
    observacao = forms.CharField(label="Observação (opcional)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()

    def clean(self):
        cleaned = super().clean()
        material = cleaned.get("material")
        quantidade = cleaned.get("quantidade")
        if material and quantidade and quantidade > material.saldo_atual():
            raise forms.ValidationError(
                f"Estoque insuficiente: só tem {material.saldo_atual()} "
                f"{material.get_unidade_medida_display()} de \"{material.nome}\" disponível."
            )
        return cleaned


# ---------------------------------------------------------------------------
# PONTO
# ---------------------------------------------------------------------------
class JornadaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JornadaTrabalho
        fields = [
            "seg_sex_entrada", "seg_sex_saida_almoco", "seg_sex_volta_almoco", "seg_sex_saida",
            "sabado_ativo", "sabado_entrada", "sabado_saida", "tolerancia_minutos",
        ]
        widgets = {
            "seg_sex_entrada": forms.TimeInput(attrs={"type": "time"}),
            "seg_sex_saida_almoco": forms.TimeInput(attrs={"type": "time"}),
            "seg_sex_volta_almoco": forms.TimeInput(attrs={"type": "time"}),
            "seg_sex_saida": forms.TimeInput(attrs={"type": "time"}),
            "sabado_entrada": forms.TimeInput(attrs={"type": "time"}),
            "sabado_saida": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class PontoLiberarForm(BootstrapFormMixin, forms.Form):
    usuario = forms.ModelChoiceField(
        label="Funcionário", queryset=User.objects.filter(role__in=["tecnico", "operador"], is_active=True)
    )
    observacao = forms.CharField(
        label="Motivo da liberação", widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Ex: dispensado mais cedo porque terminou o serviço, atestado médico, etc.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class LiberacaoExtraForm(BootstrapFormMixin, forms.Form):
    usuario = forms.ModelChoiceField(
        label="Funcionário", queryset=User.objects.filter(role__in=["tecnico", "operador"], is_active=True)
    )
    motivo = forms.CharField(
        label="Motivo (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Ex: emergência na empresa, chamado urgente, etc.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class AbonoForm(BootstrapFormMixin, forms.Form):
    usuario = forms.ModelChoiceField(
        label="Funcionário", queryset=User.objects.filter(role__in=["tecnico", "operador"], is_active=True)
    )
    data = forms.DateField(label="Data a abonar", widget=forms.DateInput(attrs={"type": "date"}))
    motivo = forms.CharField(
        label="Motivo", widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Ex: atestado médico, folga autorizada, etc. Esse dia não conta como falta.",
    )
    anexo = forms.FileField(
        label="Anexar atestado (opcional)", required=False,
        help_text="PDF ou foto do atestado/documento, se tiver.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()
