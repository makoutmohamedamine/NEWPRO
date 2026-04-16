"""
Pipeline Gmail → ML → Base de données
======================================
Identique au pipeline Outlook mais utilise Gmail comme source d'emails.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile

from .pipeline import PipelineReport, _first_name, _last_name, _detect_format, _resolve_poste

logger = logging.getLogger(__name__)


class GmailCVPipeline:
    """Pipeline complet : Gmail → ML → Django DB."""

    def __init__(self, max_messages: int = 50):
        self._max_messages = max_messages

    def run(self) -> PipelineReport:
        report = PipelineReport()
        report.started_at = datetime.now().isoformat()

        try:
            from .gmail_connector import GmailCVConnector
            from .ml_classifier import get_classifier
            from .models import EmailLog, Candidat, CV, Candidature

            # ── 1. Vérifier que le token Gmail existe ──────────────────────────
            connector = GmailCVConnector.from_env()
            connection_test = connector.test_connection()

            if connection_test['status'] != 'ok':
                msg = f"Connexion Gmail échouée : {connection_test.get('error', 'inconnue')}"
                logger.error(msg)
                report.errors.append(msg)
                report.finished_at = datetime.now().isoformat()
                return report

            # ── 2. IDs déjà traités ────────────────────────────────────────────
            already_processed = set(
                EmailLog.objects.values_list('message_id', flat=True)
            )

            # ── 3. Classificateur ML ───────────────────────────────────────────
            classifier = get_classifier()

            # ── 4. Parcourir les emails Gmail ──────────────────────────────────
            for attachment in connector.fetch_new_cvs(
                already_processed_ids=already_processed,
                max_messages=self._max_messages,
            ):
                report.emails_scanned += 1
                report.cvs_found += 1

                if EmailLog.objects.filter(message_id=attachment.message_id).exists():
                    report.cvs_duplicate += 1
                    continue

                try:
                    candidat = self._process_attachment(attachment, classifier)
                    EmailLog.objects.create(
                        message_id=attachment.message_id,
                        sender_email=attachment.sender_email,
                        sender_name=attachment.sender_name,
                        subject=attachment.subject,
                        received_at=attachment.received_at,
                        filename=attachment.filename,
                        candidat=candidat,
                        status='processed',
                    )
                    report.cvs_created += 1
                    logger.info("CV traité : %s → candidat #%d", attachment.filename, candidat.id)

                except Exception as exc:
                    report.cvs_error += 1
                    error_msg = f"Erreur '{attachment.filename}' ({attachment.sender_email}) : {exc}"
                    report.errors.append(error_msg)
                    logger.exception(error_msg)
                    try:
                        EmailLog.objects.create(
                            message_id=attachment.message_id,
                            sender_email=attachment.sender_email,
                            sender_name=attachment.sender_name,
                            subject=attachment.subject,
                            received_at=attachment.received_at,
                            filename=attachment.filename,
                            candidat=None,
                            status='error',
                            error_message=str(exc),
                        )
                    except Exception:
                        pass

        except Exception as exc:
            msg = f"Erreur critique pipeline Gmail : {exc}"
            report.errors.append(msg)
            logger.exception(msg)

        report.finished_at = datetime.now().isoformat()
        return report

    def _process_attachment(self, attachment, classifier):
        from .models import Candidat, CV, Candidature

        result = classifier.analyse(
            cv_bytes=attachment.content_bytes,
            filename=attachment.filename,
            sender_email=attachment.sender_email,
            sender_name=attachment.sender_name,
        )

        candidate_email = result.email or attachment.sender_email
        if not candidate_email:
            import uuid
            candidate_email = f"inconnu_{uuid.uuid4().hex[:8]}@gmail-import.local"

        candidat, created = Candidat.objects.get_or_create(
            email=candidate_email,
            defaults={
                'nom':       _last_name(result.full_name),
                'prenom':    _first_name(result.full_name),
                'telephone': result.phone,
            },
        )
        if not created and not candidat.telephone and result.phone:
            candidat.telephone = result.phone
            candidat.save(update_fields=['telephone'])

        file_obj = InMemoryUploadedFile(
            file=BytesIO(attachment.content_bytes),
            field_name='fichier',
            name=attachment.filename,
            content_type=attachment.content_type or 'application/octet-stream',
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

        poste = _resolve_poste(result.best_profile)
        existing = Candidature.objects.filter(candidat=candidat, poste=poste).first()
        if existing:
            if result.match_score > (existing.score or 0):
                existing.score = result.match_score
                existing.cv = cv_obj
                existing.save(update_fields=['score', 'cv', 'updated_at'])
        else:
            Candidature.objects.create(
                candidat=candidat,
                poste=poste,
                cv=cv_obj,
                score=result.match_score,
                statut='nouveau',
            )

        return candidat

    def test_connection(self) -> dict:
        try:
            from .gmail_connector import GmailCVConnector
            connector = GmailCVConnector.from_env()
            return connector.test_connection()
        except Exception as exc:
            return {'status': 'error', 'error': str(exc), 'provider': 'gmail'}


_pipeline: GmailCVPipeline | None = None


def get_gmail_pipeline() -> GmailCVPipeline:
    global _pipeline
    if _pipeline is None:
        max_msg = int(os.environ.get('GMAIL_MAX_MESSAGES', 50))
        _pipeline = GmailCVPipeline(max_messages=max_msg)
    return _pipeline
