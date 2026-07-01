from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from dashboard.views import (
    home,
    lista_ctos_lotadas,
    sair,
)

urlpatterns = [

    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html'
        ),
        name='login'
    ),

    path(
        'logout/',
        sair,
        name='logout'
    ),

    path(
        '',
        home,
        name='home'
    ),

    path(
        'ctos-lotadas/',
        lista_ctos_lotadas,
        name='ctos_lotadas'
    ),

    path(
        'admin/',
        admin.site.urls
    ),

    path(
        'clientes/',
        include('clientes.urls')
    ),

    path(
        'ctos/',
        include('ctos.urls')
    ),

    path(
        'financeiro/',
        include('financeiro.urls')
    ),

    path(
        'planos/',
        include('planos.urls')
    ),

    path(
        'sistema/',
        include('sistema.urls')
    ),
]