from django.core.management.base import BaseCommand
from core.backup_utils import fazer_backup


class Command(BaseCommand):
    help = "Cria uma cópia de segurança (backup) do banco de dados atual."

    def handle(self, *args, **options):
        destino = fazer_backup()
        if destino:
            self.stdout.write(self.style.SUCCESS(f"Backup criado: {destino}"))
        else:
            self.stdout.write(self.style.WARNING("db.sqlite3 não encontrado — nada pra fazer backup."))
