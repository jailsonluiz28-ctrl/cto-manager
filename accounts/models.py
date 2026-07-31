from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Administrador"),
        ("operador", "Operador"),
        ("tecnico", "Técnico"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="operador")
    telefone = models.CharField(max_length=20, blank=True)

    tentativas_login_falhas = models.PositiveSmallIntegerField(default=0, editable=False)
    bloqueado_ate = models.DateTimeField(null=True, blank=True, editable=False)

    def is_admin_role(self):
        return self.role == "admin"

    def is_operador_role(self):
        return self.role in ("admin", "operador")

    def is_tecnico_role(self):
        return self.role == "tecnico"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
