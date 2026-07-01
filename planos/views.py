from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.contrib.auth.decorators import login_required

from django.http import (
    JsonResponse,
    HttpResponse
)

from django.db.models import Q

from .models import PlanoInternet
from .forms import PlanoForm


@login_required
def lista_planos(request):

    busca = request.GET.get(
        "busca",
        ""
    ).strip()

    planos = PlanoInternet.objects.all()

    if busca:

        planos = planos.filter(

            Q(nome__icontains=busca)

            |

            Q(velocidade__icontains=busca)

        )

    return render(

        request,

        "planos/lista_planos.html",

        {

            "planos": planos,

            "busca": busca,

        }

    )


@login_required
def novo_plano(request):

    if request.method == "POST":

        form = PlanoForm(request.POST)

        if form.is_valid():

            form.save()

            return redirect("/planos/")

    else:

        form = PlanoForm()

    return render(

        request,

        "planos/novo_plano.html",

        {

            "form": form

        }

    )


@login_required
def editar_plano(

    request,

    plano_id

):

    plano = get_object_or_404(

        PlanoInternet,

        id=plano_id

    )

    if request.method == "POST":

        form = PlanoForm(

            request.POST,

            instance=plano

        )

        if form.is_valid():

            form.save()

            return redirect("/planos/")

    else:

        form = PlanoForm(

            instance=plano

        )

    return render(

        request,

        "planos/editar_plano.html",

        {

            "form": form,

            "plano": plano,

        }

    )


@login_required
def detalhe_plano(

    request,

    plano_id

):

    plano = get_object_or_404(

        PlanoInternet,

        id=plano_id

    )

    return render(

        request,

        "planos/detalhe_plano.html",

        {

            "plano": plano

        }

    )


@login_required
def excluir_plano(

    request,

    plano_id

):

    plano = get_object_or_404(

        PlanoInternet,

        id=plano_id

    )

    if request.method == "POST":

        plano.delete()

        return redirect("/planos/")

    return render(

        request,

        "planos/excluir_plano.html",

        {

            "plano": plano

        }

    )


def plano_json(

    request,

    plano_id

):

    plano = get_object_or_404(

        PlanoInternet,

        id=plano_id

    )

    return JsonResponse({

        "id": plano.id,

        "nome": plano.nome,

        "velocidade": plano.velocidade,

        "valor": str(plano.valor),

    })