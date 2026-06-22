from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from ctos.models import CTO


class Cliente(models.Model):
    nome = models.CharField(max_length=100)

    cto = models.ForeignKey(
        CTO,
        on_delete=models.CASCADE
    )

    porta = models.IntegerField()

    def clean(self):
        # Verifica se a porta existe na CTO
        if self.porta > self.cto.portas_total:
            raise ValidationError(
                f"Esta CTO possui apenas {self.cto.portas_total} portas."
            )

        if self.porta < 1:
            raise ValidationError(
                "O número da porta deve ser maior que zero."
            )

        # Verifica se já existe cliente usando essa porta
        cliente_existente = Cliente.objects.filter(
            cto=self.cto,
            porta=self.porta
        ).exclude(pk=self.pk)

        if cliente_existente.exists():
            raise ValidationError(
                f"A porta {self.porta} já está ocupada."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


@receiver(post_save, sender=Cliente)
@receiver(post_delete, sender=Cliente)
def atualizar_ocupacao_cto(sender, instance, **kwargs):

    cto = instance.cto

    quantidade = Cliente.objects.filter(
        cto=cto
    ).count()

    if quantidade != cto.portas_ocupadas:

        cto.portas_ocupadas = quantidade

        cto.save(
            update_fields=['portas_ocupadas']
        )


class HistoricoMovimentacao(models.Model):

    data = models.DateTimeField(
        auto_now_add=True
    )

    usuario = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    cliente_nome = models.CharField(
        max_length=100
    )

    cto_nome = models.CharField(
        max_length=100
    )

    porta = models.IntegerField()

    acao = models.CharField(
        max_length=50
    )

    observacao = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.acao} - {self.cliente_nome}"