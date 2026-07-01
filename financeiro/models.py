from django.db import models

from clientes.models import Cliente


class Mensalidade(models.Model):

    STATUS = [

        ("ABERTO", "Em Aberto"),

        ("PAGO", "Pago"),

        ("ATRASADO", "Atrasado"),

        ("CANCELADO", "Cancelado"),

    ]

    cliente = models.ForeignKey(

        Cliente,

        on_delete=models.CASCADE,

        related_name="mensalidades"

    )

    competencia = models.DateField()

    vencimento = models.DateField()

    valor = models.DecimalField(

        max_digits=10,

        decimal_places=2

    )

    status = models.CharField(

        max_length=20,

        choices=STATUS,

        default="ABERTO"

    )

    data_pagamento = models.DateField(

        blank=True,

        null=True

    )

    forma_pagamento = models.CharField(

        max_length=30,

        blank=True

    )

    observacao = models.TextField(

        blank=True

    )

    criado_em = models.DateTimeField(

        auto_now_add=True

    )

    class Meta:

        ordering = [

            "-vencimento"

        ]

    def __str__(self):

        return f"{self.cliente.nome} - {self.competencia}"