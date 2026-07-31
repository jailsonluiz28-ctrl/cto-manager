from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from . import signals  # noqa: F401

        import sys
        if "runserver" in sys.argv:
            try:
                from .backup_utils import fazer_backup_diario_se_necessario
                fazer_backup_diario_se_necessario()
            except Exception:
                pass  # nunca deixa um problema de backup travar o sistema
            try:
                from .utils import limpar_auditoria_antiga
                limpar_auditoria_antiga()
            except Exception:
                pass  # nunca deixa um problema de limpeza travar o sistema
