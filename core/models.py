from datetime import datetime, time as time_cls

from django.conf import settings
from django.db import models
from django.utils import timezone


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
        ("cancelado", "Cancelado"),
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

    motivo_cancelamento = models.TextField(blank=True)
    data_cancelamento = models.DateField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    latitude = models.FloatField(null=True, blank=True, editable=False)
    longitude = models.FloatField(null=True, blank=True, editable=False)

    cpf_digitos = models.CharField(max_length=14, blank=True, editable=False, db_index=True)
    portal_senha_hash = models.CharField(max_length=128, blank=True, editable=False)
    portal_senha_definida_em = models.DateTimeField(null=True, blank=True, editable=False)
    portal_tentativas_falhas = models.PositiveSmallIntegerField(default=0, editable=False)
    portal_bloqueado_ate = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-criado_em"]

    def save(self, *args, **kwargs):
        self.cpf_digitos = "".join(ch for ch in (self.cpf_cnpj or "") if ch.isdigit())
        super().save(*args, **kwargs)

    def valor_mensal(self):
        return self.plano.valor_mensal if self.plano else 0

    def pago_mes_atual(self):
        primeiro_dia = timezone.now().date().replace(day=1)
        return self.pagamentos.filter(mes_referencia=primeiro_dia).exists()

    def endereco_completo(self):
        linha1 = ", ".join(p for p in [self.logradouro, self.numero] if p)
        linha2 = " - ".join(p for p in [self.bairro, self.cidade, self.estado] if p)
        return " · ".join(p for p in [linha1, linha2] if p) or "Endereço não informado"

    def telefone_digitos(self):
        return "".join(ch for ch in (self.telefone or "") if ch.isdigit())

    def telefone_whatsapp(self):
        digitos = self.telefone_digitos()
        if digitos and not digitos.startswith("55"):
            digitos = "55" + digitos
        return digitos

    def __str__(self):
        return self.nome


class Chamado(models.Model):
    TIPO_CHOICES = [
        ("sem_sinal", "Sem sinal"),
        ("lentidao", "Lentidão"),
        ("instalacao", "Instalação nova"),
        ("equipamento", "Troca de senha do Wi-Fi"),
        ("alteracao_plano", "Alteração de Plano"),
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
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="chamados_abertos"
    )
    descricao = models.TextField("Observação (do operador)", blank=True)
    observacao_fechamento = models.TextField("Observação de fechamento (do técnico)", blank=True)
    pego_em = models.DateTimeField(null=True, blank=True)
    atendimento_iniciado_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Quando o técnico bateu a foto e apertou 'Iniciar Atendimento' (chegada no cliente)",
    )
    foto_inicio = models.ImageField(
        "Foto de início (obrigatória)", upload_to="chamados/inicio/%Y/%m/", null=True, blank=True
    )
    atendimento_iniciado_lat = models.FloatField(null=True, blank=True, editable=False)
    atendimento_iniciado_lng = models.FloatField(null=True, blank=True, editable=False)
    atendimento_iniciado_precisao = models.FloatField(
        null=True, blank=True, editable=False,
        help_text="Margem de erro do GPS em metros, informada pelo navegador",
    )
    atendimento_iniciado_distancia_metros = models.FloatField(
        null=True, blank=True, editable=False,
        help_text="Distância entre onde o técnico estava e o endereço cadastrado do cliente, calculada no momento do início",
    )
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

    DISTANCIA_ALERTA_METROS = 300

    def duracao_atendimento(self):
        inicio = self.atendimento_iniciado_em or self.pego_em
        if inicio and self.concluido_em:
            return self.concluido_em - inicio
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

    def distancia_suspeita(self):
        """True se o técnico iniciou o atendimento longe demais do endereço cadastrado do cliente."""
        if self.atendimento_iniciado_distancia_metros is None:
            return False
        return self.atendimento_iniciado_distancia_metros > self.DISTANCIA_ALERTA_METROS

    def distancia_formatada(self):
        d = self.atendimento_iniciado_distancia_metros
        if d is None:
            return None
        if d >= 1000:
            return f"{d / 1000:.1f} km".replace(".", ",")
        return f"{int(round(d))} m"

    def link_mapa_inicio(self):
        if self.atendimento_iniciado_lat is None or self.atendimento_iniciado_lng is None:
            return None
        return f"https://www.google.com/maps?q={self.atendimento_iniciado_lat},{self.atendimento_iniciado_lng}"


