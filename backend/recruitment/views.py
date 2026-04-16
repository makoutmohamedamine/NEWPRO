from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q, Avg, Max
from .models import Candidat, CV, Candidature, Poste, EmailLog, SyncHistory
from .serializers import (
    CandidatSerializer, CVSerializer, CandidatureSerializer, PosteSerializer,
    UserSerializer, CreateUserSerializer,
)
from .ai_engine import analyser_cv

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Permission helper
# ─────────────────────────────────────────────────────────────────────────────

def is_admin(user):
    """Retourne True si l'utilisateur connecté a le rôle admin."""
    return user.is_authenticated and user.role == 'admin'


# ─────────────────────────────────────────────────────────────────────────────
# Authentification
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_setup(request):
    """
    Vérifie si un administrateur existe déjà dans le système.
    Retourne needs_setup=True si aucun admin n'existe.
    """
    has_admin = User.objects.filter(role='admin').exists()
    return Response({'needs_setup': not has_admin})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def setup_superuser(request):
    """
    Crée le premier compte administrateur (superuser).
    Bloqué si un admin existe déjà.
    Body: { "username", "email", "password", "first_name", "last_name" }
    """
    if User.objects.filter(role='admin').exists():
        return Response({'error': 'Un administrateur existe déjà. Cette opération est réservée à l\'initialisation.'}, status=403)

    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()

    if not username:
        return Response({'error': 'Le nom d\'utilisateur est requis.'}, status=400)
    if not email:
        return Response({'error': 'L\'email est requis.'}, status=400)
    if not password or len(password) < 6:
        return Response({'error': 'Le mot de passe doit faire au moins 6 caractères.'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'error': f'Le nom d\'utilisateur "{username}" est déjà pris.'}, status=400)

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

    refresh = RefreshToken.for_user(user)
    return Response({
        'message': f'Compte administrateur "{user.username}" créé avec succès.',
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }, status=201)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    Connexion : retourne les tokens JWT + les infos de l'utilisateur.
    Body: { "username": "...", "password": "..." }
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    if not username or not password:
        return Response({'error': 'Nom d\'utilisateur et mot de passe requis.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': 'Identifiants incorrects.'}, status=401)

    if not user.is_active:
        return Response({'error': 'Ce compte est désactivé.'}, status=403)

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Déconnexion : invalide le refresh token.
    Body: { "refresh": "..." }
    """
    try:
        refresh_token = request.data.get('refresh')
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Déconnexion réussie.'})
    except Exception:
        return Response({'message': 'Déconnexion effectuée.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Retourne les informations de l'utilisateur actuellement connecté."""
    return Response({'user': UserSerializer(request.user).data})


