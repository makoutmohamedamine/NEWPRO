"""
Connecteur Microsoft Graph API - Outlook Office 365
====================================================
Récupère automatiquement les emails contenant des CV (PDF/DOCX)
depuis une boite mail Outlook via l'API Microsoft Graph.

Flux d'authentification : Client Credentials (daemon app)
  Azure AD → access_token → Graph API → messages + pièces jointes
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Iterator

import msal
import requests

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

CV_KEYWORDS = [
    "cv", "curriculum", "resume", "candidature", "candidat",
    "application", "profil", "portfolio",
]


# ─── Structures de données ──────────────────────────────────────────────────────

@dataclass
class EmailAttachment:
    """Représente une pièce jointe CV extraite d'un email."""
    filename: str
    content_type: str
    content_bytes: bytes
    message_id: str
    sender_email: str
    sender_name: str
    subject: str
    received_at: str
    body_preview: str


@dataclass
class SyncResult:
    """Résultat d'une synchronisation Outlook."""
    fetched: int = 0
    processed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ─── Authentification MSAL ──────────────────────────────────────────────────────

class OutlookAuthenticator:
    """
    Gère l'authentification OAuth2 via MSAL.
    Utilise le flux Client Credentials (sans interaction utilisateur).
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._app: msal.ConfidentialClientApplication | None = None
        self._token: str | None = None

    def _build_app(self) -> msal.ConfidentialClientApplication:
        authority = f"https://login.microsoftonline.com/{self._tenant_id}"
        return msal.ConfidentialClientApplication(
            client_id=self._client_id,
            client_credential=self._client_secret,
            authority=authority,
        )

    def get_token(self) -> str:
        """Obtient ou renouvelle le token d'accès Microsoft Graph."""
        if self._app is None:
            self._app = self._build_app()

        scopes = ["https://graph.microsoft.com/.default"]
        result = self._app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in result:
            error = result.get("error_description", "Erreur inconnue MSAL")
            raise RuntimeError(f"Authentification Microsoft Graph échouée : {error}")

        return result["access_token"]

    def get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
        }


# ─── Client Graph API ───────────────────────────────────────────────────────────

