from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("recruitment", "0007_data_ownership_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Domaine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("actif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "domains",
                "ordering": ["nom"],
            },
        ),
        migrations.AddField(
            model_name="candidat",
            name="domaine",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="candidats",
                to="recruitment.domaine",
            ),
        ),
        migrations.AlterField(
            model_name="candidature",
            name="statut",
            field=models.CharField(
                choices=[
                    ("nouveau", "Nouveau"),
                    ("prequalifie", "Pre-qualifie"),
                    ("shortlist", "Shortlist"),
                    ("entretien_rh", "Entretien RH"),
                    ("entretien_technique", "Entretien Technique"),
                    ("validation_manager", "Validation Manager"),
                    ("accepte", "Accepte"),
                    ("refuse", "Refuse"),
                    ("entretien", "Entretien (legacy)"),
                    ("finaliste", "Finaliste (legacy)"),
                    ("offre", "Offre (legacy)"),
                    ("en_cours", "En cours (legacy)"),
                    ("archive", "Archive"),
                ],
                default="nouveau",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="CandidatureStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(blank=True, max_length=30)),
                ("new_status", models.CharField(max_length=30)),
                ("comment", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "candidature",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="recruitment.candidature",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "application_status_history",
                "ordering": ["-changed_at"],
            },
        ),
    ]
