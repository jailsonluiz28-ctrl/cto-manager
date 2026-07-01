from django import forms

from .models import Mensalidade


class MensalidadeForm(forms.ModelForm):

    class Meta:

        model = Mensalidade

        fields = [

            "cliente",

            "competencia",

            "vencimento",

            "valor",

            "status",

            "data_pagamento",

            "forma_pagamento",

            "observacao",

        ]

        widgets = {

            "competencia": forms.DateInput(
                attrs={"type": "date"}
            ),

            "vencimento": forms.DateInput(
                attrs={"type": "date"}
            ),

            "data_pagamento": forms.DateInput(
                attrs={"type": "date"}
            ),

            "observacao": forms.Textarea(
                attrs={"rows":3}
            ),

        }