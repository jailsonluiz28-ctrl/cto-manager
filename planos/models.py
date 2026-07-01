from django.db import models


class PlanoInternet(models.Model):

    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome do Plano"
    )

    velocidade = models.CharField(
        max_length=50,
        verbose_name="Velocidade"
    )

    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor Mensal"
    )

    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição"
    )

    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    class Meta:

        verbose_name = "Plano de Internet"

        verbose_name_plural = "Planos de Internet"

        ordering = [
            "valor",
            "nome"
        ]

    def __str__(self):

        return f"{self.nome} - R$ {self.valor}"