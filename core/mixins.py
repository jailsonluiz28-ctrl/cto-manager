from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class SomenteAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Só o Administrador pode acessar."""
    def test_func(self):
        return self.request.user.role == "admin"


class SomenteOperacaoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Bloqueia o perfil Técnico (Admin e Operador podem acessar)."""
    def test_func(self):
        return self.request.user.role in ("admin", "operador")
