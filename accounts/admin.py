from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Informações adicionais", {"fields": ("role", "telefone")}),
    )
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")


admin.site.register(User, CustomUserAdmin)
