from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ChatConversation, ChatMessage, CustomUser, Candidat, CV, Candidature, Poste, Entretien

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
admin.site.register(Entretien)


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "title", "updated_at", "message_count_display"]
    list_filter = ["created_at"]
    search_fields = ["title", "user__username"]
    readonly_fields = ["created_at", "updated_at"]

    def message_count_display(self, obj):
        return obj.messages.count()

    message_count_display.short_description = "Messages"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "conversation", "role", "created_at", "text_preview"]
    list_filter = ["role", "created_at"]
    search_fields = ["text", "user__username"]
    readonly_fields = ["created_at"]

    def text_preview(self, obj):
        return (obj.text or "")[:80]

    text_preview.short_description = "Aperçu"