class ChamadoAnexo(models.Model):
    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name="anexos")
    imagem = models.ImageField(upload_to="chamados/%Y/%m/")
    enviado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo do chamado #{self.chamado_id}"


class ChamadoDevolucao(models.Model):
    """Registro de quando um técnico devolveu o chamado pra fila (ex: chegou e o
    cliente não estava em casa), pra ficar guardado o motivo e quem devolveu."""

    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name="devolucoes")
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    motivo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Devolução de chamado"
        verbose_name_plural = "Devoluções de chamado"

    def __str__(self):
        return f"Devolução do chamado #{self.chamado_id} por {self.tecnico}"


class MovimentacaoReceita(models.Model):
    TIPO_CHOICES = [
        ("novo_cliente", "Novo cliente"),
        ("cancelamento", "Cancelamento"),
        ("upgrade", "Upgrade de plano"),
        ("downgrade", "Downgrade de plano"),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="movimentacoes_receita")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor_anterior = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    valor_novo = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Movimentação de receita"
        verbose_name_plural = "Movimentações de receita"

    def diferenca(self):
        return self.valor_novo - self.valor_anterior

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.cliente.nome}"


class Pagamento(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="pagamentos")
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    mes_referencia = models.DateField(help_text="Dia 1 do mês a que esse pagamento se refere")
    data_pagamento = models.DateField()
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-mes_referencia"]
        unique_together = ("cliente", "mes_referencia")
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self):
        return f"{self.cliente.nome} - {self.mes_referencia.strftime('%m/%Y')}"


class DebitoCongelado(models.Model):
    """Dívidas antigas que ainda não foram negociadas — ficam de lado, fora do
    somatório mensal, até o dia em que forem negociadas e virarem parcelas normais."""
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_origem = models.DateField(null=True, blank=True, help_text="De quando é essa dívida (opcional)")
    observacoes = models.TextField(blank=True)

    negociado = models.BooleanField(default=False)
    negociado_em = models.DateTimeField(null=True, blank=True)
    conta_pagar_gerada = models.ForeignKey(
        "ContaPagar", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Débito congelado"
        verbose_name_plural = "Débitos congelados"

    def __str__(self):
        return self.descricao


class ContaPagar(models.Model):
    STATUS_CHOICES = [("pendente", "Pendente"), ("agendado", "Agendado"), ("pago", "Pago")]
    FORMA_PAGAMENTO_CHOICES = [
        ("avista", "À vista"),
        ("boleto", "Boleto parcelado"),
        ("cartao", "Cartão parcelado"),
    ]
    descricao = models.CharField(max_length=200)
    vencimento = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")

    recorrente = models.BooleanField("Débito fixo (repete todo mês)", default=False)
    gerada_de = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="proximas"
    )

    forma_pagamento = models.CharField(max_length=20, choices=FORMA_PAGAMENTO_CHOICES, default="avista")
    parcela_atual = models.PositiveIntegerField(default=1)
    total_parcelas = models.PositiveIntegerField(default=1)

    nota_fiscal = models.FileField("Nota fiscal (PDF)", upload_to="notas_fiscais/%Y/%m/", null=True, blank=True)

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
    detalhes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Log de atividade"
        verbose_name_plural = "Histórico de movimentações"

    def __str__(self):
        return f"{self.acao} - {self.usuario}"


