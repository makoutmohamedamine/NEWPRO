"""
Commande Django pour créer ou promouvoir un compte administrateur.

Usage :
    python manage.py create_admin
    python manage.py create_admin --username=admin --email=admin@example.com --password=secret123
    python manage.py create_admin --username=existinguser --promote
    python manage.py list_admins
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crée ou promeut un compte administrateur du système."

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Nom d\'utilisateur (défaut: admin)')
        parser.add_argument('--email', type=str, default='admin@recrutement.com', help='Email de l\'admin')
        parser.add_argument('--password', type=str, default=None, help='Mot de passe (si vide, sera demandé)')
        parser.add_argument('--first-name', type=str, default='Super', dest='first_name')
        parser.add_argument('--last-name', type=str, default='Admin', dest='last_name')
        parser.add_argument(
            '--promote',
            action='store_true',
            default=False,
            help='Si l\'utilisateur existe déjà, le promouvoir au rôle admin.',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            default=False,
            help='Lister tous les utilisateurs existants et leurs rôles.',
        )

    def handle(self, *args, **options):
        # ── Mode liste ────────────────────────────────────────────────────────
        if options['list']:
            users = User.objects.all().order_by('username')
            if not users.exists():
                self.stdout.write(self.style.WARNING('Aucun utilisateur en base.'))
                return
            self.stdout.write('\nUtilisateurs en base :')
            self.stdout.write('-' * 55)
            for u in users:
                status = 'actif' if u.is_active else 'désactivé'
                self.stdout.write(
                    f'  {u.username:<20} rôle={u.role:<10} {status}'
                )
            self.stdout.write('-' * 55)
            return

        username = options['username']
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        promote = options['promote']

        # ── Promouvoir un utilisateur existant ────────────────────────────────
        existing = User.objects.filter(username=username).first()
        if existing:
            if promote:
                existing.role = 'admin'
                existing.is_staff = True
                existing.is_superuser = True
                existing.is_active = True
                existing.save()
                self.stdout.write(self.style.SUCCESS(
                    f'\nUtilisateur "{existing.username}" promu administrateur !\n'
                    f'   Email  : {existing.email}\n'
                    f'   Rôle   : {existing.role}\n'
                    f'\nReconnectez-vous pour voir les changements.\n'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  L\'utilisateur "{username}" existe déjà (rôle: {existing.role}).\n'
                    f'   Pour le promouvoir admin, ajoutez --promote :\n'
                    f'   python manage.py create_admin --username={username} --promote\n'
                ))
            return

        # ── Créer un nouvel admin ─────────────────────────────────────────────
        if not password:
            import getpass
            self.stdout.write('Entrez le mot de passe pour l\'administrateur :')
            password = getpass.getpass('Mot de passe : ')
            password_confirm = getpass.getpass('Confirmer le mot de passe : ')
            if password != password_confirm:
                self.stdout.write(self.style.ERROR('❌ Les mots de passe ne correspondent pas.'))
                return
            if len(password) < 6:
                self.stdout.write(self.style.ERROR('❌ Le mot de passe doit faire au moins 6 caractères.'))
                return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='admin',
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nCompte administrateur créé avec succès !\n'
            f'   Nom d\'utilisateur : {user.username}\n'
            f'   Email             : {user.email}\n'
            f'   Rôle              : {user.role}\n'
            f'\nConnectez-vous via l\'interface ou POST /api/auth/login/\n'
        ))
