from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('recruteur', 'Recruteur'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='recruteur')

    def __str__(self):
        return f"{self.username} ({self.role})"


class Poste(models.Model):
    titre = models.CharField(max_length=200)
    description = models.TextField()
    competences_requises = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre


class Candidat(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class CV(models.Model):
    FORMAT_CHOICES = [('pdf', 'PDF'), ('docx', 'DOCX')]

    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='cvs')
    fichier = models.FileField(upload_to='cvs/')
    format_fichier = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    texte_extrait = models.TextField(blank=True)
    email_source = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CV de {self.candidat}"


class Candidature(models.Model):
    STATUT_CHOICES = [
        ('nouveau', 'Nouveau'),
        ('en_cours', 'En cours'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
    ]

    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='candidatures')
    poste = models.ForeignKey(Poste, on_delete=models.CASCADE, related_name='candidatures')
    cv = models.ForeignKey(CV, on_delete=models.SET_NULL, null=True, related_name='candidatures')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='nouveau')
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidat} → {self.poste} ({self.statut})"

    class Meta:
        ordering = ['-score']


class EmailLog(models.Model):
    """
    Journal de traçabilité de chaque email Outlook traité.
    Permet d'éviter les doublons et d'auditer les imports automatiques.
    """
    STATUS_CHOICES = [
        ('processed', 'Traité avec succès'),
        ('duplicate', 'Doublon ignoré'),
        ('error', 'Erreur de traitement'),
        ('no_cv', 'Pas de CV détecté'),
    ]

    # Identifiant unique du message Outlook (Graph API)
    message_id = models.CharField(max_length=512, unique=True, db_index=True)

    # Métadonnées de l'email
    sender_email = models.EmailField(blank=True)
    sender_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    received_at = models.CharField(max_length=50, blank=True)  # ISO datetime string
    filename = models.CharField(max_length=300, blank=True)

    # Résultat du traitement
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processed')
    error_message = models.TextField(blank=True)

    # Lien vers le candidat créé (null si erreur)
    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Log email Outlook"
        verbose_name_plural = "Logs emails Outlook"

    def __str__(self):
        return f"[{self.status}] {self.sender_email} — {self.filename} ({self.created_at:%Y-%m-%d %H:%M})"


class SyncHistory(models.Model):
    """
    Historique des synchronisations Outlook.
    Chaque exécution du pipeline crée une entrée.
    """
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    emails_scanned = models.IntegerField(default=0)
    cvs_found = models.IntegerField(default=0)
    cvs_created = models.IntegerField(default=0)
    cvs_duplicate = models.IntegerField(default=0)
    cvs_error = models.IntegerField(default=0)
    triggered_by = models.CharField(max_length=50, default='manual')  # manual / cron / api
    errors_json = models.TextField(blank=True, default='[]')

    class Meta:
        ordering = ['-started_at']
        verbose_name = "Historique de synchronisation"
        verbose_name_plural = "Historiques de synchronisation"

    def __str__(self):
        return f"Sync {self.started_at:%Y-%m-%d %H:%M} — {self.cvs_created} créés / {self.cvs_error} erreurs"