from django import forms

from .models import PlanoInternet


class PlanoForm(forms.ModelForm):

    class Meta:

        model = PlanoInternet

        fields = [

            'nome',

            'velocidade',

            'valor',

            'descricao',

            'ativo',

        ]

        labels = {

            'nome': 'Nome do Plano',

            'velocidade': 'Velocidade',

            'valor': 'Valor Mensal',

            'descricao': 'Descrição',

            'ativo': 'Plano Ativo',

        }