from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from ctos.models import CTO
from planos.models import PlanoInternet


class Cliente(models.Model):

    TIPO_PESSOA = [
        ('CPF', 'CPF'),
        ('CNPJ', 'CNPJ'),
    ]

    PROPRIEDADE_EQUIPAMENTO = [
        ('EMPRESA', 'Empresa'),
        ('CLIENTE', 'Cliente'),
    ]

    TIPO_EQUIPAMENTO = [
        ('ONT', 'ONT'),
        ('ROTEADOR', 'Roteador'),
        ('ONU', 'ONU'),
        ('ONU+ROTEADOR', 'ONU + Roteador'),
    ]

    DIA_VENCIMENTO = [
        (5, "05"),
        (10, "10"),
        (15, "15"),
        (20, "20"),
    ]

    STATUS_CLIENTE = [
        ("ATIVO", "Ativo em Dia"),
        ("SUSPENSO", "Suspenso por Falta de Pagamento"),
    ]

    nome = models.CharField(max_length=100)

    tipo_pessoa = models.CharField(
        max_length=10,
        choices=TIPO_PESSOA,
        default='CPF'
    )

    cpf_cnpj = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    possui_whatsapp = models.BooleanField(
        default=True
    )

    data_nascimento = models.DateField(
        blank=True,
        null=True
    )

    cep = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    logradouro = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    numero = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    complemento = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    bairro = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    cidade = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    estado = models.CharField(
        max_length=2,
        blank=True,
        null=True
    )

    login_pppoe = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    senha_pppoe = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    plano = models.ForeignKey(
        PlanoInternet,
        on_delete=models.PROTECT,
        verbose_name="Plano",
        blank=True,
        null=True
    )

    valor_mensalidade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor da Mensalidade",
        blank=True,
        null=True
    )

    data_ativacao = models.DateField(
        verbose_name="Data da Ativação",
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CLIENTE,
        default="ATIVO",
        verbose_name="Situação"
    )

    dia_vencimento = models.IntegerField(
        choices=DIA_VENCIMENTO,
        blank=True,
        null=True,
        verbose_name="Dia do Vencimento"
    )

    equipamento_propriedade = models.CharField(
        max_length=20,
        choices=PROPRIEDADE_EQUIPAMENTO,
        blank=True,
        null=True
    )

    tipo_equipamento = models.CharField(
        max_length=30,
        choices=TIPO_EQUIPAMENTO,
        blank=True,
        null=True
    )

    observacao = models.TextField(
        blank=True,
        null=True
    )

    cto = models.ForeignKey(
        CTO,
        on_delete=models.CASCADE
    )

    porta = models.IntegerField()

    def clean(self):

        if self.porta > self.cto.portas_total:
            raise ValidationError(
                f"Esta CTO possui apenas {self.cto.portas_total} portas."
            )

        if self.porta < 1:
            raise ValidationError(
                "O número da porta deve ser maior que zero."
            )

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

        cto.save(update_fields=['portas_ocupadas'])


class HistoricoMovimentacao(models.Model):

    data = models.DateTimeField(auto_now_add=True)

    usuario = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    cliente_nome = models.CharField(max_length=100)

    cto_nome = models.CharField(max_length=100)

    porta = models.IntegerField()

    acao = models.CharField(max_length=50)

    observacao = models.TextField(
        blank=True,
        null=True
    )

    class Meta:

        ordering = ['-data']

        verbose_name = "Histórico"

        verbose_name_plural = "Histórico de Movimentações"

    def __str__(self):

        return f"{self.data.strftime('%d/%m/%Y %H:%M')} - {self.acao}"