# Generated manually for ChatConversation + ChatMessage.conversation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_conversations(apps, schema_editor):
    ChatMessage = apps.get_model("recruitment", "ChatMessage")
    ChatConversation = apps.get_model("recruitment", "ChatConversation")
    uids = list(ChatMessage.objects.order_by().values_list("user_id", flat=True).distinct())
    for uid in uids:
        if uid is None:
            continue
        conv = ChatConversation.objects.create(user_id=uid, title="Historique")
        ChatMessage.objects.filter(user_id=uid).update(conversation_id=conv.id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("recruitment", "0010_chat_message_archive"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_conversations",
                        to=settings.AUTH_USER_MODEL,
                        db_index=True,
                    ),
                ),
            ],
            options={
                "db_table": "chat_conversations",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="conversation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="recruitment.chatconversation",
            ),
        ),
        migrations.RunPython(backfill_conversations, noop_reverse),
        migrations.AlterField(
            model_name="chatmessage",
            name="conversation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="recruitment.chatconversation",
            ),
        ),
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(fields=["conversation", "created_at"], name="chat_messag_conversa_idx"),
        ),
    ]
