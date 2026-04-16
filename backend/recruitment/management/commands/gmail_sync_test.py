"""
Commande Django pour tester et déclencher la synchronisation Gmail.

Usage :
    python manage.py gmail_sync_test             # Diagnostic complet
    python manage.py gmail_sync_test --run       # Lance la synchro réelle
    python manage.py gmail_sync_test --list 10   # Liste les 10 prochains emails CV
"""
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Teste la connexion Gmail et diagnostique la collecte de CVs."

    def add_arguments(self, parser):
        parser.add_argument('--run',  action='store_true', help='Lance la synchro réelle')
        parser.add_argument('--list', type=int, default=5,  metavar='N', help='Nombre d\'emails à lister')

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  DIAGNOSTIC GMAIL SYNC")
        self.stdout.write("=" * 60 + "\n")

        # ── 1. Vérifier les fichiers ───────────────────────────────────────────
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        secret_file = os.environ.get(
            'GMAIL_CLIENT_SECRET_FILE',
            os.path.join(backend_dir, 'client_secret.json'),
        )
        token_file = os.environ.get(
            'GMAIL_TOKEN_FILE',
            os.path.join(backend_dir, 'token.json'),
        )

        self.stdout.write(f"[1] Fichiers de configuration")
        self.stdout.write(f"    client_secret : {secret_file}")
        self.stdout.write(f"    token         : {token_file}")

        if not os.path.exists(secret_file):
            self.stdout.write(self.style.ERROR(
                f"\n    ERREUR : client_secret.json introuvable !\n"
                f"    Téléchargez-le depuis Google Cloud Console."
            ))
            return

        self.stdout.write(self.style.SUCCESS("    client_secret.json : OK"))

        if not os.path.exists(token_file):
            self.stdout.write(self.style.ERROR(
                "\n    ERREUR : token.json introuvable !\n"
                "    Lancez : python manage.py gmail_auth"
            ))
            return

        self.stdout.write(self.style.SUCCESS("    token.json : OK"))

        # ── 2. Tester la connexion ─────────────────────────────────────────────
        self.stdout.write(f"\n[2] Test de connexion Gmail")
        try:
            from recruitment.gmail_connector import GmailCVConnector
            connector = GmailCVConnector.from_env()
            conn = connector.test_connection()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERREUR import : {e}"))
            return

        if conn['status'] != 'ok':
            self.stdout.write(self.style.ERROR(f"    ECHEC : {conn.get('error')}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"    Connecté à : {conn['mailbox']}\n"
            f"    Emails total : {conn.get('messagesTotal', '?')}"
        ))

        # ── 3. Lister les emails CV trouvés ───────────────────────────────────
        n = options['list']
        self.stdout.write(f"\n[3] Recherche d'emails avec pièces jointes CV (max {n})")

        try:
            service = connector._get_service()
            query = 'has:attachment (filename:pdf OR filename:docx OR filename:doc) in:inbox'
            self.stdout.write(f"    Requête : {query}")

            result = service.users().messages().list(
                userId='me', q=query, maxResults=n,
            ).execute()
            messages = result.get('messages', [])
            total = result.get('resultSizeEstimate', 0)

            self.stdout.write(f"    Résultats estimés : {total}")
            self.stdout.write(f"    Messages récupérés : {len(messages)}")

            if not messages:
                self.stdout.write(self.style.WARNING(
                    "\n    AUCUN EMAIL TROUVÉ avec la requête.\n"
                    "    Assurez-vous que votre Gmail contient des emails\n"
                    "    non lus avec des pièces jointes PDF ou DOCX dans INBOX."
                ))
            else:
                self.stdout.write("\n    Emails trouvés :")
                for msg_meta in messages:
                    msg = service.users().messages().get(
                        userId='me', id=msg_meta['id'], format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date'],
                    ).execute()
                    headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
                    self.stdout.write(
                        f"    - [{msg_meta['id'][:12]}] "
                        f"De: {headers.get('from', '?')[:40]} | "
                        f"Sujet: {headers.get('subject', '?')[:40]}"
                    )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ERREUR : {e}"))
            return

        # ── 4. IDs déjà traités ────────────────────────────────────────────────
        try:
            from recruitment.models import EmailLog
            already = EmailLog.objects.count()
            self.stdout.write(f"\n[4] Emails déjà traités en base : {already}")
        except Exception as e:
            self.stdout.write(f"    (impossible de lire EmailLog : {e})")

        # ── 5. Lancer la synchro si --run ──────────────────────────────────────
        if options['run']:
            self.stdout.write(f"\n[5] Lancement de la synchronisation…")
            try:
                from recruitment.gmail_pipeline import get_gmail_pipeline
                pipeline = get_gmail_pipeline()
                report = pipeline.run()

                self.stdout.write(self.style.SUCCESS(
                    f"\n    Terminé !\n"
                    f"    Emails scannés : {report.emails_scanned}\n"
                    f"    CVs trouvés    : {report.cvs_found}\n"
                    f"    CVs créés      : {report.cvs_created}\n"
                    f"    Doublons       : {report.cvs_duplicate}\n"
                    f"    Erreurs        : {report.cvs_error}"
                ))
                if report.errors:
                    self.stdout.write(self.style.ERROR("\n    Erreurs détaillées :"))
                    for e in report.errors:
                        self.stdout.write(f"    - {e}")
            except Exception as e:
                import traceback
                self.stdout.write(self.style.ERROR(f"\n    ERREUR pipeline : {e}"))
                self.stdout.write(traceback.format_exc())
        else:
            self.stdout.write(
                "\n[5] Pour lancer la synchro réelle :\n"
                "    python manage.py gmail_sync_test --run\n"
            )

        self.stdout.write("=" * 60 + "\n")
