import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, 'C:\\Users\\STG IT2\\Desktop\\NEWPRO\\backend')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Vérifier les utilisateurs existants
users = User.objects.all()
print(f'✅ Utilisateurs existants: {users.count()}')
for u in users:
    print(f'   - {u.username} | Email: {u.email} | Rôle: {u.role}')

# Créer ou mettre à jour le compte de test
username = 'Amine'
password = '123456789'
email = 'amine@example.com'

try:
    user = User.objects.get(username=username)
    print(f'\n⚠️  Utilisateur "{username}" existe déjà')
    print(f'   - Email: {user.email}')
    print(f'   - Rôle: {user.role}')
    print(f'   - Actif: {user.is_active}')
except User.DoesNotExist:
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name='Amine',
        role='recruteur'
    )
    print(f'\n✅ Nouvel utilisateur créé: {username}')
    print(f'   - Email: {email}')
    print(f'   - Mot de passe: {password}')
    print(f'   - Rôle: recruteur')

print(f'\n🔓 Essayez maintenant:')
print(f'   Username: {username}')
print(f'   Password: {password}')
