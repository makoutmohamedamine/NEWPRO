from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Candidat, CV, Candidature, Poste

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Rôle', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']

admin.site.register(Poste)
admin.site.register(Candidat)
admin.site.register(CV)
admin.site.register(Candidature)