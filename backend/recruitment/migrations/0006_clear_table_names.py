from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("recruitment", "0005_alter_candidature_options_candidat_annees_experience_and_more"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="customuser",
            table="users",
        ),
        migrations.AlterModelTable(
            name="poste",
            table="job_positions",
        ),
        migrations.AlterModelTable(
            name="candidat",
            table="candidates",
        ),
        migrations.AlterModelTable(
            name="cv",
            table="resumes",
        ),
        migrations.AlterModelTable(
            name="candidature",
            table="applications",
        ),
        migrations.AlterModelTable(
            name="emaillog",
            table="email_logs",
        ),
        migrations.AlterModelTable(
            name="synchistory",
            table="sync_history",
        ),
    ]
