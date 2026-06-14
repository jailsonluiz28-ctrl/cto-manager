from django.db import models


class CTO(models.Model):
    nome = models.CharField(max_length=100)

    tipo = models.CharField(
        max_length=10,
        choices=[
            ('1x8', 'CTO 1x8'),
            ('1x16', 'CTO 1x16'),
        ]
    )

    rua = models.CharField(max_length=200)

    portas_total = models.IntegerField(default=8)

    portas_ocupadas = models.IntegerField(default=0)

    ativa = models.BooleanField(default=True)

    def save(self, *args, **kwargs):

        # Define automaticamente a quantidade de portas
        if self.tipo == '1x8':
            self.portas_total = 8

        elif self.tipo == '1x16':
            self.portas_total = 16

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome