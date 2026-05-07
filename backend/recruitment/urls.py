from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    PosteViewSet, CandidatViewSet, CVViewSet, CandidatureViewSet, EntretienViewSet,
    dashboard, candidates_list, candidate_detail, candidate_delete, candidate_upload, candidate_update,
    # Outlook / ML
    outlook_sync, outlook_status, analyse_cv_ml, dossiers,
    # Gmail
    gmail_sync, gmail_status, gmail_debug,
    # IA Groq
    analyse_cv_ia, score_cv_ia,
    # Authentification
    login_view, logout_view, me_view, register_view,
    # Setup initial superuser
    check_setup, setup_superuser,
    # Gestion des utilisateurs
    user_list, user_create, user_detail, user_delete, user_toggle_active,
    # Workflow / Domains
    workflow_statuses, domains_list, domain_candidates, domain_create, candidate_move_domain, candidate_status_history,
    chat_ask, chat_history, chat_history_clear, chat_conversations, chat_conversation_delete,
)
from .scoring_api import (
    calculate_score_for_candidature,
    calculate_scores_for_job,
    calculate_all_scores,
)

router = DefaultRouter()
router.register(r'postes', PosteViewSet)
router.register(r'candidats', CandidatViewSet)
router.register(r'cvs', CVViewSet)
router.register(r'candidatures', CandidatureViewSet)
router.register(r'entretiens', EntretienViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # ── Setup initial (premier administrateur) ───────────────────────────────
    path('auth/check-setup/', check_setup),       # GET  — système initialisé ?
    path('auth/setup/', setup_superuser),         # POST — créer le premier admin

    # ── Authentification ─────────────────────────────────────────────────────
    path('auth/login/', login_view),              # POST — connexion
    path('auth/register/', register_view),        # POST — inscription (Sign Up)
    path('auth/logout/', logout_view),            # POST — déconnexion
    path('auth/me/', me_view),                    # GET  — utilisateur courant
    path('auth/refresh/', TokenRefreshView.as_view()),  # POST — rafraîchir token

    # ── Gestion des utilisateurs (admin) ─────────────────────────────────────
    path('users/', user_list),                    # GET  — liste des comptes
    path('users/create/', user_create),           # POST — créer un compte
    path('users/<int:pk>/', user_detail),         # GET/PUT/PATCH — voir/modifier
    path('users/<int:pk>/delete/', user_delete),  # DELETE — supprimer
    path('users/<int:pk>/toggle/', user_toggle_active),  # PATCH — activer/désactiver

    # ── Dashboard et candidats ───────────────────────────────────────────────
    path('dashboard/', dashboard),
    path('candidates/', candidates_list),
    path('candidates/<int:pk>/', candidate_detail),
    path('candidates/<int:pk>/delete/', candidate_delete),
    path('candidates/upload/', candidate_upload),
    path('candidates/<int:pk>/update/', candidate_update),
    path('candidates/<int:pk>/history/', candidate_status_history),
    path('workflow/statuses/', workflow_statuses),
    path('domains/', domains_list),
    path('domains/create/', domain_create),
    path('domains/<int:pk>/candidates/', domain_candidates),
    path('candidates/<int:pk>/move-domain/', candidate_move_domain),
    path('chat/ask/', chat_ask),
    path('chat/history/', chat_history),
    path('chat/history/clear/', chat_history_clear),
    path('chat/conversations/', chat_conversations),
    path('chat/conversations/<int:pk>/', chat_conversation_delete),

    # ── Pipeline Outlook (legacy) ────────────────────────────────────────────
    path('outlook/sync/', outlook_sync),           # POST — déclenche la synchro
    path('outlook/status/', outlook_status),       # GET  — statut + historique

    # ── Pipeline Gmail ────────────────────────────────────────────────────────
    path('gmail/sync/', gmail_sync),               # POST — déclenche la synchro Gmail
    path('gmail/status/', gmail_status),           # GET  — statut Gmail + historique
    path('gmail/debug/', gmail_debug),             # GET  — diagnostic connexion Gmail

    # ── Analyse ML à la demande ──────────────────────────────────────────────
    path('ml/analyse/', analyse_cv_ml),            # POST — analyse un CV uploadé

    # ── Analyse IA (Groq) ─────────────────────────────────────────────────────
    path('ai/analyse/', analyse_cv_ia),            # POST — analyse complète par IA
    path('ai/score/', score_cv_ia),                # POST — score CV vs poste par IA

    # ── Scoring des candidatures ──────────────────────────────────────────────
    path('scoring/candidature/', calculate_score_for_candidature),  # POST — calcule score pour 1 candidature
    path('scoring/job/', calculate_scores_for_job),                 # POST — calcule scores pour une offre
    path('scoring/all/', calculate_all_scores),                     # POST — calcule tous les scores

    # ── Dossiers par domaine ─────────────────────────────────────────────────
    path('dossiers/', dossiers),                   # GET  — postes + CVs groupés
]
