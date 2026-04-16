"""
Commande Django pour autoriser l'accès Gmail (OAuth2).

Usage :
    python manage.py gmail_auth

Cette commande ouvre un navigateur pour que vous autorisiez l'accès Gmail.
Le token est ensuite sauvegardé dans token.json (valide 1 an, auto-renouvelé).
À n'exécuter qu'une seule fois.
"""
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Autorise l'accès Gmail via OAuth2 et sauvegarde le token."

    def add_arguments(self, parser):
        parser.add_argument(
            '--credentials',
            type=str,
            default=None,
            help='Chemin vers client_secret.json (défaut : backend/client_secret.json)',
        )
        parser.add_argument(
            '--token',
            type=str,
            default=None,
            help='Chemin où sauvegarder token.json (défaut : backend/token.json)',
        )

    def handle(self, *args, **options):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "Packages Google manquants. Installez-les avec :\n"
                "  pip install google-auth google-auth-oauthlib google-api-python-client"
            ))
            return

        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        credentials_file = options['credentials'] or os.environ.get(
            'GMAIL_CLIENT_SECRET_FILE',
            os.path.join(backend_dir, 'client_secret.json'),
        )
        token_file = options['token'] or os.environ.get(
            'GMAIL_TOKEN_FILE',
            os.path.join(backend_dir, 'token.json'),
        )

        if not os.path.exists(credentials_file):
            self.stdout.write(self.style.ERROR(
                f"\nFichier client_secret.json introuvable : {credentials_file}\n"
                "Téléchargez-le depuis https://console.cloud.google.com/ "
                "(APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON)\n"
                "et placez-le dans le dossier backend/."
            ))
            return

        self.stdout.write("\nAutorisation Gmail en cours…")
        self.stdout.write(f"  Credentials : {credentials_file}")
        self.stdout.write(f"  Token cible  : {token_file}\n")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur OAuth2 : {e}"))
            return

        # Sauvegarder le token
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

        # Vérifier en lisant le profil Gmail
        try:
            service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            profile = service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress', 'inconnue')
            self.stdout.write(self.style.SUCCESS(
                f"\nAutorisation réussie !\n"
                f"  Boite Gmail : {email}\n"
                f"  Token sauvegardé dans : {token_file}\n\n"
                "L'application peut maintenant lire vos emails Gmail pour importer les CVs.\n"
                "Lancez la synchronisation depuis l'interface ou via POST /api/gmail/sync/\n"
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f"Token sauvegardé mais impossible de lire le profil : {e}"
            ))
