"""
Pipeline d'intégration Outlook → ML → Base de données
======================================================
Orchestre le flux complet :
  Outlook inbox → Extraction CV → Analyse ML → Sauvegarde DB → Log

Peut être déclenché :
  - Manuellement via l'API REST (POST /api/outlook/sync/)
  - Par une tâche planifiée (cron / management command Django)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Optional

from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)


# ─── Résultat du pipeline ───────────────────────────────────────────────────────

@dataclass
class PipelineReport:
    """Rapport d'exécution d'un cycle de synchronisation."""
    started_at: str = ""
    finished_at: str = ""
    emails_scanned: int = 0
    cvs_found: int = 0
    cvs_created: int = 0
    cvs_duplicate: int = 0
    cvs_error: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.cvs_error == 0

    def to_dict(self) -> dict:
        return {
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "emailsScanned": self.emails_scanned,
            "cvsFound": self.cvs_found,
            "cvsCreated": self.cvs_created,
            "cvsDuplicate": self.cvs_duplicate,
            "cvsError": self.cvs_error,
            "success": self.success,
            "errors": self.errors,
        }


# ─── Pipeline principal ─────────────────────────────────────────────────────────

class OutlookCVPipeline:
    """
    Pipeline complet : Outlook → ML → Django DB.

    Étapes par CV :
      1. Récupérer l'email et la pièce jointe via Microsoft Graph
      2. Vérifier les doublons (message_id ou email candidat)
      3. Extraire et analyser le texte via ml_classifier
      4. Créer/mettre à jour les enregistrements Django
      5. Journaliser dans EmailLog
    """

    def __init__(self, max_messages: int = 50):
        self._max_messages = max_messages

    def run(self) -> PipelineReport:
        """
        Exécute un cycle complet de synchronisation.
        Retourne un rapport détaillé.
        """
        report = PipelineReport()
        report.started_at = datetime.now().isoformat()

        try:
            from .outlook_connector import OutlookCVExtractor
            from .ml_classifier import get_classifier
            from .models import EmailLog, Candidat, CV, Candidature, Poste

            # ── 1. Vérifier la configuration Azure ─────────────────────────────
            required_env = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "OUTLOOK_MAILBOX"]
            missing = [k for k in required_env if not os.environ.get(k)]
            if missing:
                msg = f"Variables d'environnement manquantes : {', '.join(missing)}"
                logger.error(msg)
                report.errors.append(msg)
                report.finished_at = datetime.now().isoformat()
                return report

            # ── 2. Récupérer les IDs déjà traités ──────────────────────────────
            already_processed = set(
                EmailLog.objects.values_list("message_id", flat=True)
            )

            # ── 3. Instancier le connecteur et le classificateur ────────────────
            extractor = OutlookCVExtractor.from_env()
            classifier = get_classifier()

            # ── 4. Itérer sur les pièces jointes ───────────────────────────────
            for attachment in extractor.fetch_new_cvs(
                already_processed_ids=already_processed,
                max_messages=self._max_messages,
                mark_as_read=True,
                move_to_processed=True,
            ):
                report.emails_scanned += 1
                report.cvs_found += 1

                # Vérification doublon (même message_id)
                if EmailLog.objects.filter(message_id=attachment.message_id).exists():
                    report.cvs_duplicate += 1
                    logger.debug("Doublon ignoré : message_id=%s", attachment.message_id)
                    continue

                try:
                    candidat = self._process_attachment(
                        attachment=attachment,
                        classifier=classifier,
                    )
                    # Journaliser le message traité
                    EmailLog.objects.create(
                        message_id=attachment.message_id,
                        sender_email=attachment.sender_email,
                        sender_name=attachment.sender_name,
                        subject=attachment.subject,
                        received_at=attachment.received_at,
                        filename=attachment.filename,
                        candidat=candidat,
                        status="processed",
                    )
                    report.cvs_created += 1
                    logger.info(
                        "CV traité : %s → candidat #%d (%s)",
                        attachment.filename, candidat.id, candidat.email,
                    )

                except Exception as exc:
                    report.cvs_error += 1
                    error_msg = f"Erreur traitement '{attachment.filename}' ({attachment.sender_email}) : {exc}"
                    report.errors.append(error_msg)
                    logger.exception(error_msg)

                    # Journaliser l'erreur
                    try:
                        from .models import EmailLog
                        EmailLog.objects.create(
                            message_id=attachment.message_id,
                            sender_email=attachment.sender_email,
                            sender_name=attachment.sender_name,
                            subject=attachment.subject,
                            received_at=attachment.received_at,
                            filename=attachment.filename,
                            candidat=None,
                            status="error",
                            error_message=str(exc),
                        )
                    except Exception:
                        pass

        except ImportError as exc:
            msg = f"Dépendance manquante : {exc}"
            report.errors.append(msg)
            logger.error(msg)
        except Exception as exc:
            msg = f"Erreur critique pipeline : {exc}"
            report.errors.append(msg)
            logger.exception(msg)

        report.finished_at = datetime.now().isoformat()
        return report

    def _process_attachment(self, attachment, classifier) -> "Candidat":
        """
        Traite une pièce jointe : analyse ML + sauvegarde en base.
        Retourne le Candidat créé ou mis à jour.
        """
        from .models import Candidat, CV, Candidature, Poste

        # ── Analyse ML ──────────────────────────────────────────────────────────
        result = classifier.analyse(
            cv_bytes=attachment.content_bytes,
            filename=attachment.filename,
            sender_email=attachment.sender_email,
            sender_name=attachment.sender_name,
        )

        # ── Résolution email ────────────────────────────────────────────────────
        candidate_email = result.email or attachment.sender_email
        if not candidate_email:
            import uuid
            candidate_email = f"inconnu_{uuid.uuid4().hex[:8]}@outlook-import.local"

        # ── Upsert Candidat ──────────────────────────────────────────────────────
        candidat, created = Candidat.objects.get_or_create(
            email=candidate_email,
            defaults={
                "nom": _last_name(result.full_name),
                "prenom": _first_name(result.full_name),
                "telephone": result.phone,
            },
        )
        if not created:
            # Enrichir si les champs sont vides
            if not candidat.telephone and result.phone:
                candidat.telephone = result.phone
                candidat.save(update_fields=["telephone"])

        # ── Sauvegarder le fichier CV ────────────────────────────────────────────
        file_obj = InMemoryUploadedFile(
            file=BytesIO(attachment.content_bytes),
            field_name="fichier",
            name=attachment.filename,
            content_type=attachment.content_type or "application/octet-stream",
            size=len(attachment.content_bytes),
            charset=None,
        )
        cv_obj = CV.objects.create(
            candidat=candidat,
            fichier=file_obj,
            format_fichier=_detect_format(attachment.filename),
            texte_extrait=result.raw_text[:10000],
            email_source=attachment.sender_email,
        )

        # ── Résoudre le poste cible ──────────────────────────────────────────────
        poste = _resolve_poste(result.best_profile)

        # ── Créer/mettre à jour la Candidature ──────────────────────────────────
        existing = Candidature.objects.filter(candidat=candidat, poste=poste).first()
        if existing:
            if result.match_score > (existing.score or 0):
                existing.score = result.match_score
                existing.cv = cv_obj
                existing.save(update_fields=["score", "cv", "updated_at"])
        else:
            Candidature.objects.create(
                candidat=candidat,
                poste=poste,
                cv=cv_obj,
                score=result.match_score,
                statut="nouveau",
            )

        return candidat

    def test_connection(self) -> dict:
        """Teste uniquement la connexion Outlook sans traiter de CV."""
        try:
            from .outlook_connector import OutlookCVExtractor
            extractor = OutlookCVExtractor.from_env()
            return extractor.test_connection()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else "Candidat"


def _last_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return " ".join(parts[1:]) if len(parts) > 1 else "Inconnu"


def _detect_format(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    return "docx" if ext in ("docx", "doc") else "pdf"


def _resolve_poste(profile_name: str) -> "Poste":
    """Trouve ou crée le poste correspondant au profil ML détecté."""
    from .models import Poste

    poste = Poste.objects.filter(titre__iexact=profile_name).first()
    if poste:
        return poste

    # Recherche partielle (ex: "Développeur Full Stack" → "Full Stack")
    for keyword in profile_name.split():
        if len(keyword) > 4:
            poste = Poste.objects.filter(titre__icontains=keyword).first()
            if poste:
                return poste

    # Créer un poste générique si aucun n'existe
    poste, _ = Poste.objects.get_or_create(
        titre=profile_name,
        defaults={
            "description": f"Poste détecté automatiquement par le système ML : {profile_name}",
            "competences_requises": "",
        },
    )
    return poste


# ─── Instance partagée ──────────────────────────────────────────────────────────

_pipeline: OutlookCVPipeline | None = None


def get_pipeline() -> OutlookCVPipeline:
    """Retourne l'instance partagée du pipeline."""
    global _pipeline
    if _pipeline is None:
        max_msg = int(os.environ.get("OUTLOOK_MAX_MESSAGES", 50))
        _pipeline = OutlookCVPipeline(max_messages=max_msg)
    return _pipeline
