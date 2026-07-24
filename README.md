# CTO Manager Pro

Sistema de gestão para provedor de internet: clientes, CTOs, planos,
chamados técnicos e financeiro — com perfis de Administrador, Operador
e Técnico.

## Como rodar no seu computador (Windows)

Abra o PowerShell **dentro da pasta do projeto** e rode, um comando por vez:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Depois abra o navegador em: http://127.0.0.1:8000

## Logins de teste (criados pelo seed_demo)

| Usuário     | Senha        | Perfil         |
|-------------|--------------|----------------|
| admin       | admin123     | Administrador  |
| operador1   | operador123  | Operador       |
| tecnico1    | tecnico123   | Técnico        |

Troque essas senhas antes de usar em produção de verdade.

## Painel administrativo do Django

Acesse http://127.0.0.1:8000/admin com o usuário `admin` para
cadastrar/editar qualquer coisa diretamente (útil enquanto as telas
customizadas ainda não cobrem tudo).

## Estrutura do projeto

- `accounts/` — usuário customizado com campo de perfil (role)
- `core/` — modelos e telas de Clientes, CTOs, Planos, Chamados e Financeiro
- `templates/` — HTML de todas as telas (Bootstrap 5)
- `core/management/commands/seed_demo.py` — popula o banco com dados de exemplo

## Próximos passos sugeridos

- Relatórios com gráficos
- Histórico de ações (auditoria)
- Backup automático do banco
- Publicar online (Render, Railway ou PythonAnywhere)
