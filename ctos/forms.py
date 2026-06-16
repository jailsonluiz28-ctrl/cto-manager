from django import forms
from .models import CTO


class CTOForm(forms.ModelForm):

    class Meta:
        model = CTO

        fields = [
            'nome',
            'tipo',
            'rua',
            'ativa',
        ]