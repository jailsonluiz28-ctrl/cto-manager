from django.contrib.auth.decorators import user_passes_test


def eh_administrador(user):

    return user.groups.filter(
        name='Administrador'
    ).exists()


def eh_operador(user):

    return user.groups.filter(
        name='Operador'
    ).exists()


def eh_tecnico(user):

    return user.groups.filter(
        name='Consulta do Técnico'
    ).exists()


def administrador_required(view_func):

    return user_passes_test(
        eh_administrador
    )(view_func)


def operador_required(view_func):

    return user_passes_test(
        lambda u:
        eh_administrador(u)
        or
        eh_operador(u)
    )(view_func)


def tecnico_required(view_func):

    return user_passes_test(
        lambda u:
        eh_administrador(u)
        or
        eh_operador(u)
        or
        eh_tecnico(u)
    )(view_func)