"""
Connecteur Gmail API
====================
Récupère automatiquement les emails contenant des CVs (PDF/DOCX)
depuis Gmail via l'API Google.

Authentification : OAuth2 avec token.json stocké localement.
Autorisation initiale : python manage.py gmail_auth
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc'}

MIME_MAP = {
    '.pdf':  'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc':  'application/msword',
}


# ─── Structure de données (identique à outlook_connector) ─────────────────────

@dataclass
class EmailAttachment:
    """Pièce jointe CV extraite d'un email Gmail."""
    filename: str
    content_type: str
    content_bytes: bytes
    message_id: str
    sender_email: str
    sender_name: str
    subject: str
    received_at: datetime


# ─── Connecteur Gmail ──────────────────────────────────────────────────────────

class GmailCVConnector:
    """
    Connecteur Gmail OAuth2.

    Usage :
        connector = GmailCVConnector.from_env()
        for attachment in connector.fetch_new_cvs(already_processed):
            process(attachment)
    """

    def __init__(self, credentials_file: str, token_file: str):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self._service = None

    @classmethod
    def from_env(cls) -> GmailCVConnector:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_file = os.environ.get(
            'GMAIL_CLIENT_SECRET_FILE',
            os.path.join(backend_dir, 'client_secret.json'),
        )
        token_file = os.environ.get(
            'GMAIL_TOKEN_FILE',
            os.path.join(backend_dir, 'token.json'),
        )
        return cls(credentials_file=credentials_file, token_file=token_file)

    # ── Authentification ─────────────────────────────────────────────────────

    def _get_service(self):
        """Retourne le service Gmail authentifié (avec refresh automatique)."""
        if self._service is not None:
            return self._service

        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Rafraîchissement du token Gmail…")
                creds.refresh(Request())
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    f.write(creds.to_json())
            else:
                raise RuntimeError(
                    "Token Gmail introuvable ou invalide.\n"
                    "Lancez d'abord : python manage.py gmail_auth"
                )

        self._service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        return self._service

    # ── Test de connexion ─────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Teste la connexion Gmail et retourne un dict de statut."""
        try:
            service = self._get_service()
            profile = service.users().getProfile(userId='me').execute()
            return {
                'status': 'ok',
                'mailbox': profile.get('emailAddress', ''),
                'provider': 'gmail',
                'messagesTotal': profile.get('messagesTotal', 0),
                'message': 'Connexion Gmail établie',
            }
        except RuntimeError as e:
            return {'status': 'not_configured', 'error': str(e), 'provider': 'gmail'}
        except Exception as e:
            return {'status': 'error', 'error': str(e), 'provider': 'gmail'}

    # ── Récupération des CVs ──────────────────────────────────────────────────

    def fetch_new_cvs(
        self,
        already_processed_ids: set,
        max_messages: int = 50,
        **_kwargs,
    ) -> Iterator[EmailAttachment]:
        """
        Parcourt la boite Gmail et yield une EmailAttachment par pièce jointe CV trouvée.
        Ignore les messages déjà présents dans already_processed_ids.
        """
        service = self._get_service()

        # Requête Gmail : emails avec pièces jointes PDF/DOCX dans la boite de réception
        query = 'has:attachment (filename:pdf OR filename:docx OR filename:doc) in:inbox'

        try:
            result = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_messages,
            ).execute()
        except HttpError as e:
            logger.error("Erreur liste Gmail : %s", e)
            return

        messages = result.get('messages', [])
        logger.info("%d message(s) Gmail correspondant(s)", len(messages))

        for msg_meta in messages:
            msg_id = msg_meta['id']

            if msg_id in already_processed_ids:
                logger.debug("Ignoré (déjà traité) : %s", msg_id)
                continue

            try:
                msg = service.users().messages().get(
                    userId='me', id=msg_id, format='full',
                ).execute()
            except HttpError as e:
                logger.error("Impossible de lire le message %s : %s", msg_id, e)
                continue

            headers = {
                h['name'].lower(): h['value']
                for h in msg.get('payload', {}).get('headers', [])
            }

            sender_raw = headers.get('from', '')
            subject    = headers.get('subject', '(sans objet)')
            date_raw   = headers.get('date', '')

            sender_name, sender_email = _parse_sender(sender_raw)

            try:
                received_at = parsedate_to_datetime(date_raw).replace(tzinfo=None)
            except Exception:
                received_at = datetime.now()

            # Extraire toutes les pièces jointes CV
            found = list(_extract_attachments(
                service, msg_id, msg,
                sender_email, sender_name, subject, received_at,
            ))

            if not found:
                logger.debug("Aucun CV dans le message %s (%s)", msg_id, subject)

            for att in found:
                yield att


# ─── Helpers internes ──────────────────────────────────────────────────────────

def _parse_sender(raw: str) -> tuple[str, str]:
    """'Prénom Nom <email@exemple.com>' → ('Prénom Nom', 'email@exemple.com')"""
    raw = raw.strip()
    if '<' in raw and '>' in raw:
        name  = raw[:raw.index('<')].strip().strip('"')
        email = raw[raw.index('<') + 1: raw.index('>')].strip()
    else:
        name  = ''
        email = raw
    return name, email


def _extract_attachments(
    service,
    msg_id: str,
    msg: dict,
    sender_email: str,
    sender_name: str,
    subject: str,
    received_at: datetime,
) -> Iterator[EmailAttachment]:
    """Parcourt les parties MIME d'un message et yield les pièces jointes CV."""

    def _walk(parts):
        for part in parts:
            # Récursion sur les parties imbriquées (multipart/*)
            sub = part.get('parts')
            if sub:
                yield from _walk(sub)
                continue

            filename     = part.get('filename', '')
            content_type = part.get('mimeType', '')
            body         = part.get('body', {})
            att_id       = body.get('attachmentId')

            if not filename or not att_id:
                continue

            ext = os.path.splitext(filename.lower())[1]
            if ext not in ALLOWED_EXTENSIONS:
                continue

            try:
                att_data = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id,
                ).execute()
                raw_bytes = base64.urlsafe_b64decode(att_data['data'])
            except Exception as e:
                logger.error("Erreur téléchargement pièce jointe %s : %s", filename, e)
                continue

            yield EmailAttachment(
                filename=filename,
                content_type=content_type or MIME_MAP.get(ext, 'application/octet-stream'),
                content_bytes=raw_bytes,
                message_id=msg_id,
                sender_email=sender_email,
                sender_name=sender_name,
                subject=subject,
                received_at=received_at,
            )

    payload = msg.get('payload', {})
    parts   = payload.get('parts', [])

    if parts:
        yield from _walk(parts)
    else:
        # Message simple sans parties imbriquées
        yield from _walk([payload])
