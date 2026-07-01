from django import forms
from .models import Cliente
from ctos.models import CTO
from planos.models import PlanoInternet


class ClienteForm(forms.ModelForm):

    class Meta:

        model = Cliente

        fields = [

            'nome',
            'tipo_pessoa',
            'cpf_cnpj',
            'telefone',
            'possui_whatsapp',
            'data_nascimento',

            'cep',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'estado',

            'login_pppoe',
            'senha_pppoe',

            'plano',
            'valor_mensalidade',
            'dia_vencimento',

            'data_ativacao',
            'status',

            'cto',
            'porta',

            'equipamento_propriedade',
            'tipo_equipamento',

            'observacao',

        ]

        widgets = {

            'nome': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'tipo_pessoa': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'cpf_cnpj': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'telefone': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'possui_whatsapp': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),

            'data_nascimento': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date'
                }
            ),

            'cep': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'logradouro': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'numero': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'complemento': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'bairro': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'cidade': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'estado': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'login_pppoe': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'senha_pppoe': forms.PasswordInput(
                attrs={'class': 'form-control'}
            ),

            'plano': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'valor_mensalidade': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'readonly': 'readonly'
                }
            ),

            'dia_vencimento': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'data_ativacao': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date'
                }
            ),

            'status': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),

            'cto': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'porta': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'equipamento_propriedade': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'tipo_equipamento': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'observacao': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Campo somente leitura
        self.fields['valor_mensalidade'].widget.attrs['readonly'] = True

        self.fields['cto'].queryset = CTO.objects.all()

        self.fields['plano'].queryset = PlanoInternet.objects.filter(
            ativo=True
        ).order_by('valor')

        self.fields['porta'].choices = [
            ('', 'Selecione uma porta')
        ]

        cto = None

        if self.instance and self.instance.pk:

            cto = self.instance.cto

        elif self.data.get('cto'):

            try:

                cto = CTO.objects.get(
                    id=self.data.get('cto')
                )

            except CTO.DoesNotExist:

                pass

        if cto:

            portas_ocupadas = list(

                Cliente.objects.filter(
                    cto=cto
                ).exclude(
                    pk=self.instance.pk
                ).values_list(
                    'porta',
                    flat=True
                )

            )

            portas = []

            for numero in range(
                1,
                cto.portas_total + 1
            ):

                if (
                    numero not in portas_ocupadas
                    or (
                        self.instance.pk
                        and numero == self.instance.porta
                    )
                ):

                    texto = f'Porta {numero}'

                    if (
                        self.instance.pk
                        and numero == self.instance.porta
                    ):

                        texto += ' (porta atual)'

                    portas.append(
                        (numero, texto)
                    )

            self.fields['porta'].choices = portas

            if self.instance.pk:

                self.initial['porta'] = (
                    self.instance.porta
                )

    def clean_valor_mensalidade(self):

        valor = self.cleaned_data.get("valor_mensalidade")

        plano = self.cleaned_data.get("plano")

        if plano:

            return plano.valor

        return valor