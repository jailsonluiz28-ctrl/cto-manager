#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cto_manager.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não consegui importar o Django. Você ativou o ambiente virtual "
            "e rodou 'pip install -r requirements.txt'?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
