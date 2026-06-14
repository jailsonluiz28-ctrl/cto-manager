from django import forms
from .models import Cliente
from ctos.models import CTO


class ClienteForm(forms.ModelForm):

    class Meta:
        model = Cliente

        fields = [
            'nome',
            'cto',
            'porta',
        ]

        widgets = {
            'nome': forms.TextInput(
                attrs={
                    'class': 'form-control'
                }
            ),

            'cto': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),

            'porta': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Carrega todas as CTOs cadastradas
        self.fields['cto'].queryset = CTO.objects.all()

        # Inicializa o campo porta
        self.fields['porta'].choices = [
            ('', 'Selecione uma CTO primeiro')
        ]

        cto_id = None

        if self.data.get('cto'):
            try:
                cto_id = int(self.data.get('cto'))
            except (ValueError, TypeError):
                pass

        elif self.instance.pk and self.instance.cto:
            cto_id = self.instance.cto.id

        if cto_id:
            try:
                cto = CTO.objects.get(id=cto_id)

                portas_ocupadas = Cliente.objects.filter(
                    cto=cto
                ).exclude(
                    pk=self.instance.pk
                ).values_list(
                    'porta',
                    flat=True
                )

                portas_disponiveis = []

                for numero in range(1, cto.portas_total + 1):
                    if numero not in portas_ocupadas:
                        portas_disponiveis.append(
                            (numero, f'Porta {numero}')
                        )

                self.fields['porta'].choices = portas_disponiveis

            except CTO.DoesNotExist:
                pass