# ---------------------------------------------------------------------------
# ESTOQUE DE MATERIAL
# ---------------------------------------------------------------------------
class Material(models.Model):
    UNIDADE_CHOICES = [
        ("un", "Unidade"),
        ("m", "Metros"),
        ("cx", "Caixa"),
        ("rolo", "Rolo"),
    ]

    nome = models.CharField(max_length=150)
    unidade_medida = models.CharField(max_length=10, choices=UNIDADE_CHOICES, default="un")
    estoque_minimo = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Avisa quando o saldo ficar igual ou abaixo deste valor (deixe 0 pra não avisar)",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Material"
        verbose_name_plural = "Materiais (Estoque)"

    def saldo_atual(self):
        entradas = self.movimentacoes.filter(tipo="entrada").aggregate(total=models.Sum("quantidade"))["total"] or 0
        saidas = self.movimentacoes.filter(tipo="saida").aggregate(total=models.Sum("quantidade"))["total"] or 0
        return entradas - saidas

    def estoque_baixo(self):
        return self.estoque_minimo > 0 and self.saldo_atual() <= self.estoque_minimo

    def saldo_exibicao(self):
        from .utils import formatar_quantidade_material
        return formatar_quantidade_material(
            self.saldo_atual(), self.unidade_medida, self.get_unidade_medida_display()
        )

    def __str__(self):
        return f"{self.nome} ({self.get_unidade_medida_display()})"


class MovimentacaoEstoque(models.Model):
    TIPO_CHOICES = [
        ("entrada", "Entrada (Compra)"),
        ("saida", "Saída (Retirada)"),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="materiais_retirados", limit_choices_to={"role__in": ["tecnico", "admin"]},
        help_text="Pra quem o material foi liberado (só faz sentido em Retirada)",
    )
    chamado = models.ForeignKey(
        Chamado, on_delete=models.SET_NULL, null=True, blank=True, related_name="materiais_usados",
        help_text="Chamado relacionado (opcional)",
    )
    observacao = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Movimentação de estoque"
        verbose_name_plural = "Movimentações de estoque"

    def quantidade_exibicao(self):
        from .utils import formatar_quantidade_material
        return formatar_quantidade_material(
            self.quantidade, self.material.unidade_medida, self.material.get_unidade_medida_display()
        )

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.material.nome} ({self.quantidade})"


