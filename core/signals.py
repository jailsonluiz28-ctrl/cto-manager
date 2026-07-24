from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .middleware import get_current_user
from .models import Cliente, CTO, Chamado, Plano, LogAtividade


def _registrar(acao, detalhes=""):
    LogAtividade.objects.create(usuario=get_current_user(), acao=acao, detalhes=detalhes)


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    LogAtividade.objects.create(usuario=user, acao="Login no sistema", detalhes="")


@receiver(post_save, sender=Cliente)
def log_cliente_save(sender, instance, created, **kwargs):
    _registrar("Cliente cadastrado" if created else "Cliente editado", instance.nome)


@receiver(post_delete, sender=Cliente)
def log_cliente_delete(sender, instance, **kwargs):
    _registrar("Cliente excluído", instance.nome)


@receiver(post_save, sender=CTO)
def log_cto_save(sender, instance, created, **kwargs):
    _registrar("CTO cadastrada" if created else "CTO editada", instance.codigo)


@receiver(post_delete, sender=CTO)
def log_cto_delete(sender, instance, **kwargs):
    _registrar("CTO excluída", instance.codigo)


@receiver(post_save, sender=Chamado)
def log_chamado_save(sender, instance, created, **kwargs):
    if created:
        _registrar("Chamado aberto", f"#{instance.id} - {instance.cliente.nome}")
    else:
        _registrar("Chamado atualizado", f"#{instance.id} - {instance.get_status_display()}")


@receiver(post_save, sender=Plano)
def log_plano_save(sender, instance, created, **kwargs):
    _registrar("Plano cadastrado" if created else "Plano editado", instance.nome)
