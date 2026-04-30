from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Administrateur"),
        ("rh", "Responsable RH"),
        ("recruteur", "Recruteur"),
        ("manager", "Manager"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="recruteur")

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.username} ({self.role})"


class Poste(models.Model):
    titre = models.CharField(max_length=200)
    description = models.TextField()
    competences_requises = models.TextField(blank=True)
    competences_optionnelles = models.TextField(blank=True)
    langues_requises = models.TextField(blank=True)
    departement = models.CharField(max_length=120, blank=True)
    localisation = models.CharField(max_length=120, blank=True)
    type_contrat = models.CharField(max_length=80, blank=True)
    experience_min_annees = models.PositiveIntegerField(default=0)
    niveau_etudes_requis = models.CharField(max_length=120, blank=True)
    quota_cible = models.PositiveIntegerField(default=1)
    workflow_actif = models.BooleanField(default=True)
    score_qualification = models.FloatField(default=70)
    niveau_priorite = models.CharField(max_length=20, default="medium")
    poids_competences = models.FloatField(default=35)
    poids_experience = models.FloatField(default=25)
    poids_formation = models.FloatField(default=20)
    poids_langues = models.FloatField(default=10)
    poids_localisation = models.FloatField(default=5)
    poids_soft_skills = models.FloatField(default=5)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_postes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "job_positions"

    def __str__(self):
        return self.titre


class Candidat(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    localisation = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=20, default="manual")
    source_detail = models.CharField(max_length=255, blank=True)
    current_title = models.CharField(max_length=160, blank=True)
    niveau_etudes = models.CharField(max_length=120, blank=True)
    annees_experience = models.FloatField(default=0)
    competences = models.TextField(blank=True)
    langues = models.TextField(blank=True)
    soft_skills = models.TextField(blank=True)
    resume_profil = models.TextField(blank=True)
    domaine = models.ForeignKey("Domaine", on_delete=models.SET_NULL, null=True, blank=True, related_name="candidats")
    consentement_rgpd = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_candidats",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "candidates"

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class CV(models.Model):
    FORMAT_CHOICES = [("pdf", "PDF"), ("docx", "DOCX")]

    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name="cvs")
    fichier = models.FileField(upload_to="cvs/")
    format_fichier = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    texte_extrait = models.TextField(blank=True)
    email_source = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "resumes"

    def __str__(self):
        return f"CV de {self.candidat}"


class Candidature(models.Model):
    STATUT_CHOICES = [
        ("nouveau", "Nouveau"),
        ("prequalifie", "Pre-qualifie"),
        ("shortlist", "Shortlist"),
        ("entretien_rh", "Entretien RH"),
        ("entretien_technique", "Entretien Technique"),
        ("validation_manager", "Validation Manager"),
        ("accepte", "Accepte"),
        ("refuse", "Refuse"),
        # Legacy values kept for backward compatibility.
        ("entretien", "Entretien (legacy)"),
        ("finaliste", "Finaliste (legacy)"),
        ("offre", "Offre (legacy)"),
        ("en_cours", "En cours (legacy)"),
        ("archive", "Archive"),
    ]

    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name="candidatures")
    poste = models.ForeignKey(Poste, on_delete=models.CASCADE, related_name="candidatures")
    cv = models.ForeignKey(CV, on_delete=models.SET_NULL, null=True, related_name="candidatures")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="nouveau")
    score = models.FloatField(null=True, blank=True)
    recommandation = models.CharField(max_length=50, blank=True)
    workflow_step = models.CharField(max_length=80, blank=True)
    source_channel = models.CharField(max_length=20, default="manual")
    explication_score = models.TextField(blank=True)
    score_details_json = models.TextField(blank=True, default="{}")
    decision_comment = models.TextField(blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_candidatures",
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_candidatures",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidat} -> {self.poste} ({self.statut})"

    class Meta:
        db_table = "applications"
        ordering = ["-score", "-updated_at"]


class CandidatureStatusHistory(models.Model):
    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name="status_history")
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30)
    comment = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "application_status_history"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"#{self.candidature_id}: {self.previous_status} -> {self.new_status}"


class Domaine(models.Model):
    nom = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "domains"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ("processed", "Traite avec succes"),
        ("duplicate", "Doublon ignore"),
        ("error", "Erreur de traitement"),
        ("no_cv", "Pas de CV detecte"),
    ]

    message_id = models.CharField(max_length=512, unique=True, db_index=True)
    sender_email = models.EmailField(blank=True)
    sender_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    received_at = models.CharField(max_length=50, blank=True)
    filename = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="processed")
    error_message = models.TextField(blank=True)
    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_logs"
        ordering = ["-created_at"]
        verbose_name = "Log email Outlook"
        verbose_name_plural = "Logs emails Outlook"

    def __str__(self):
        return f"[{self.status}] {self.sender_email} - {self.filename} ({self.created_at:%Y-%m-%d %H:%M})"


class SyncHistory(models.Model):
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    emails_scanned = models.IntegerField(default=0)
    cvs_found = models.IntegerField(default=0)
    cvs_created = models.IntegerField(default=0)
    cvs_duplicate = models.IntegerField(default=0)
    cvs_error = models.IntegerField(default=0)
    triggered_by = models.CharField(max_length=50, default="manual")
    errors_json = models.TextField(blank=True, default="[]")

    class Meta:
        db_table = "sync_history"
        ordering = ["-started_at"]
        verbose_name = "Historique de synchronisation"
        verbose_name_plural = "Historiques de synchronisation"

    def __str__(self):
        return f"Sync {self.started_at:%Y-%m-%d %H:%M} - {self.cvs_created} crees / {self.cvs_error} erreurs"
