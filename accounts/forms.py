from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone


class LoginComBloqueioForm(AuthenticationForm):
    """Igual ao formulário de login padrão do Django, só que barra a entrada
    se a conta estiver temporariamente bloqueada por muitas tentativas
    erradas seguidas (ver accounts.models.User.bloqueado_ate, controlado
    pelo sinal user_login_failed em core/signals.py)."""

    def confirm_login_allowed(self, user):
        if user.bloqueado_ate and user.bloqueado_ate > timezone.now():
            minutos = int((user.bloqueado_ate - timezone.now()).total_seconds() // 60) + 1
            raise ValidationError(
                f"Conta bloqueada por muitas tentativas de senha erradas. Tente de novo em {minutos} minuto(s).",
                code="conta_bloqueada",
            )
        super().confirm_login_allowed(user)
