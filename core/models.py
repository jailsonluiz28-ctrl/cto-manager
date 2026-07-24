from django.conf import settings
from django.db import models


class Plano(models.Model):
    nome = models.CharField(max_length=100)
    velocidade_mb = models.PositiveIntegerField(help_text="Velocidade em Mega, ex: 300")
    valor_mensal = models.DecimalField(max_digits=8, decimal_places=2)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["velocidade_mb"]

    def __str__(self):
        return f"{self.nome} - R$ {self.valor_mensal}"


class CTO(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    bairro = models.CharField(max_length=150)
    endereco = models.CharField(max_length=255, blank=True)
    capacidade = models.PositiveIntegerField(default=16, choices=[(8, "8 portas"), (16, "16 portas")])
    ruas_atendidas = models.TextField(
        "Ruas atendidas", blank=True,
        help_text="Uma rua por linha. Ex: Rua Clara\\nRua Puebla",
    )

    class Meta:
        ordering = ["codigo"]
        verbose_name = "CTO"
        verbose_name_plural = "CTOs"

    def portas_ocupadas(self):
        return self.clientes.exclude(status="inativo").count()

    def portas_livres(self):
        return max(self.capacidade - self.portas_ocupadas(), 0)

    def percentual_ocupacao(self):
        if self.capacidade == 0:
            return 0
        return round((self.portas_ocupadas() / self.capacidade) * 100, 1)

    def esta_lotada(self):
        return self.portas_ocupadas() >= self.capacidade

    def portas_disponiveis(self):
        ocupadas = set(self.clientes.exclude(status="inativo").values_list("porta", flat=True))
        return [str(p).zfill(2) for p in range(1, self.capacidade + 1) if str(p).zfill(2) not in ocupadas]

    def lista_ruas(self):
        return [r.strip() for r in self.ruas_atendidas.splitlines() if r.strip()]

    def __str__(self):
        return self.codigo


class Cliente(models.Model):
    STATUS_CHOICES = [
        ("ativo", "Ativo em Dia"),
        ("inadimplente", "Inadimplente"),
        ("suspenso", "Suspenso"),
        ("inativo", "Inativo"),
    ]
    TIPO_PESSOA_CHOICES = [("fisica", "Pessoa Física"), ("juridica", "Pessoa Jurídica")]
    PROPRIEDADE_EQUIP_CHOICES = [("empresa", "Empresa"), ("cliente", "Cliente")]
    TIPO_EQUIPAMENTO_CHOICES = [
        ("onu", "ONU"),
        ("roteador", "Roteador"),
        ("onu_roteador", "ONU + Roteador"),
        ("ont", "ONT"),
    ]

    nome = models.CharField("Nome completo", max_length=150)
    tipo_pessoa = models.CharField(max_length=10, choices=TIPO_PESSOA_CHOICES, default="fisica")
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    possui_whatsapp = models.BooleanField("Possui WhatsApp", default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo")

    cep = models.CharField(max_length=10, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=150, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    complemento = models.CharField(max_length=150, blank=True)

    login_pppoe = models.CharField("Login PPPoE", max_length=100, blank=True)
    senha_pppoe = models.CharField("Senha PPPoE", max_length=100, blank=True)
    plano = models.ForeignKey(Plano, on_delete=models.SET_NULL, null=True, related_name="clientes")
    data_ativacao = models.DateField(null=True, blank=True)
    dia_vencimento = models.PositiveSmallIntegerField(default=10)

    cto = models.ForeignKey(CTO, on_delete=models.SET_NULL, null=True, blank=True, related_name="clientes")
    porta = models.CharField(max_length=10, blank=True)

    propriedade_equipamento = models.CharField(max_length=20, choices=PROPRIEDADE_EQUIP_CHOICES, default="empresa")
    tipo_equipamento = models.CharField(max_length=20, choices=TIPO_EQUIPAMENTO_CHOICES, default="onu_roteador")

    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def valor_mensal(self):
        return self.plano.valor_mensal if self.plano else 0

    def endereco_completo(self):
        linha1 = ", ".join(p for p in [self.logradouro, self.numero] if p)
        linha2 = " - ".join(p for p in [self.bairro, self.cidade, self.estado] if p)
        return " · ".join(p for p in [linha1, linha2] if p) or "Endereço não informado"

    def __str__(self):
        return self.nome


class Chamado(models.Model):
    TIPO_CHOICES = [
        ("sem_sinal", "Sem sinal"),
        ("lentidao", "Lentidão"),
        ("instalacao", "Instalação nova"),
        ("equipamento", "Troca de equipamento"),
        ("financeiro", "Financeiro"),
        ("outro", "Outro"),
    ]
    PRIORIDADE_CHOICES = [
        ("extrema", "Extrema"),
        ("alta", "Alta"),
        ("media", "Média"),
        ("baixa", "Baixa"),
    ]
    STATUS_CHOICES = [
        ("aberto", "Aberto"),
        ("andamento", "Em andamento"),
        ("concluido", "Concluído"),
        ("cancelado", "Cancelado"),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="chamados")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="outro")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default="media")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberto")
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="chamados"
    )
    descricao = models.TextField("Observação (do operador)", blank=True)
    observacao_fechamento = models.TextField("Observação de fechamento (do técnico)", blank=True)
    pego_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    eh_retorno = models.BooleanField(default=False)
    tecnico_ultimo_atendimento = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chamados_retorno_anteriores",
    )
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chamados_finalizados_por_mim",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def duracao_atendimento(self):
        if self.pego_em and self.concluido_em:
            return self.concluido_em - self.pego_em
        return None

    def duracao_formatada(self):
        delta = self.duracao_atendimento()
        if not delta:
            return "—"
        total_min = int(delta.total_seconds() // 60)
        horas, minutos = divmod(total_min, 60)
        if horas:
            return f"{horas}h {minutos}min"
        return f"{minutos}min"

    def __str__(self):
        return f"#{self.id} - {self.cliente.nome}"


class ChamadoAnexo(models.Model):
    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name="anexos")
    imagem = models.ImageField(upload_to="chamados/%Y/%m/")
    enviado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo do chamado #{self.chamado_id}"


class ContaPagar(models.Model):
    STATUS_CHOICES = [("pendente", "Pendente"), ("agendado", "Agendado"), ("pago", "Pago")]
    descricao = models.CharField(max_length=200)
    vencimento = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")

    class Meta:
        ordering = ["vencimento"]
        verbose_name = "Conta a pagar"
        verbose_name_plural = "Contas a pagar"

    def __str__(self):
        return self.descricao


class LogAtividade(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    acao = models.CharField(max_length=255)
    detalhes = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Log de atividade"
        verbose_name_plural = "Histórico de movimentações"

    def __str__(self):
        return f"{self.acao} - {self.usuario}"
