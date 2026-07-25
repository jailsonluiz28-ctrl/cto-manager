import shutil
from datetime import datetime
from django.conf import settings

BACKUPS_DIR = settings.BASE_DIR / "backups"
MAX_BACKUPS = 15


def fazer_backup():
    """Copia o db.sqlite3 atual pra pasta de backups, com data/hora no nome.
    Devolve o Path do arquivo criado, ou None se o banco não existir."""
    origem = settings.BASE_DIR / "db.sqlite3"
    if not origem.exists():
        return None

    BACKUPS_DIR.mkdir(exist_ok=True)
    agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino = BACKUPS_DIR / f"backup_{agora}.sqlite3"
    shutil.copy2(origem, destino)
    _limpar_backups_antigos()
    return destino


def _limpar_backups_antigos():
    """Mantém só os MAX_BACKUPS mais recentes, apaga o resto."""
    arquivos = sorted(BACKUPS_DIR.glob("backup_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antigo in arquivos[MAX_BACKUPS:]:
        antigo.unlink(missing_ok=True)


def listar_backups():
    if not BACKUPS_DIR.exists():
        return []
    arquivos = sorted(BACKUPS_DIR.glob("backup_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "nome": a.name,
            "tamanho_kb": round(a.stat().st_size / 1024, 1),
            "data": datetime.fromtimestamp(a.stat().st_mtime),
        }
        for a in arquivos
    ]


def fazer_backup_diario_se_necessario():
    """Chamado automaticamente quando o servidor sobe. Só faz 1 backup por dia,
    pra não ficar copiando toda hora que o Django recarrega sozinho."""
    BACKUPS_DIR.mkdir(exist_ok=True)
    marcador = BACKUPS_DIR / ".ultimo_backup_automatico"
    hoje = datetime.now().strftime("%Y-%m-%d")
    if marcador.exists() and marcador.read_text().strip() == hoje:
        return
    if fazer_backup():
        marcador.write_text(hoje)