# ---------------------------------------------------------------------------
# PONTO (JORNADA DE TRABALHO)
# ---------------------------------------------------------------------------
class JornadaTrabalho(models.Model):
    """Horário de trabalho de cada funcionário (Operador ou Técnico). Cada um pode
    ter um horário diferente — por isso é configurável por pessoa, não fixo no
    código. Segunda a sexta tem 2 turnos (manhã e tarde); sábado é um turno único
    e pode ser desligado (folga aos sábados) por pessoa."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jornada"
    )
    seg_sex_entrada = models.TimeField("Entrada (seg a sex)", default=time_cls(8, 0))
    seg_sex_saida_almoco = models.TimeField("Saída para almoço", default=time_cls(12, 0))
    seg_sex_volta_almoco = models.TimeField("Volta do almoço", default=time_cls(14, 0))
    seg_sex_saida = models.TimeField("Saída (seg a sex)", default=time_cls(18, 0))
    sabado_ativo = models.BooleanField("Trabalha aos sábados?", default=True)
    sabado_entrada = models.TimeField("Entrada (sábado)", default=time_cls(8, 0))
    sabado_saida = models.TimeField("Saída (sábado)", default=time_cls(12, 0))
    tolerancia_minutos = models.PositiveIntegerField(
        "Tolerância (minutos)", default=10,
        help_text="Quantos minutos de atraso ainda não contam como atraso",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jornada de trabalho"
        verbose_name_plural = "Jornadas de trabalho"

    def carga_horaria_dia(self, data):
        """Devolve quantas horas essa pessoa deveria trabalhar num dia específico
        (0 se for domingo, ou sábado com sabado_ativo=False)."""
        dia_semana = data.weekday()  # 0=segunda ... 5=sábado, 6=domingo
        if dia_semana == 6:
            return 0.0
        if dia_semana == 5:
            if not self.sabado_ativo:
                return 0.0
            entrada = datetime.combine(data, self.sabado_entrada)
            saida = datetime.combine(data, self.sabado_saida)
            return round((saida - entrada).total_seconds() / 3600, 2)
        manha = datetime.combine(data, self.seg_sex_saida_almoco) - datetime.combine(data, self.seg_sex_entrada)
        tarde = datetime.combine(data, self.seg_sex_saida) - datetime.combine(data, self.seg_sex_volta_almoco)
        return round((manha + tarde).total_seconds() / 3600, 2)

    def __str__(self):
        return f"Jornada de {self.usuario}"


class RegistroPonto(models.Model):
    TIPO_CHOICES = [
        ("entrada", "Entrada"),
        ("saida_almoco", "Saída para almoço"),
        ("volta_almoco", "Volta do almoço"),
        ("saida", "Saída"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registros_ponto"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    data_hora = models.DateTimeField(default=timezone.now)
    liberado_mais_cedo = models.BooleanField(
        default=False, help_text="Marcado quando o Administrador autoriza uma saída/registro fora do horário normal"
    )
    eh_chamada_de_volta = models.BooleanField(
        default=False,
        help_text="Marcado quando essa entrada é de um 'chamado de volta' do Administrador (emergência), depois de já ter saído no dia",
    )
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    observacao = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True, editable=False)
    longitude = models.FloatField(null=True, blank=True, editable=False)
    precisao_metros = models.FloatField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "Registro de ponto"
        verbose_name_plural = "Registros de ponto"

    def __str__(self):
        return f"{self.usuario} - {self.get_tipo_display()} em {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    def link_mapa(self):
        if self.latitude is None or self.longitude is None:
            return None
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"


class AbonoPonto(models.Model):
    """Quando o Administrador abona um dia (ex: atestado médico), esse dia não
    conta como falta/débito de horas pro funcionário."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="abonos_ponto"
    )
    data = models.DateField()
    motivo = models.CharField(max_length=255, blank=True)
    anexo = models.FileField(
        "Atestado (PDF ou imagem)", upload_to="atestados/%Y/%m/", null=True, blank=True
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "data")
        ordering = ["-data"]
        verbose_name = "Abono de ponto"
        verbose_name_plural = "Abonos de ponto"

    def __str__(self):
        return f"Abono de {self.usuario} em {self.data.strftime('%d/%m/%Y')}"


