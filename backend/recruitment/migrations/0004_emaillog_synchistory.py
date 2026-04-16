from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField()),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('emails_scanned', models.IntegerField(default=0)),
                ('cvs_found', models.IntegerField(default=0)),
                ('cvs_created', models.IntegerField(default=0)),
                ('cvs_duplicate', models.IntegerField(default=0)),
                ('cvs_error', models.IntegerField(default=0)),
                ('triggered_by', models.CharField(default='manual', max_length=50)),
                ('errors_json', models.TextField(blank=True, default='[]')),
            ],
            options={
                'verbose_name': 'Historique de synchronisation',
                'verbose_name_plural': 'Historiques de synchronisation',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.CharField(db_index=True, max_length=512, unique=True)),
                ('sender_email', models.EmailField(blank=True)),
                ('sender_name', models.CharField(blank=True, max_length=200)),
                ('subject', models.CharField(blank=True, max_length=500)),
                ('received_at', models.CharField(blank=True, max_length=50)),
                ('filename', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(
                    choices=[
                        ('processed', 'Traité avec succès'),
                        ('duplicate', 'Doublon ignoré'),
                        ('error', 'Erreur de traitement'),
                        ('no_cv', 'Pas de CV détecté'),
                    ],
                    default='processed',
                    max_length=20,
                )),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('candidat', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='email_logs',
                    to='recruitment.candidat',
                )),
            ],
            options={
                'verbose_name': 'Log email Outlook',
                'verbose_name_plural': 'Logs emails Outlook',
                'ordering': ['-created_at'],
            },
        ),
    ]
