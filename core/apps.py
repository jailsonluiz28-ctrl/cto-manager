from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from . import signals  # noqa: F401

        import sys
        if "runserver" in sys.argv:
            import threading

            def _tarefas_iniciais():
                """Roda um pouquinho depois do servidor ligar de vez (não na
                hora do 'ready()'), pra não disparar o aviso do Django sobre
                acessar o banco cedo demais durante a inicialização."""
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

            threading.Timer(1.5, _tarefas_iniciais).start()
