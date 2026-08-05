"""Integração com o Mikrotik via API do RouterOS. Cria/atualiza o PPP Secret
do cliente (login/senha/velocidade/bloqueado) direto no roteador, a partir do
cadastro do cliente no CTO Manager Pro."""

import routeros_api

from .models import ConfiguracaoMikrotik


class MikrotikErro(Exception):
    """Erro de conexão ou de comando no Mikrotik — sempre com uma mensagem
    pronta pra mostrar pro usuário, sem precisar traduzir stacktrace."""
    pass


def _conectar():
    config = ConfiguracaoMikrotik.obter()
    if not config.ativo:
        raise MikrotikErro("A integração com o Mikrotik está desligada. Ative em Configuração do Mikrotik.")
    if not config.host:
        raise MikrotikErro("Endereço (IP) do Mikrotik não configurado.")
    try:
        return routeros_api.RouterOsApiPool(
            config.host,
            username=config.usuario,
            password=config.senha,
            port=config.porta,
            plaintext_login=True,
            use_ssl=config.usar_ssl,
            ssl_verify=False,
        )
    except Exception as e:
        raise MikrotikErro(f"Não foi possível conectar ao Mikrotik ({config.host}): {e}")


def testar_conexao():
    """Só confirma que dá pra conectar e autenticar — usado no botão
    'Testar conexão' da tela de configuração."""
    pool = _conectar()
    try:
        api = pool.get_api()
        identidade = api.get_resource("/system/identity").get()
        nome = identidade[0].get("name", "?") if identidade else "?"
        return f"Conectado com sucesso! Identidade do roteador: \"{nome}\"."
    except Exception as e:
        raise MikrotikErro(f"Conectou, mas deu erro ao consultar o roteador: {e}")
    finally:
        pool.disconnect()


def _nome_profile(plano):
    return f"cto-{plano.id}-{int(plano.velocidade_mb)}m"


def _garantir_profile(api, plano):
    """Cria (ou atualiza) no Mikrotik um PPP Profile com o limite de
    velocidade do plano. Um profile por plano, reaproveitado por todos os
    clientes daquele plano."""
    profiles = api.get_resource("/ppp/profile")
    nome = _nome_profile(plano)
    limite = f"{int(plano.velocidade_mb)}M/{int(plano.velocidade_mb)}M"
    existentes = profiles.get(name=nome)
    if existentes:
        profiles.set(id=existentes[0]["id"], **{"rate-limit": limite})
    else:
        profiles.add(name=nome, **{"rate-limit": limite})
    return nome


def sincronizar_cliente(cliente):
    """Cria ou atualiza o PPP Secret do cliente no Mikrotik: login, senha,
    perfil de velocidade (de acordo com o plano) e se está bloqueado ou não
    (de acordo com o status do cliente)."""
    if not cliente.login_pppoe:
        raise MikrotikErro("Esse cliente não tem \"Login PPPoE\" cadastrado.")
    if not cliente.plano:
        raise MikrotikErro("Esse cliente não tem plano definido.")

    pool = _conectar()
    try:
        api = pool.get_api()
        nome_profile = _garantir_profile(api, cliente.plano)
        secrets = api.get_resource("/ppp/secret")
        existentes = secrets.get(name=cliente.login_pppoe)
        bloqueado = cliente.status in ("suspenso", "cancelado", "inadimplente")
        dados = {
            "password": cliente.senha_pppoe or "",
            "service": "pppoe",
            "profile": nome_profile,
            "disabled": "yes" if bloqueado else "no",
        }
        if existentes:
            secrets.set(id=existentes[0]["id"], **dados)
        else:
            secrets.add(name=cliente.login_pppoe, **dados)

        # Sessão já conectada não pega velocidade/perfil novo sozinha — só na
        # próxima vez que reconectar. Derruba a sessão ativa (se tiver uma)
        # pra forçar reconectar na hora e já aplicar o novo limite.
        ativos = api.get_resource("/ppp/active").get(name=cliente.login_pppoe)
        for sessao in ativos:
            api.get_resource("/ppp/active").remove(id=sessao["id"])

        situacao = "BLOQUEADO" if bloqueado else "liberado"
        aviso_reconexao = " O cliente pode precisar reconectar o PPPoE pra pegar a velocidade nova." if ativos and not bloqueado else ""
        return f"Sincronizado! Plano {cliente.plano.velocidade_mb} Mega aplicado — cliente {situacao}.{aviso_reconexao}"
    except MikrotikErro:
        raise
    except Exception as e:
        raise MikrotikErro(f"Erro ao sincronizar \"{cliente.login_pppoe}\": {e}")
    finally:
        pool.disconnect()


def bloquear_cliente(cliente):
    """Bloqueia o PPPoE do cliente no Mikrotik e derruba a sessão ativa, se
    tiver uma conectada agora."""
    if not cliente.login_pppoe:
        raise MikrotikErro("Esse cliente não tem \"Login PPPoE\" cadastrado.")
    pool = _conectar()
    try:
        api = pool.get_api()
        secrets = api.get_resource("/ppp/secret")
        existentes = secrets.get(name=cliente.login_pppoe)
        if not existentes:
            raise MikrotikErro("Esse cliente ainda não foi sincronizado com o Mikrotik (usa \"Sincronizar\" primeiro).")
        secrets.set(id=existentes[0]["id"], disabled="yes")

        ativos = api.get_resource("/ppp/active").get(name=cliente.login_pppoe)
        for sessao in ativos:
            api.get_resource("/ppp/active").remove(id=sessao["id"])

        return "Cliente bloqueado no Mikrotik (sessão ativa derrubada, se havia uma)."
    except MikrotikErro:
        raise
    except Exception as e:
        raise MikrotikErro(f"Erro ao bloquear \"{cliente.login_pppoe}\": {e}")
    finally:
        pool.disconnect()


def liberar_cliente(cliente):
    """Libera de novo o PPPoE do cliente no Mikrotik."""
    if not cliente.login_pppoe:
        raise MikrotikErro("Esse cliente não tem \"Login PPPoE\" cadastrado.")
    pool = _conectar()
    try:
        api = pool.get_api()
        secrets = api.get_resource("/ppp/secret")
        existentes = secrets.get(name=cliente.login_pppoe)
        if not existentes:
            raise MikrotikErro("Esse cliente ainda não foi sincronizado com o Mikrotik (usa \"Sincronizar\" primeiro).")
        secrets.set(id=existentes[0]["id"], disabled="no")
        return "Cliente liberado no Mikrotik."
    except MikrotikErro:
        raise
    except Exception as e:
        raise MikrotikErro(f"Erro ao liberar \"{cliente.login_pppoe}\": {e}")
    finally:
        pool.disconnect()
