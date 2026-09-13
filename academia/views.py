from django.shortcuts import redirect, render


def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "academia/landing_page.html")