# ─────────────────────────────────────────────────────────────────────────────
# Gestion des utilisateurs (admin uniquement)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_list(request):
    """Liste tous les utilisateurs. Réservé aux admins."""
    if not is_admin(request.user):
        return Response({'error': 'Accès refusé. Réservé aux administrateurs.'}, status=403)
    users = User.objects.all().order_by('-date_joined')
    return Response({'users': UserSerializer(users, many=True).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_create(request):
    """
    Crée un nouveau compte utilisateur. Réservé aux admins.
    Body: { "username", "email", "first_name", "last_name", "role", "password" }
    """
    if not is_admin(request.user):
        return Response({'error': 'Accès refusé. Réservé aux administrateurs.'}, status=403)

    serializer = CreateUserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': f'Compte "{user.username}" créé avec succès.',
            'user': UserSerializer(user).data,
        }, status=201)
    return Response({'errors': serializer.errors}, status=400)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_detail(request, pk):
    """
    GET  — Voir un utilisateur.
    PUT/PATCH — Modifier un utilisateur (admin uniquement).
    """
    if not is_admin(request.user):
        return Response({'error': 'Accès refusé. Réservé aux administrateurs.'}, status=403)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur non trouvé.'}, status=404)

    if request.method == 'GET':
        return Response({'user': UserSerializer(user).data})

    # PUT / PATCH
    partial = request.method == 'PATCH'
    serializer = CreateUserSerializer(user, data=request.data, partial=partial)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Utilisateur mis à jour.',
            'user': UserSerializer(user).data,
        })
    return Response({'errors': serializer.errors}, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def user_delete(request, pk):
    """Supprime un utilisateur. Réservé aux admins. Un admin ne peut pas se supprimer lui-même."""
    if not is_admin(request.user):
        return Response({'error': 'Accès refusé. Réservé aux administrateurs.'}, status=403)
    if request.user.pk == pk:
        return Response({'error': 'Vous ne pouvez pas supprimer votre propre compte.'}, status=400)
    try:
        user = User.objects.get(pk=pk)
        username = user.username
        user.delete()
        return Response({'message': f'Compte "{username}" supprimé.'})
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur non trouvé.'}, status=404)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def user_toggle_active(request, pk):
    """Active ou désactive un compte utilisateur. Réservé aux admins."""
    if not is_admin(request.user):
        return Response({'error': 'Accès refusé. Réservé aux administrateurs.'}, status=403)
    if request.user.pk == pk:
        return Response({'error': 'Vous ne pouvez pas désactiver votre propre compte.'}, status=400)
    try:
        user = User.objects.get(pk=pk)
        user.is_active = not user.is_active
        user.save()
        status_label = 'activé' if user.is_active else 'désactivé'
        return Response({
            'message': f'Compte "{user.username}" {status_label}.',
            'user': UserSerializer(user).data,
        })
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur non trouvé.'}, status=404)


def format_candidate(candidat):
    candidature = candidat.candidatures.first()
    cv = candidat.cvs.first()
    return {
        'id': candidat.id,
        'fullName': f"{candidat.prenom} {candidat.nom}",
        'email': candidat.email,
        'phone': candidat.telephone,
        'profileLabel': candidature.poste.titre if candidature and candidature.poste else 'Non classé',
        'matchScore': candidature.score or 0.0 if candidature else 0.0,
        'status': candidature.statut if candidature else 'nouveau',
        'educationLevel': 'Non détecté',
        'yearsExperience': 0,
        'summary': cv.texte_extrait[:200] if cv and cv.texte_extrait else '',
        'skills': [],
        'notes': '',
        'source': 'manual',
        'sourceEmail': cv.email_source if cv else '',
        'cvUrl': cv.fichier.url if cv and cv.fichier else None,
        'cvFileName': cv.fichier.name.split('/')[-1] if cv and cv.fichier else None,
        'targetJob': candidature.poste.titre if candidature and candidature.poste else '',
        'createdAt': str(candidat.created_at),
    }


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def dashboard(request):
    try:
        q = request.GET.get('q', '')
        status = request.GET.get('status', '')
        profile = request.GET.get('profile', '')
        sort = request.GET.get('sort', '-created_at')

        candidats = Candidat.objects.all()

        if q:
            candidats = candidats.filter(
                Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(email__icontains=q)
            )
        if status:
            candidats = candidats.filter(candidatures__statut=status)

        all_candidatures = Candidature.objects.all()
        scores = [c.score for c in all_candidatures if c.score is not None]

        # Répartition par profil
        profile_dist = {}
        for c in all_candidatures:
            if c.poste:
                label = c.poste.titre
                profile_dist[label] = profile_dist.get(label, 0) + 1

        # Top candidats
        top = all_candidatures.filter(score__isnull=False).order_by('-score')[:5]
        top_candidates = [{
            'id': c.candidat.id,
            'fullName': f"{c.candidat.prenom} {c.candidat.nom}",
            'profileLabel': c.poste.titre if c.poste else '',
            'matchScore': c.score or 0,
        } for c in top]

        # Postes disponibles
        postes = Poste.objects.all()
        job_profiles = [{'id': p.id, 'name': p.titre} for p in postes]

        # Statuts disponibles
        statuses = [
            {'value': 'nouveau', 'label': 'Nouveau'},
            {'value': 'en_cours', 'label': 'En cours'},
            {'value': 'accepte', 'label': 'Accepté'},
            {'value': 'refuse', 'label': 'Refusé'},
        ]

        profiles = list(profile_dist.keys())
        candidates_list = [format_candidate(c) for c in candidats]

        # Tri
        if sort == '-match_score':
            candidates_list.sort(key=lambda x: x['matchScore'], reverse=True)
        elif sort == 'full_name':
            candidates_list.sort(key=lambda x: x['fullName'])
        elif sort == '-created_at':
            candidates_list.sort(key=lambda x: x['createdAt'], reverse=True)

        return Response({
            'stats': {
                'totalCandidates': Candidat.objects.count(),
                'averageScore': round(sum(scores) / len(scores), 1) if scores else 0,
                'bestScore': round(max(scores), 1) if scores else 0,
                'newCandidates': all_candidatures.filter(statut='nouveau').count(),
            },
            'candidates': candidates_list,
            'topCandidates': top_candidates,
            'profileDistribution': profile_dist,
            'jobProfiles': job_profiles,
            'filters': {
                'statuses': statuses,
                'profiles': profiles,
            },
        })
    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def candidate_detail(request, pk):
    try:
        candidat = Candidat.objects.get(pk=pk)
        return Response({'candidate': format_candidate(candidat)})
    except Candidat.DoesNotExist:
        return Response({'error': 'Candidat non trouvé'}, status=404)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def candidate_upload(request):
    try:
        cv_file = request.FILES.get('cv')
        source = request.POST.get('source', 'manual')
        source_email = request.POST.get('sourceEmail', '')
        target_job_id = request.POST.get('targetJobId', '')

        if not cv_file:
            return Response({'error': 'Aucun fichier CV fourni'}, status=400)

        # Détecter le format
        filename = cv_file.name.lower()
        if filename.endswith('.pdf'):
            format_f = 'pdf'
        elif filename.endswith('.docx'):
            format_f = 'docx'
        else:
            format_f = 'pdf'

        # Créer candidat temporaire
        candidat = Candidat.objects.create(
            nom='Inconnu',
            prenom='Candidat',
            email=source_email or f"candidat_{Candidat.objects.count() + 1}@unknown.com",
        )

        # Sauvegarder CV
        cv = CV.objects.create(
            candidat=candidat,
            fichier=cv_file,
            format_fichier=format_f,
            email_source=source_email,
        )

        # Analyser
        resultat = analyser_cv(cv.fichier.path, format_f)
        cv.texte_extrait = resultat.get('texte_extrait', '')
        cv.save()

        # Mettre à jour candidat avec infos extraites
        if resultat.get('email'):
            candidat.email = resultat['email']
        if resultat.get('telephone'):
            candidat.telephone = resultat['telephone']
        candidat.save()

        # Créer candidature si poste cible
        if target_job_id:
            try:
                poste = Poste.objects.get(pk=target_job_id)
                from .ai_engine import calculer_score
                score = calculer_score(cv.texte_extrait, poste.description)
                Candidature.objects.create(
                    candidat=candidat,
                    poste=poste,
                    cv=cv,
                    score=score,
                    statut='nouveau',
                )
            except Poste.DoesNotExist:
                pass

        return Response({'candidate': format_candidate(candidat)})

    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['PATCH'])