class LiberacaoExtraPonto(models.Model):
    """Quando o Administrador precisa chamar de volta alguém que já bateu o ponto
    de saída (ex: emergência), ele libera aqui — a próxima vez que a pessoa entrar
    no sistema, vai poder bater um novo ciclo de ponto (entrada -> ... -> saída)
    mesmo já tendo saído hoje. Cada liberação vale pra um novo ciclo só; o
    Administrador precisa liberar de novo se precisar chamar de volta outra vez."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liberacoes_extra_ponto"
    )
    data = models.DateField(default=timezone.localdate)
    usada = models.BooleanField(default=False)
    motivo = models.CharField(max_length=255, blank=True)
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Liberação extra de ponto"
        verbose_name_plural = "Liberações extras de ponto"

    def __str__(self):
        status = "usada" if self.usada else "pendente"
        return f"Liberação extra de {self.usuario} em {self.data} ({status})"


# ---------------------------------------------------------------------------
# PORTAL DO CLIENTE
# ---------------------------------------------------------------------------
class ConfiguracaoEmpresa(models.Model):
    """Dados da empresa usados no Portal do Cliente (WhatsApp, nome exibido) e
    a identidade visual (logo + cor) do sistema inteiro — pra quando alugar
    pra outra empresa, ela pode trocar a marca sem mexer em código.
    Existe só um registro (padrão de 'configuração única')."""

    nome_fantasia = models.CharField(max_length=150, blank=True)
    whatsapp_numero = models.CharField(
        max_length=20, blank=True,
        help_text="Só números, com DDD e DDI (ex: 5581999998888) — usado no botão de WhatsApp do Portal do Cliente",
    )
    mensagem_boas_vindas = models.CharField(
        max_length=255, blank=True,
        help_text="Mensagem curta mostrada no topo do Portal do Cliente (opcional)",
    )
    logo = models.ImageField(
        upload_to="marca/", null=True, blank=True,
        help_text="Substitui o ícone/nome padrão no menu do sistema e no Portal do Cliente",
    )
    cor_primaria = models.CharField(
        max_length=7, default="#2563eb",
        help_text="Cor principal do sistema (botões, destaque do menu). Formato: #2563eb",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da Empresa"
        verbose_name_plural = "Configuração da Empresa"

    def __str__(self):
        return self.nome_fantasia or "Configuração da Empresa"

    @classmethod
    def obter(cls):
        obj, _criado = cls.objects.get_or_create(pk=1)
        return obj


class Promocao(models.Model):
    """Avisos/promoções que o Administrador cadastra e que aparecem na tela
    inicial do Portal do Cliente."""

    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    imagem = models.ImageField(upload_to="promocoes/%Y/%m/", null=True, blank=True)
    ativa = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Promoção"
        verbose_name_plural = "Promoções"

    def __str__(self):
        return self.titulo


class SolicitacaoLiberacaoConfianca(models.Model):
    """Pedido feito pelo cliente no Portal, pedindo pra internet ser liberada
    por confiança mesmo com a fatura em aberto (ex: vai pagar em breve).
    O Administrador/Operador vê e marca como atendida depois de resolver."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="solicitacoes_liberacao")
    criado_em = models.DateTimeField(auto_now_add=True)
    atendida = models.BooleanField(default=False)
    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    atendida_em = models.DateTimeField(null=True, blank=True)
    observacao_admin = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Solicitação de liberação de confiança"
        verbose_name_plural = "Solicitações de liberação de confiança"

    def __str__(self):
        status = "atendida" if self.atendida else "pendente"
        return f"Liberação de confiança - {self.cliente.nome} ({status})"


# ---------------------------------------------------------------------------
# LICENÇA DO SISTEMA (pra alugar o sistema pra outras empresas)
# ---------------------------------------------------------------------------
class LicencaSistema(models.Model):
    """Controle de aluguel do sistema. Se a data de vencimento passar (mais
    a carência), o sistema inteiro fica bloqueado pra quem alugou — só quem
    tem acesso de superusuário (o dono do sistema, não o cliente que alugou)
    consegue entrar pra ver/editar essa tela e liberar de novo."""

    nome_contratante = models.CharField(
        max_length=150, blank=True,
        help_text="Nome da empresa que está alugando o sistema (só pra você identificar)",
    )
    data_vencimento = models.DateField(
        null=True, blank=True,
        help_text="Depois dessa data (+ carência), o sistema bloqueia sozinho. Deixe em branco pra nunca bloquear.",
    )
    dias_carencia = models.PositiveSmallIntegerField(
        default=3, help_text="Quantos dias depois do vencimento o sistema ainda deixa usar, antes de bloquear",
    )
    bloqueado_manualmente = models.BooleanField(
        default=False, help_text="Bloqueia o sistema na hora, independente da data (ex: pediu pra cancelar)",
    )
    mensagem_bloqueio = models.CharField(
        max_length=255, blank=True,
        help_text="Mensagem mostrada pra quem tentar acessar o sistema bloqueado (opcional)",
    )
    observacoes = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Licença do Sistema"
        verbose_name_plural = "Licença do Sistema"

    def __str__(self):
        return self.nome_contratante or "Licença do Sistema"

    @classmethod
    def obter(cls):
        obj, _criado = cls.objects.get_or_create(pk=1)
        return obj

    def esta_bloqueado(self):
        if self.bloqueado_manualmente:
            return True
        if not self.data_vencimento:
            return False
        from datetime import timedelta
        from django.utils import timezone
        limite = self.data_vencimento + timedelta(days=self.dias_carencia)
        return timezone.now().date() > limite

    def dias_ate_vencer(self):
        if not self.data_vencimento:
            return None
        from django.utils import timezone
        return (self.data_vencimento - timezone.now().date()).days