class GraphMailClient:
    """
    Client pour l'API Microsoft Graph — lecture de la boite mail.
    Permissions requises (application) : Mail.Read, User.Read.All
    """

    def __init__(self, auth: OutlookAuthenticator, mailbox: str):
        self._auth = auth
        self._mailbox = mailbox  # ex: recrutement@entreprise.com

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        url = f"{GRAPH_BASE}{endpoint}"
        response = requests.get(
            url,
            headers=self._auth.get_headers(),
            params=params or {},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _patch(self, endpoint: str, body: dict) -> None:
        url = f"{GRAPH_BASE}{endpoint}"
        response = requests.patch(
            url,
            headers=self._auth.get_headers(),
            json=body,
            timeout=30,
        )
        response.raise_for_status()

    def list_unread_messages_with_attachments(
        self,
        folder: str = "inbox",
        max_results: int = 50,
    ) -> list[dict]:
        """
        Retourne les messages non lus ayant des pièces jointes.
        Filtre : hasAttachments eq true AND isRead eq false
        """
        endpoint = f"/users/{self._mailbox}/mailFolders/{folder}/messages"
        params = {
            "$filter": "hasAttachments eq true and isRead eq false",
            "$top": min(max_results, 50),
            "$select": "id,subject,from,receivedDateTime,bodyPreview,hasAttachments,isRead",
            "$orderby": "receivedDateTime desc",
        }
        data = self._get(endpoint, params)
        return data.get("value", [])

    def list_attachments(self, message_id: str) -> list[dict]:
        """Liste les pièces jointes d'un message."""
        endpoint = f"/users/{self._mailbox}/messages/{message_id}/attachments"
        params = {"$select": "id,name,contentType,size,contentBytes"}
        data = self._get(endpoint, params)
        return data.get("value", [])

    def get_attachment_bytes(self, message_id: str, attachment_id: str) -> bytes:
        """Télécharge le contenu binaire d'une pièce jointe."""
        endpoint = f"/users/{self._mailbox}/messages/{message_id}/attachments/{attachment_id}"
        data = self._get(endpoint)
        content_b64 = data.get("contentBytes", "")
        return base64.b64decode(content_b64) if content_b64 else b""

    def mark_as_read(self, message_id: str) -> None:
        """Marque un message comme lu après traitement."""
        endpoint = f"/users/{self._mailbox}/messages/{message_id}"
        self._patch(endpoint, {"isRead": True})

    def move_to_folder(self, message_id: str, destination_folder_id: str) -> None:
        """Déplace un message vers un dossier (ex: CVs-Traités)."""
        endpoint = f"/users/{self._mailbox}/messages/{message_id}/move"
        url = f"{GRAPH_BASE}{endpoint}"
        requests.post(
            url,
            headers=self._auth.get_headers(),
            json={"destinationId": destination_folder_id},
            timeout=30,
        ).raise_for_status()

    def get_or_create_folder(self, folder_name: str) -> str:
        """Retourne l'ID d'un dossier, le crée s'il n'existe pas."""
        endpoint = f"/users/{self._mailbox}/mailFolders"
        data = self._get(endpoint)
        for folder in data.get("value", []):
            if folder.get("displayName", "").lower() == folder_name.lower():
                return folder["id"]

        # Créer le dossier
        url = f"{GRAPH_BASE}{endpoint}"
        response = requests.post(
            url,
            headers=self._auth.get_headers(),
            json={"displayName": folder_name},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["id"]


# ─── Détection intelligente des CVs ────────────────────────────────────────────

def _is_cv_attachment(filename: str, content_type: str, subject: str) -> bool:
    """
    Heuristique pour détecter si une pièce jointe est un CV.
    Critères : extension valide + (nom de fichier OU sujet contient un mot-clé CV).
    """
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False

    if content_type.lower() not in ALLOWED_CONTENT_TYPES and content_type != "":
        # Certains serveurs envoient application/octet-stream — on accepte si extension valide
        if content_type.lower() not in {"application/octet-stream", ""}:
            return False

    filename_lower = filename.lower()
    subject_lower = subject.lower()
    combined = filename_lower + " " + subject_lower

    # Toujours accepter si le nom de fichier ou le sujet contient un mot-clé
    if any(kw in combined for kw in CV_KEYWORDS):
        return True

    # Accepter également les fichiers PDF/DOCX même sans mot-clé
    # (cas où le candidat n'a pas nommé son fichier "cv_...")
    return ext in {".pdf", ".docx"}


# ─── Extracteur principal ───────────────────────────────────────────────────────

class OutlookCVExtractor:
    """
    Orchestre la connexion Outlook, la récupération et le filtrage des CVs.
    Usage :
        extractor = OutlookCVExtractor.from_env()
        for attachment in extractor.fetch_new_cvs():
            # traiter la pièce jointe
    """

    PROCESSED_FOLDER = "CVs-Traités"

    def __init__(self, auth: OutlookAuthenticator, mailbox: str):
        self._auth = auth
        self._client = GraphMailClient(auth, mailbox)

    @classmethod
    def from_env(cls) -> "OutlookCVExtractor":
        """Instancie depuis les variables d'environnement."""
        tenant_id = os.environ["AZURE_TENANT_ID"]
        client_id = os.environ["AZURE_CLIENT_ID"]
        client_secret = os.environ["AZURE_CLIENT_SECRET"]
        mailbox = os.environ["OUTLOOK_MAILBOX"]

        auth = OutlookAuthenticator(tenant_id, client_id, client_secret)
        return cls(auth, mailbox)

    def fetch_new_cvs(
        self,
        already_processed_ids: set[str] | None = None,
        max_messages: int = 50,
        mark_as_read: bool = True,
        move_to_processed: bool = True,
    ) -> Iterator[EmailAttachment]:
        """
        Générateur qui yield chaque pièce jointe CV trouvée dans les emails non lus.

        Args:
            already_processed_ids : IDs de messages déjà traités (évite les doublons).
            max_messages          : Nombre maximum de messages à analyser.
            mark_as_read          : Marque le message comme lu après traitement.
            move_to_processed     : Déplace le message dans le dossier CVs-Traités.
        """
        already_processed_ids = already_processed_ids or set()
        processed_folder_id: str | None = None

        try:
            messages = self._client.list_unread_messages_with_attachments(
                max_results=max_messages
            )
        except Exception as exc:
            logger.error("Impossible de récupérer les messages Outlook : %s", exc)
            return

        for message in messages:
            msg_id = message["id"]

            if msg_id in already_processed_ids:
                logger.debug("Message %s déjà traité, ignoré.", msg_id)
                continue

            sender = message.get("from", {}).get("emailAddress", {})
            sender_email = sender.get("address", "")
            sender_name = sender.get("name", "")
            subject = message.get("subject", "")
            received_at = message.get("receivedDateTime", "")
            body_preview = message.get("bodyPreview", "")

            found_cv = False
            try:
                attachments = self._client.list_attachments(msg_id)
            except Exception as exc:
                logger.warning("Erreur lors de la récupération des pièces jointes %s : %s", msg_id, exc)
                continue

            for att in attachments:
                att_id = att.get("id", "")
                filename = att.get("name", "")
                content_type = att.get("contentType", "")

                if not _is_cv_attachment(filename, content_type, subject):
                    continue

                try:
                    content_bytes = self._client.get_attachment_bytes(msg_id, att_id)
                except Exception as exc:
                    logger.warning("Erreur téléchargement pièce jointe %s : %s", att_id, exc)
                    continue

                if not content_bytes:
                    continue

                found_cv = True
                logger.info(
                    "CV détecté : '%s' de %s <%s> (message %s)",
                    filename, sender_name, sender_email, msg_id,
                )
                yield EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    content_bytes=content_bytes,
                    message_id=msg_id,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=subject,
                    received_at=received_at,
                    body_preview=body_preview,
                )

            # Post-traitement du message
            if found_cv:
                try:
                    if mark_as_read:
                        self._client.mark_as_read(msg_id)
                    if move_to_processed:
                        if processed_folder_id is None:
                            processed_folder_id = self._client.get_or_create_folder(
                                self.PROCESSED_FOLDER
                            )
                        self._client.move_to_folder(msg_id, processed_folder_id)
                except Exception as exc:
                    logger.warning("Erreur post-traitement message %s : %s", msg_id, exc)

    def test_connection(self) -> dict:
        """Teste la connexion à Microsoft Graph et retourne un rapport."""
        try:
            token = self._auth.get_token()
            messages = self._client.list_unread_messages_with_attachments(max_results=1)
            return {
                "status": "ok",
                "token_acquired": True,
                "mailbox": self._client._mailbox,
                "unread_with_attachments_sample": len(messages),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "token_acquired": False,
            }