@authentication_classes([])
@permission_classes([AllowAny])
def candidate_update(request, pk):
    try:
        candidat = Candidat.objects.get(pk=pk)
        candidature = candidat.candidatures.first()

        if candidature:
            status = request.data.get('status')
            if status:
                candidature.statut = status
                candidature.save()

        return Response({'candidate': format_candidate(candidat)})
    except Candidat.DoesNotExist:
        return Response({'error': 'Candidat non trouvé'}, status=404)


class PosteViewSet(viewsets.ModelViewSet):
    queryset = Poste.objects.all()
    serializer_class = PosteSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


class CandidatViewSet(viewsets.ModelViewSet):
    queryset = Candidat.objects.all()
    serializer_class = CandidatSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


class CVViewSet(viewsets.ModelViewSet):
    queryset = CV.objects.all()
    serializer_class = CVSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


class CandidatureViewSet(viewsets.ModelViewSet):
    queryset = Candidature.objects.all()
    serializer_class = CandidatureSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


# ─── Endpoints Outlook / Pipeline ML ───────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_debug(request):
    """
    Diagnostic complet de la connexion Gmail.
    GET /api/gmail/debug/
    """
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secret_file = os.environ.get('GMAIL_CLIENT_SECRET_FILE', os.path.join(backend_dir, 'client_secret.json'))
    token_file  = os.environ.get('GMAIL_TOKEN_FILE',          os.path.join(backend_dir, 'token.json'))

    info = {
        'secret_file_exists': os.path.exists(secret_file),
        'token_file_exists':  os.path.exists(token_file),
        'secret_file_path':   secret_file,
        'token_file_path':    token_file,
        'connection': None,
        'emails_found': 0,
        'already_processed': 0,
        'sample_emails': [],
        'error': None,
    }

    if not info['token_file_exists']:
        info['error'] = "token.json manquant. Lancez : python manage.py gmail_auth"
        return Response(info)

    try:
        from .gmail_connector import GmailCVConnector
        connector = GmailCVConnector.from_env()
        info['connection'] = connector.test_connection()

        if info['connection']['status'] == 'ok':
            service = connector._get_service()
            query = 'has:attachment (filename:pdf OR filename:docx OR filename:doc) in:inbox'
            result = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
            messages = result.get('messages', [])
            info['emails_found'] = result.get('resultSizeEstimate', len(messages))

            for msg_meta in messages[:5]:
                msg = service.users().messages().get(
                    userId='me', id=msg_meta['id'], format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date'],
                ).execute()
                headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
                info['sample_emails'].append({
                    'id': msg_meta['id'],
                    'from': headers.get('from', ''),
                    'subject': headers.get('subject', ''),
                    'date': headers.get('date', ''),
                })

        from .models import EmailLog
        info['already_processed'] = EmailLog.objects.count()

    except Exception as e:
        import traceback
        info['error'] = str(e)
        info['traceback'] = traceback.format_exc()

    return Response(info)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_sync(request):
    """
    Déclenche la synchronisation Gmail → ML → DB.
    POST /api/gmail/sync/
    """
    import json
    from datetime import datetime
    from .gmail_pipeline import get_gmail_pipeline

    try:
        pipeline = get_gmail_pipeline()
        report = pipeline.run()

        SyncHistory.objects.create(
            started_at=datetime.fromisoformat(report.started_at) if report.started_at else datetime.now(),
            finished_at=datetime.fromisoformat(report.finished_at) if report.finished_at else datetime.now(),
            emails_scanned=report.emails_scanned,
            cvs_found=report.cvs_found,
            cvs_created=report.cvs_created,
            cvs_duplicate=report.cvs_duplicate,
            cvs_error=report.cvs_error,
            triggered_by=request.data.get('triggeredBy', 'manual'),
            errors_json=json.dumps(report.errors, ensure_ascii=False),
        )

        return Response(report.to_dict())

    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_status(request):
    """
    Statut de la connexion Gmail + historique des synchros.
    GET /api/gmail/status/
    """
    from .gmail_pipeline import get_gmail_pipeline

    pipeline = get_gmail_pipeline()
    connection = pipeline.test_connection()

    last_syncs = SyncHistory.objects.order_by('-started_at')[:5]
    history = [{
        'startedAt': str(s.started_at),
        'finishedAt': str(s.finished_at),
        'emailsScanned': s.emails_scanned,
        'cvsCreated': s.cvs_created,
        'cvsError': s.cvs_error,
        'triggeredBy': s.triggered_by,
    } for s in last_syncs]

    logs = EmailLog.objects.select_related('candidat').order_by('-created_at')[:20]
    email_logs = [{
        'messageId': l.message_id[:16] + '…',
        'senderEmail': l.sender_email,
        'senderName': l.sender_name,
        'subject': l.subject[:80],
        'filename': l.filename,
        'status': l.status,
        'errorMessage': l.error_message[:200] if l.error_message else '',
        'candidatId': l.candidat_id,
        'candidatName': f"{l.candidat.prenom} {l.candidat.nom}" if l.candidat else None,
        'createdAt': str(l.created_at),
    } for l in logs]

    return Response({
        'connection': connection,
        'syncHistory': history,
        'emailLogs': email_logs,
        'totalEmailsProcessed': EmailLog.objects.count(),
        'totalSyncs': SyncHistory.objects.count(),
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def outlook_sync(request):
    """
    Déclenche manuellement le pipeline de synchronisation Outlook.
    Lance la récupération des emails, l'analyse ML et la sauvegarde en DB.
    """
    import json
    from datetime import datetime
    from .pipeline import get_pipeline

    try:
        pipeline = get_pipeline()
        report = pipeline.run()

        # Sauvegarder l'historique
        SyncHistory.objects.create(
            started_at=datetime.fromisoformat(report.started_at) if report.started_at else datetime.now(),
            finished_at=datetime.fromisoformat(report.finished_at) if report.finished_at else datetime.now(),
            emails_scanned=report.emails_scanned,
            cvs_found=report.cvs_found,
            cvs_created=report.cvs_created,
            cvs_duplicate=report.cvs_duplicate,
            cvs_error=report.cvs_error,
            triggered_by=request.data.get('triggeredBy', 'manual'),
            errors_json=json.dumps(report.errors, ensure_ascii=False),
        )

        return Response(report.to_dict())

    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def outlook_status(request):
    """
    Retourne le statut de la connexion Outlook et les statistiques de synchro.
    """
    from .pipeline import get_pipeline

    pipeline = get_pipeline()
    connection = pipeline.test_connection()

    # Dernières synchros
    last_syncs = SyncHistory.objects.order_by('-started_at')[:5]
    history = [{
        'startedAt': str(s.started_at),
        'finishedAt': str(s.finished_at),
        'emailsScanned': s.emails_scanned,
        'cvsCreated': s.cvs_created,
        'cvsError': s.cvs_error,
        'triggeredBy': s.triggered_by,
    } for s in last_syncs]

    # Logs des 20 derniers emails traités
    logs = EmailLog.objects.select_related('candidat').order_by('-created_at')[:20]
    email_logs = [{
        'messageId': l.message_id[:16] + '…',
        'senderEmail': l.sender_email,
        'senderName': l.sender_name,
        'subject': l.subject[:80],
        'filename': l.filename,
        'status': l.status,
        'errorMessage': l.error_message[:200] if l.error_message else '',
        'candidatId': l.candidat_id,
        'candidatName': f"{l.candidat.prenom} {l.candidat.nom}" if l.candidat else None,
        'createdAt': str(l.created_at),
    } for l in logs]

    return Response({
        'connection': connection,
        'syncHistory': history,
        'emailLogs': email_logs,
        'totalEmailsProcessed': EmailLog.objects.count(),
        'totalSyncs': SyncHistory.objects.count(),
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def dossiers(request):
    """
    Retourne les postes avec leurs candidatures groupées.
    Chaque "dossier" = un domaine/poste contenant ses CVs.
    """
    try:
        postes = Poste.objects.all()
        result = []
        for poste in postes:
            candidatures = Candidature.objects.filter(poste=poste).select_related('candidat', 'cv')
            scores = [c.score for c in candidatures if c.score is not None]
            cvs = []
            for c in candidatures.order_by('-score'):
                cv = c.cv
                # Détecter si le CV vient d'Outlook (email_source renseigné)
                source = 'outlook' if (cv and cv.email_source) else 'manual'
                cvs.append({
                    'candidatureId': c.id,
                    'candidatId': c.candidat.id,
                    'fullName': f"{c.candidat.prenom} {c.candidat.nom}",
                    'email': c.candidat.email,
                    'phone': c.candidat.telephone,
                    'score': c.score or 0,
                    'statut': c.statut,
                    'source': source,
                    'sourceEmail': cv.email_source if cv else '',
                    'cvUrl': cv.fichier.url if cv and cv.fichier else None,
                    'cvFileName': cv.fichier.name.split('/')[-1] if cv and cv.fichier else None,
                    'createdAt': str(c.created_at),
                })
            result.append({
                'id': poste.id,
                'titre': poste.titre,
                'description': poste.description,
                'competences': poste.competences_requises,
                'totalCvs': len(cvs),
                'nouveaux': sum(1 for c in candidatures if c.statut == 'nouveau'),
                'acceptes': sum(1 for c in candidatures if c.statut == 'accepte'),
                'refuses': sum(1 for c in candidatures if c.statut == 'refuse'),
                'outlookCvs': sum(1 for cv_item in cvs if cv_item['source'] == 'outlook'),
                'bestScore': round(max(scores), 1) if scores else 0,
                'avgScore': round(sum(scores) / len(scores), 1) if scores else 0,
                'cvs': cvs,
            })
        return Response({'dossiers': result})
    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def analyse_cv_ia(request):
    """
    Analyse un CV avec Claude (IA Anthropic).
    Body (multipart/form-data) :
      - cv        : fichier PDF ou DOCX
      - job_title : titre du poste (optionnel)
      - job_desc  : description du poste (optionnel)
    """
    from .ai_claude import analyser_cv_claude
    from .ai_engine import extraire_texte

    cv_file = request.FILES.get('cv')
    job_title = request.POST.get('job_title', '')
    job_desc = request.POST.get('job_desc', '')

    if not cv_file:
        return Response({'error': 'Aucun fichier CV fourni'}, status=400)

    try:
        # Sauvegarder temporairement
        import tempfile, os
        suffix = '.pdf' if cv_file.name.lower().endswith('.pdf') else '.docx'
        fmt = 'pdf' if suffix == '.pdf' else 'docx'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in cv_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Extraire le texte
        cv_text = extraire_texte(tmp_path, fmt)
        os.unlink(tmp_path)

        if not cv_text.strip():
            return Response({'error': 'Impossible d\'extraire le texte du CV.'}, status=400)

        # Analyser avec Claude
        result = analyser_cv_claude(cv_text, job_description=job_desc, job_title=job_title)
        return Response(result)

    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def score_cv_ia(request):
    """
    Calcule le score de correspondance entre un CV et un poste avec Claude.
    Body (multipart/form-data) :
      - cv         : fichier PDF ou DOCX
      - job_title  : titre du poste
      - job_desc   : description du poste
    """
    from .ai_claude import score_cv_contre_poste
    from .ai_engine import extraire_texte

    cv_file = request.FILES.get('cv')
    job_title = request.POST.get('job_title', '')
    job_desc = request.POST.get('job_desc', '')

    if not cv_file:
        return Response({'error': 'Aucun fichier CV fourni'}, status=400)
    if not job_title and not job_desc:
        return Response({'error': 'Titre ou description du poste requis.'}, status=400)

    try:
        import tempfile, os
        suffix = '.pdf' if cv_file.name.lower().endswith('.pdf') else '.docx'
        fmt = 'pdf' if suffix == '.pdf' else 'docx'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in cv_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        cv_text = extraire_texte(tmp_path, fmt)
        os.unlink(tmp_path)

        if not cv_text.strip():
            return Response({'error': 'Impossible d\'extraire le texte du CV.'}, status=400)

        result = score_cv_contre_poste(cv_text, job_title, job_desc)
        return Response(result)

    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def analyse_cv_ml(request):
    """
    Analyse un CV uploadé manuellement via le moteur ML amélioré.
    Retourne les compétences, le profil détecté et le score.
    """
    from .ml_classifier import get_classifier

    cv_file = request.FILES.get('cv')
    if not cv_file:
        return Response({'error': 'Aucun fichier CV fourni'}, status=400)

    try:
        classifier = get_classifier()
        content = cv_file.read()
        result = classifier.analyse(
            cv_bytes=content,
            filename=cv_file.name,
        )
        return Response({
            'fullName': result.full_name,
            'email': result.email,
            'phone': result.phone,
            'educationLevel': result.education_level,
            'yearsExperience': result.years_experience,
            'detectedSkills': result.detected_skills,
            'summary': result.summary,
            'bestProfile': result.best_profile,
            'matchScore': result.match_score,
            'profileScores': result.profile_scores,
            'tfidfScore': result.tfidf_score,
            'ruleScore': result.rule_score,
            'confidence': result.confidence,
        })
    except Exception as e:
        import traceback
        return Response({'error': str(e), 'detail': traceback.format_exc()}, status=500)