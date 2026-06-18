from django import forms
from .models import Cliente
from ctos.models import CTO


class ClienteForm(forms.ModelForm):

    class Meta:
        model = Cliente
        fields = ['nome', 'cto', 'porta']

        widgets = {
            'nome': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'cto': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'porta': forms.Select(
                attrs={'class': 'form-select'}
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['cto'].queryset = CTO.objects.all()

        self.fields['porta'].choices = [
            ('', 'Selecione uma porta')
        ]

        cto = None

        # EDITANDO UM CLIENTE
        if self.instance and self.instance.pk:

            cto = self.instance.cto

        # POST DO FORMULÁRIO
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

            for numero in range(1, cto.portas_total + 1):

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

            # deixa a porta atual selecionada
            if self.instance.pk:
                self.initial['porta'] = self.instance.porta