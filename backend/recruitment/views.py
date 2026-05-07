import json
import os
import re
import unicodedata
from datetime import datetime, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .ml_classifier import get_classifier
from .ai_engine import calculer_score_avance
from .models import (
    Candidat,
    Candidature,
    CandidatureStatusHistory,
    ChatConversation,
    ChatMessage,
    CV,
    Domaine,
    EmailLog,
    Entretien,
    Poste,
    SyncHistory,
)
from .serializers import (
    CVSerializer,
    CandidatSerializer,
    CandidatureSerializer,
    CandidatureStatusHistorySerializer,
    CreateUserSerializer,
    DomaineSerializer,
    EntretienSerializer,
    PosteSerializer,
    UserSerializer,
)

User = get_user_model()


STATUS_LABELS = {
    "nouveau": "Nouveau",
    "prequalifie": "Pre-qualifie",
    "shortlist": "Shortlist",
    "entretien_rh": "Entretien RH",
    "entretien_technique": "Entretien Technique",
    "validation_manager": "Validation Manager",
    "accepte": "Accepte",
    "refuse": "Refuse",
    "entretien": "Entretien",
    "finaliste": "Finaliste",
    "offre": "Offre",
    "en_cours": "En cours",
    "archive": "Archive",
}

STATUS_FLOW = [
    "nouveau",
    "prequalifie",
    "shortlist",
    "entretien_rh",
    "entretien_technique",
    "validation_manager",
    "accepte",
    "refuse",
]

WORKFLOW_STATUS_META = [
    {"value": "nouveau", "label": "Nouveau", "color": "#b42318"},
    {"value": "prequalifie", "label": "Pre-qualifie", "color": "#ea580c"},
    {"value": "shortlist", "label": "Shortlist", "color": "#0f766e"},
    {"value": "entretien_rh", "label": "Entretien RH", "color": "#1d4ed8"},
    {"value": "entretien_technique", "label": "Entretien Technique", "color": "#4f46e5"},
    {"value": "validation_manager", "label": "Validation Manager", "color": "#7c3aed"},
    {"value": "accepte", "label": "Accepte", "color": "#15803d"},
    {"value": "refuse", "label": "Refuse", "color": "#6b7280"},
]

DEFAULT_DOMAIN_NAMES = [
    "Informatique & IT",
    "Ressources Humaines",
    "Finance & Comptabilite",
    "Marketing & Communication",
    "Commerce & Vente",
    "Production Industrielle",
    "Logistique",
    "Maintenance",
    "Qualite & Securite",
    "Administration",
]


def is_admin(user):
    return user.is_authenticated and user.role == "admin"


def scope_owned_queryset(request, queryset, owner_field="created_by"):
    """
    Isole les données par profil utilisateur.
    - admin: accès global
    - utilisateur connecté: uniquement ses données
    - anonyme: aucune donnée
    """
    if is_admin(request.user):
        return queryset
    # Certaines routes sont encore en AllowAny: dans ce cas,
    # on garde un mode "espace public" avec les enregistrements sans propriétaire.
    if not request.user.is_authenticated:
        return queryset.filter(**{f"{owner_field}__isnull": True})
    return queryset.filter(Q(**{owner_field: request.user}) | Q(**{f"{owner_field}__isnull": True}))


def split_csv(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def ai_strict_mode_enabled():
    return str(os.environ.get("AI_STRICT_PROVIDER", "false")).strip().lower() in {"1", "true", "yes", "on"}


DOMAIN_KEYWORDS = {
    "Industrie & Peinture": [
        "industrie",
        "industriel",
        "peinture",
        "colorado",
        "production",
        "usine",
        "maintenance",
        "electromecanique",
        "qse",
        "hse",
        "qualite",
        "colorimetrie",
        "resine",
        "pigment",
        "lean manufacturing",
    ],
    "IT & Digital": [
        "developpeur",
        "developer",
        "software",
        "data",
        "ia",
        "ai",
        "python",
        "react",
        "django",
        "devops",
        "cloud",
        "informatique",
    ],
    "Commercial & Marketing": [
        "commercial",
        "vente",
        "sales",
        "marketing",
        "brand",
        "crm",
        "business development",
        "communication",
    ],
    "Finance & Administration": [
        "finance",
        "comptable",
        "comptabilite",
        "controle de gestion",
        "administration",
        "rh",
        "paie",
    ],
}


def classify_poste_domain(poste):
    haystack = " ".join(
        [
            poste.titre or "",
            poste.description or "",
            poste.departement or "",
            poste.competences_requises or "",
            poste.competences_optionnelles or "",
        ]
    ).lower()
    if not haystack.strip():
        return "Autres domaines"

    best_domain = "Autres domaines"
    best_score = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain


def recommendation_for_score(score):
    score = float(score or 0)
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Selectionnable"
    if score >= 50:
        return "A evaluer"
    return "Insuffisant"


def workflow_step_for_status(status):
    return {
        "nouveau": "Ingestion",
        "prequalifie": "Pre-qualification",
        "shortlist": "Shortlist",
        "entretien_rh": "Entretien RH",
        "entretien_technique": "Entretien Technique",
        "validation_manager": "Validation Manager",
        "accepte": "Cloture",
        "refuse": "Cloture",
        "archive": "Archive",
        "entretien": "Entretien",
        "finaliste": "Decision finale",
        "offre": "Offre envoyee",
        "en_cours": "Evaluation RH",
    }.get(status, "Evaluation RH")


def sla_due_for_status(status):
    now = timezone.now()
    hours = {
        "nouveau": 24,
        "prequalifie": 48,
        "shortlist": 72,
        "entretien_rh": 4 * 24,
        "entretien_technique": 5 * 24,
        "validation_manager": 48,
        "entretien": 7 * 24,
        "finaliste": 48,
        "offre": 72,
        "en_cours": 24,
    }.get(status, 72)
    return now + timedelta(hours=hours)


def bootstrap_default_domains():
    for name in DEFAULT_DOMAIN_NAMES:
        Domaine.objects.get_or_create(nom=name, defaults={"description": f"Domaine RH: {name}"})


def normalize_text(value):
    text = (value or "").lower()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return " ".join(text.split())


def suggest_domain_name_from_text(text):
    value = normalize_text(text)
    if not value:
        return "Administration"

    def score_keywords(keywords):
        # Compte les occurrences réelles dans le texte (pas seulement présence unique)
        # pour réduire les erreurs de classement sur les profils mixtes.
        return sum(value.count(keyword) for keyword in keywords)

    mapping = [
        (
            "Production Industrielle",
            [
                "industrie",
                "industriel",
                "production",
                "usine",
                "peinture",
                "colorado",
                "ligne de production",
                "atelier",
            ],
        ),
        (
            "Maintenance",
            [
                "maintenance",
                "electromecanique",
                "electrique",
                "automatismes",
                "automatises",
                "mecanique",
                "machines",
                "systemes automatises",
                "maintenance preventive",
                "maintenance corrective",
            ],
        ),
        ("Qualite & Securite", ["qualite", "qse", "hse", "securite", "hygiene", "audit qualite"]),
        ("Informatique & IT", ["informatique", "developpeur", "software", "data", "python", "devops", "cloud"]),
        ("Ressources Humaines", ["ressources humaines", "recrutement", "talent", "gestion des talents"]),
        ("Finance & Comptabilite", ["finance", "comptable", "comptabilite", "controle de gestion"]),
        ("Marketing & Communication", ["marketing", "communication", "brand", "digital"]),
        ("Commerce & Vente", ["commercial", "vente", "sales", "business development"]),
        ("Logistique", ["logistique", "supply chain", "transport", "warehouse"]),
        ("Administration", ["administration", "assistant", "office manager"]),
    ]

    best_domain = "Administration"
    best_score = 0
    for domain_name, keywords in mapping:
        score = score_keywords(keywords)
        if score > best_score:
            best_score = score
            best_domain = domain_name

    # Priorité métier: les profils commerciaux/gestion ne doivent pas basculer
    # en maintenance à cause de quelques termes techniques dans le contexte.
    commercial_boost_terms = [
        "commercial",
        "responsable commercial",
        "gestion commerciale",
        "vente",
        "marketing",
        "business development",
    ]
    maintenance_terms = [
        "electromecanique",
        "maintenance preventive",
        "maintenance corrective",
        "systemes automatises",
        "automatismes",
        "mecanique",
    ]
    commercial_score = score_keywords(commercial_boost_terms)
    maintenance_score = score_keywords(maintenance_terms)
    if commercial_score >= 2 and commercial_score >= maintenance_score:
        return "Commerce & Vente"

    if best_score > 0:
        return best_domain
    return "Administration"


def resolve_domain_for_candidate(poste=None, analysis=None):
    source_text = " ".join(
        [
            getattr(poste, "titre", "") or "",
            getattr(poste, "description", "") or "",
            getattr(poste, "departement", "") or "",
            getattr(analysis, "best_profile", "") or "",
            getattr(analysis, "summary", "") or "",
            getattr(analysis, "raw_text", "") or "",
            ", ".join(getattr(analysis, "detected_skills", []) or []),
        ]
    )
    name = suggest_domain_name_from_text(source_text)
    domain, _ = Domaine.objects.get_or_create(nom=name, defaults={"description": f"Domaine RH: {name}"})
    return domain


def infer_domain_for_existing_candidate(candidat):
    best_candidature = candidat.candidatures.select_related("poste").order_by("-score", "-updated_at").first()
    latest_cv = candidat.cvs.order_by("-created_at").first()
    if latest_cv and latest_cv.texte_extrait:
        postes_payload = []
        if best_candidature and best_candidature.poste:
            postes_payload = [
                {
                    "id": best_candidature.poste.id,
                    "titre": best_candidature.poste.titre,
                    "description": best_candidature.poste.description or "",
                    "competences_requises": best_candidature.poste.competences_requises or "",
                    "departement": best_candidature.poste.departement or "",
                }
            ]
        groq_domain, _ = grok_recommend_domain(latest_cv.texte_extrait, postes_payload)
        if groq_domain:
            return groq_domain

    signal = " ".join(
        [
            candidat.current_title or "",
            candidat.resume_profil or "",
            candidat.competences or "",
            candidat.niveau_etudes or "",
            latest_cv.texte_extrait[:3000] if latest_cv and latest_cv.texte_extrait else "",
            # Le poste sert d'indice secondaire seulement pour éviter
            # qu'un mauvais mapping poste écrase le vrai domaine du CV.
            best_candidature.poste.titre if best_candidature and best_candidature.poste else "",
        ]
    )
    name = suggest_domain_name_from_text(signal)
    domain, _ = Domaine.objects.get_or_create(nom=name, defaults={"description": f"Domaine RH: {name}"})
    return domain


def grok_recommend_domain(cv_text, postes=None):
    try:
        from .ai_deepseek import recommander_repartition_cv_groq

        postes_payload = postes or []
        response = recommander_repartition_cv_groq(cv_text or "", postes_payload, DEFAULT_DOMAIN_NAMES)
        if response.get("ia_disponible") and response.get("domaine"):
            domain_name = str(response.get("domaine")).strip()
            if domain_name:
                domain, _ = Domaine.objects.get_or_create(
                    nom=domain_name,
                    defaults={"description": f"Domaine RH: {domain_name}"},
                )
                return domain, response
    except Exception:
        pass
    return None, {}


def grok_score_against_poste(cv_text, poste):
    try:
        from .ai_deepseek import score_cv_contre_poste_groq

        result = score_cv_contre_poste_groq(cv_text or "", poste.titre or "", poste.description or "")
        if result.get("ia_disponible"):
            score = float(result.get("score", 0.0) or 0.0)
            matched = result.get("competences_matchees", []) or []
            missing = result.get("competences_manquantes", []) or []
            level = str(result.get("niveau", "")).lower().strip()
            details = {
                "skills": round(score, 1),
                "experience": 0.0,
                "education": 0.0,
                "languages": 0.0,
                "location": 0.0,
                "softSkills": 0.0,
                "requiredSkillMatches": len(matched),
                "optionalSkillMatches": 0,
                "matchedSkills": matched,
                "missingSkills": missing,
                "provider": result.get("methode", "Grok"),
            }
            explanation = result.get("justification", "") or f"Scoring {result.get('methode', 'Grok')}."
            if level in {"excellent", "bon"} and score < 70:
                score = 70.0
            return score, details, explanation, True
    except Exception:
        pass
    return 0.0, {}, "", False


def backfill_candidates_domains(request):
    queryset = scope_owned_queryset(request, Candidat.objects.filter(domaine__isnull=True))
    updated_ids = []
    for candidat in queryset:
        # Backfill rapide pour éviter la latence au chargement des pages.
        domain = infer_domain_for_existing_candidate(candidat)
        if domain is None:
            continue
        candidat.domaine = domain
        candidat.save(update_fields=["domaine"])
        updated_ids.append(candidat.id)
    return updated_ids


def refresh_candidates_domains(request):
    queryset = scope_owned_queryset(
        request,
        Candidat.objects.prefetch_related("candidatures__poste", "cvs").all(),
    )
    updated_ids = []
    for candidat in queryset:
        # Eviter un reclassement coûteux à chaque chargement pour les domaines déjà fiables.
        if candidat.domaine and candidat.domaine.nom not in {"Administration", "Maintenance"}:
            continue
        domain = infer_domain_for_existing_candidate(candidat)
        if not domain:
            continue
        if candidat.domaine_id != domain.id:
            candidat.domaine = domain
            candidat.save(update_fields=["domaine"])
            updated_ids.append(candidat.id)
    return updated_ids


def ensure_candidate_has_scored_candidature(candidat, request_user=None):
    # Si une candidature existe déjà, ne rien faire.
    if candidat.candidatures.exists():
        return
    cv = candidat.cvs.order_by("-created_at").first()
    if not cv:
        return

    owner = request_user if getattr(request_user, "is_authenticated", False) else None
    analysis_stub = type("A", (), {"best_profile": candidat.current_title or ""})()
    poste = pick_target_job(analysis_stub, explicit_job_id=None, owner=owner)
    if not poste:
        return

    score, details_payload, explanation, grok_used = grok_score_against_poste(cv.texte_extrait or "", poste)
    if not grok_used:
        candidat_data = {
            "texte_cv": cv.texte_extrait or "",
            "competences": split_csv(candidat.competences),
            "langues": candidat.langues or "",
            "soft_skills": candidat.soft_skills or "",
            "annees_experience": float(candidat.annees_experience or 0),
            "niveau_etudes": candidat.niveau_etudes or "",
            "localisation": candidat.localisation or "",
        }
        poste_data = {
            "competences_requises": poste.competences_requises or "",
            "competences_optionnelles": poste.competences_optionnelles or "",
            "langues_requises": poste.langues_requises or "",
            "experience_min_annees": float(poste.experience_min_annees or 0),
            "niveau_etudes_requis": poste.niveau_etudes_requis or "",
            "localisation": poste.localisation or "",
            "poids_competences": float(poste.poids_competences or 35),
            "poids_experience": float(poste.poids_experience or 25),
            "poids_formation": float(poste.poids_formation or 20),
            "poids_langues": float(poste.poids_langues or 10),
            "poids_localisation": float(poste.poids_localisation or 5),
            "poids_soft_skills": float(poste.poids_soft_skills or 5),
        }
        score_result = calculer_score_avance(candidat_data, poste_data)
        score = float(score_result.get("score_final", 0.0))
        details_payload = {
            "skills": round(float(score_result.get("score_competences", 0.0)), 1),
            "experience": round(float(score_result.get("score_experience", 0.0)), 1),
            "education": round(float(score_result.get("score_formation", 0.0)), 1),
            "languages": round(float(score_result.get("score_langues", 0.0)), 1),
            "location": round(float(score_result.get("score_localisation", 0.0)), 1),
            "softSkills": round(float(score_result.get("score_soft_skills", 0.0)), 1),
            "requiredSkillMatches": len(score_result.get("details", {}).get("competences_matchees", [])),
            "optionalSkillMatches": len(score_result.get("details", {}).get("competences_optionnelles", [])),
        }
        explanation = (
            f"Skills {details_payload['skills']}%, experience {details_payload['experience']}%, "
            f"education {details_payload['education']}%, languages {details_payload['languages']}%, "
            f"location {details_payload['location']}%."
        )

    status = "shortlist" if score >= poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")

    Candidature.objects.update_or_create(
        candidat=candidat,
        poste=poste,
        defaults={
            "cv": cv,
            "statut": status,
            "score": score,
            "recommandation": recommendation_for_score(score),
            "workflow_step": workflow_step_for_status(status),
            "source_channel": candidat.source or "manual",
            "explication_score": explanation,
            "score_details_json": json.dumps(details_payload),
            "sla_due_at": sla_due_for_status(status),
            "created_by": owner,
        },
    )


def parse_candidate_name(full_name):
    raw = (full_name or "").strip()
    cleaned = " ".join(raw.replace("_", " ").replace("-", " ").split())
    lower = cleaned.lower()
    invalid_markers = [
        "competence",
        "compétence",
        "experience",
        "expérience",
        "formation",
        "profil",
        "resume",
        "curriculum",
        "vitae",
        "contact",
    ]
    if any(marker in lower for marker in invalid_markers):
        return "Candidat", "Inconnu"
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return "Candidat", "Inconnu"
    if len(parts) == 1:
        return parts[0], "Inconnu"
    return " ".join(parts[:-1]), parts[-1]


def unique_candidate_email(base_email):
    if base_email and not Candidat.objects.filter(email=base_email).exists():
        return base_email
    local = (base_email or f"candidat_{Candidat.objects.count() + 1}").split("@")[0].replace(" ", "_").lower()
    domain = "example.local"
    index = 1
    while True:
        candidate_email = f"{local}_{index}@{domain}"
        if not Candidat.objects.filter(email=candidate_email).exists():
            return candidate_email
        index += 1


def score_candidate_against_job(analysis, poste):
    required_skills = split_csv(poste.competences_requises)
    optional_skills = split_csv(poste.competences_optionnelles)
    required_languages = split_csv(poste.langues_requises)
    candidate_skills = set(skill.lower() for skill in analysis.detected_skills)
    candidate_languages = set(lang.lower() for lang in split_csv(getattr(analysis, "languages_csv", "")))
    lower_text = (analysis.raw_text or "").lower()

    required_overlap = len(candidate_skills & {skill.lower() for skill in required_skills})
    optional_overlap = len(candidate_skills & {skill.lower() for skill in optional_skills})
    skill_denominator = max(1, len(required_skills) + max(1, len(optional_skills)) * 0.4)
    skills_score = min(100.0, ((required_overlap + optional_overlap * 0.35) / skill_denominator) * 100)

    min_exp = float(poste.experience_min_annees or 0)
    if min_exp <= 0:
        experience_score = 100.0
    else:
        experience_score = min(100.0, (float(analysis.years_experience or 0) / min_exp) * 100)

    required_education = (poste.niveau_etudes_requis or "").lower()
    education_score = 100.0 if not required_education else (100.0 if required_education in (analysis.education_level or "").lower() else 55.0)

    if not required_languages:
        language_score = 100.0
    else:
        lang_overlap = len(candidate_languages & {lang.lower() for lang in required_languages})
        language_score = min(100.0, (lang_overlap / max(1, len(required_languages))) * 100)

    location_score = 100.0
    if poste.localisation:
        candidate_location = (getattr(analysis, "location", "") or "").lower()
        location_score = 100.0 if poste.localisation.lower() in candidate_location or candidate_location in poste.localisation.lower() else 50.0

    soft_keywords = {"leadership", "communication", "travail", "team", "gestion", "collaboration", "organisation", "autonomie"}
    soft_hits = len([kw for kw in soft_keywords if kw in lower_text])
    soft_score = min(100.0, (soft_hits / 4) * 100)

    weights = {
        "skills": float(poste.poids_competences or 35),
        "experience": float(poste.poids_experience or 25),
        "education": float(poste.poids_formation or 20),
        "languages": float(poste.poids_langues or 10),
        "location": float(poste.poids_localisation or 5),
        "soft": float(poste.poids_soft_skills or 5),
    }
    total_weight = sum(weights.values()) or 100.0
    final_score = (
        skills_score * weights["skills"]
        + experience_score * weights["experience"]
        + education_score * weights["education"]
        + language_score * weights["languages"]
        + location_score * weights["location"]
        + soft_score * weights["soft"]
    ) / total_weight

    details = {
        "skills": round(skills_score, 1),
        "experience": round(experience_score, 1),
        "education": round(education_score, 1),
        "languages": round(language_score, 1),
        "location": round(location_score, 1),
        "softSkills": round(soft_score, 1),
        "requiredSkillMatches": required_overlap,
        "optionalSkillMatches": optional_overlap,
    }
    explanation = (
        f"Skills {details['skills']}%, experience {details['experience']}%, education {details['education']}%, "
        f"languages {details['languages']}%, location {details['location']}%."
    )
    return round(final_score, 1), details, explanation


def pick_target_job(analysis, explicit_job_id=None, owner=None):
    posts_qs = Poste.objects.all()
    if owner and not is_admin(owner):
        # Inclure les postes de l'utilisateur + postes legacy sans propriétaire.
        posts_qs = posts_qs.filter(Q(created_by=owner) | Q(created_by__isnull=True))

    if explicit_job_id:
        try:
            return posts_qs.get(pk=explicit_job_id)
        except Poste.DoesNotExist:
            return None

    for poste in posts_qs:
        if poste.titre.lower() == (analysis.best_profile or "").lower():
            return poste
    selected = posts_qs.order_by("-created_at").first()
    if selected:
        return selected

    # Fallback de sécurité: si aucun poste scope user, tenter un poste global.
    return Poste.objects.all().order_by("-created_at").first()


def candidature_payload(candidature):
    cv = candidature.cv
    candidat = candidature.candidat
    skills = split_csv(candidat.competences)
    details = {}
    try:
        details = json.loads(candidature.score_details_json or "{}")
    except Exception:
        details = {}
    return {
        "id": candidature.id,
        "candidatureId": candidature.id,
        "candidateId": candidat.id,
        "jobId": candidature.poste_id,
        "fullName": f"{candidat.prenom} {candidat.nom}".strip(),
        "email": candidat.email,
        "phone": candidat.telephone,
        "location": candidat.localisation,
        "profileLabel": candidature.poste.titre if candidature.poste else candidat.current_title,
        "currentTitle": candidat.current_title,
        "matchScore": float(candidature.score or 0),
        "status": candidature.statut,
        "statusLabel": STATUS_LABELS.get(candidature.statut, candidature.statut),
        "recommendation": candidature.recommandation or recommendation_for_score(candidature.score),
        "workflowStep": candidature.workflow_step or workflow_step_for_status(candidature.statut),
        "educationLevel": candidat.niveau_etudes or "Non precise",
        "yearsExperience": float(candidat.annees_experience or 0),
        "summary": candidat.resume_profil or (cv.texte_extrait[:240] if cv and cv.texte_extrait else ""),
        "skills": skills,
        "languages": split_csv(candidat.langues),
        "softSkills": split_csv(candidat.soft_skills),
        "notes": candidature.decision_comment,
        "scoreDetails": details,
        "scoreExplanation": candidature.explication_score,
        "source": candidat.source,
        "domainId": candidat.domaine_id,
        "domainName": candidat.domaine.nom if candidat.domaine else "",
        "sourceEmail": cv.email_source if cv else candidat.source_detail,
        "cvUrl": cv.fichier.url if cv and cv.fichier else None,
        "cvFileName": cv.fichier.name.split("/")[-1] if cv and cv.fichier else None,
        "targetJob": candidature.poste.titre if candidature.poste else "",
        "assignedTo": candidature.assigned_to.username if candidature.assigned_to else "",
        "slaDueAt": candidature.sla_due_at.isoformat() if candidature.sla_due_at else None,
        "createdAt": candidat.created_at.isoformat(),
        "updatedAt": candidature.updated_at.isoformat(),
    }


def candidate_summary_payload(candidat):
    # Pour le dashboard et les listes, on expose la candidature la plus
    # récemment modifiée pour refléter fidèlement les changements de statut.
    candidature = (
        candidat.candidatures.select_related("poste", "assigned_to")
        .order_by("-updated_at", "-score")
        .first()
    )
    if candidature:
        return candidature_payload(candidature)
    cv = candidat.cvs.order_by("-created_at").first()
    skills = split_csv(candidat.competences)
    base_score = min(
        100.0,
        (len(skills) * 7.0)
        + (float(candidat.annees_experience or 0) * 6.0)
        + (10.0 if candidat.niveau_etudes else 0.0),
    )
    base_score = round(base_score, 1)
    return {
        "id": candidat.id,
        "candidatureId": None,
        "candidateId": candidat.id,
        "fullName": f"{candidat.prenom} {candidat.nom}".strip(),
        "email": candidat.email,
        "phone": candidat.telephone,
        "location": candidat.localisation,
        "profileLabel": candidat.current_title or "Non classe",
        "currentTitle": candidat.current_title,
        "matchScore": base_score,
        "status": "nouveau",
        "statusLabel": STATUS_LABELS["nouveau"],
        "recommendation": recommendation_for_score(base_score),
        "workflowStep": "Ingestion",
        "educationLevel": candidat.niveau_etudes or "Non precise",
        "yearsExperience": float(candidat.annees_experience or 0),
        "summary": candidat.resume_profil or (cv.texte_extrait[:240] if cv and cv.texte_extrait else ""),
        "skills": skills,
        "languages": split_csv(candidat.langues),
        "softSkills": split_csv(candidat.soft_skills),
        "notes": "",
        "scoreDetails": {},
        "scoreExplanation": "",
        "source": candidat.source,
        "domainId": candidat.domaine_id,
        "domainName": candidat.domaine.nom if candidat.domaine else "",
        "sourceEmail": cv.email_source if cv else candidat.source_detail,
        "cvUrl": cv.fichier.url if cv and cv.fichier else None,
        "cvFileName": cv.fichier.name.split("/")[-1] if cv and cv.fichier else None,
        "targetJob": "",
        "assignedTo": "",
        "slaDueAt": None,
        "createdAt": candidat.created_at.isoformat(),
        "updatedAt": candidat.created_at.isoformat(),
    }


def deduplicate_candidate_items(items):
    """
    Déduplique les candidats pour éviter les doublons d'affichage.
    Conserve la version la plus récente (updatedAt desc).
    """
    dedup = {}
    sorted_items = sorted(
        items,
        key=lambda item: item.get("updatedAt") or item.get("createdAt") or "",
        reverse=True,
    )
    for item in sorted_items:
        email = (item.get("email") or "").strip().lower()
        full_name = (item.get("fullName") or "").strip().lower()
        phone = "".join(ch for ch in (item.get("phone") or "") if ch.isdigit())
        if email:
            key = f"email:{email}"
        elif full_name and phone:
            key = f"name_phone:{full_name}:{phone}"
        elif full_name:
            key = f"name:{full_name}"
        else:
            key = f"id:{item.get('candidateId') or item.get('id')}"
        if key not in dedup:
            dedup[key] = item
    return list(dedup.values())


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def check_setup(request):
    # Afficher l'écran de setup uniquement au tout premier démarrage
    # (quand aucun compte n'existe). Sinon on garde l'écran de login normal.
    return Response({"needs_setup": User.objects.count() == 0})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def setup_superuser(request):
    if User.objects.exists():
        return Response({"error": "Le setup initial est deja termine."}, status=403)

    username = request.data.get("username", "").strip()
    email = request.data.get("email", "").strip()
    password = request.data.get("password", "")
    first_name = request.data.get("first_name", "").strip()
    last_name = request.data.get("last_name", "").strip()

    if not username or not email or len(password) < 6:
        return Response({"error": "Username, email et mot de passe valide requis."}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role="admin",
        is_staff=True,
        is_superuser=True,
    )
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "message": f'Compte administrateur "{user.username}" cree.',
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        },
        status=201,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "").strip()

    if not username or not password:
        return Response({"error": "Identifiants requis."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "Identifiants incorrects."}, status=401)
    if not user.is_active:
        return Response({"error": "Compte desactive."}, status=403)

    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        RefreshToken(request.data.get("refresh")).blacklist()
    except Exception:
        pass
    return Response({"message": "Deconnexion effectuee."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register_view(request):
    serializer = CreateUserSerializer(data={**request.data, "role": "recruteur"})
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "message": f'Compte "{user.username}" cree.',
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=201,
        )
    return Response({"errors": serializer.errors}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_list(request):
    if not is_admin(request.user):
        return Response({"error": "Acces refuse."}, status=403)
    return Response({"users": UserSerializer(User.objects.all().order_by("-date_joined"), many=True).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_create(request):
    if not is_admin(request.user):
        return Response({"error": "Acces refuse."}, status=403)
    serializer = CreateUserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"message": f'Compte "{user.username}" cree.', "user": UserSerializer(user).data}, status=201)
    return Response({"errors": serializer.errors}, status=400)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def user_detail(request, pk):
    if not is_admin(request.user):
        return Response({"error": "Acces refuse."}, status=403)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Utilisateur non trouve."}, status=404)

    if request.method == "GET":
        return Response({"user": UserSerializer(user).data})

    serializer = CreateUserSerializer(user, data=request.data, partial=request.method == "PATCH")
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Utilisateur mis a jour.", "user": UserSerializer(user).data})
    return Response({"errors": serializer.errors}, status=400)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def user_delete(request, pk):
    if not is_admin(request.user):
        return Response({"error": "Acces refuse."}, status=403)
    if request.user.pk == pk:
        return Response({"error": "Suppression de votre propre compte interdite."}, status=400)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Utilisateur non trouve."}, status=404)
    username = user.username
    user.delete()
    return Response({"message": f'Compte "{username}" supprime.'})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def user_toggle_active(request, pk):
    if not is_admin(request.user):
        return Response({"error": "Acces refuse."}, status=403)
    if request.user.pk == pk:
        return Response({"error": "Action interdite sur votre propre compte."}, status=400)
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"error": "Utilisateur non trouve."}, status=404)
    user.is_active = not user.is_active
    user.save()
    return Response({"message": "Statut mis a jour.", "user": UserSerializer(user).data})


@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard(request):
    try:
        q = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        profile_filter = request.GET.get("profile", "").strip()

        candidatures_qs = scope_owned_queryset(
            request,
            Candidature.objects.select_related("candidat", "poste", "cv", "assigned_to"),
        )
        candidats_qs = scope_owned_queryset(
            request,
            Candidat.objects.prefetch_related("candidatures__poste", "candidatures__assigned_to", "cvs"),
        ).order_by("-created_at")

        items = [candidate_summary_payload(candidat) for candidat in candidats_qs]
        items = deduplicate_candidate_items(items)
        if q:
            q_lower = q.lower()
            items = [
                item
                for item in items
                if any(
                    q_lower in str(value).lower()
                    for value in [item.get("fullName"), item.get("email"), item.get("targetJob"), item.get("currentTitle")]
                    if value
                )
            ]
        if status_filter:
            items = [item for item in items if item.get("status") == status_filter]
        if profile_filter:
            items = [item for item in items if item.get("targetJob") == profile_filter]

        items = sorted(items, key=lambda it: it.get("updatedAt") or it.get("createdAt") or "", reverse=True)
        scores = [item["matchScore"] for item in items if item["matchScore"] is not None]

        status_distribution = {}
        profile_distribution = {}
        for item in items:
            status_distribution[item.get("status", "nouveau")] = status_distribution.get(item.get("status", "nouveau"), 0) + 1
            profile_key = item.get("targetJob") or "Non classe"
            profile_distribution[profile_key] = profile_distribution.get(profile_key, 0) + 1

        funnel = [{"key": key, "label": STATUS_LABELS.get(key, key), "count": status_distribution.get(key, 0)} for key in STATUS_FLOW]
        score_distribution = [
            {"label": ">=85", "count": len([s for s in scores if s >= 85])},
            {"label": "70-84", "count": len([s for s in scores if 70 <= s < 85])},
            {"label": "50-69", "count": len([s for s in scores if 50 <= s < 70])},
            {"label": "<50", "count": len([s for s in scores if s < 50])},
        ]

        alerts = [
            item
            for item in items
            if item["matchScore"] >= 85 and item["status"] in {"nouveau", "prequalifie", "en_cours", "entretien_rh"}
        ][:6]

        jobs_overview = []
        postes_qs = scope_owned_queryset(request, Poste.objects.all()).order_by("titre")
        candidatures_global_qs = scope_owned_queryset(request, Candidature.objects.all())

        for poste in postes_qs:
            job_candidatures = candidatures_qs.filter(poste=poste)
            job_scores = [float(c.score or 0) for c in job_candidatures if c.score is not None]
            jobs_overview.append(
                {
                    "id": poste.id,
                    "name": poste.titre,
                    "department": poste.departement,
                    "location": poste.localisation,
                    "priority": poste.niveau_priorite,
                    "qualifiedThreshold": poste.score_qualification,
                    "candidateCount": job_candidatures.count(),
                    "qualifiedCount": job_candidatures.filter(score__gte=poste.score_qualification).count(),
                    "avgScore": round(sum(job_scores) / len(job_scores), 1) if job_scores else 0,
                }
            )

        processing_hours = []
        now = timezone.now()
        for candidature in candidatures_qs:
            if candidature.created_at and candidature.updated_at:
                processing_hours.append((candidature.updated_at - candidature.created_at).total_seconds() / 3600)
        overdue_count = len([c for c in candidatures_qs if c.sla_due_at and c.sla_due_at < now and c.statut not in {"accepte", "refuse", "archive"}])

        return Response(
            {
                "stats": {
                    "totalApplications": candidatures_global_qs.count(),
                    "openJobs": postes_qs.filter(workflow_actif=True).count(),
                    "totalCandidates": scope_owned_queryset(request, Candidat.objects.all()).count(),
                    "averageScore": round(sum(scores) / len(scores), 1) if scores else 0,
                    "bestScore": round(max(scores), 1) if scores else 0,
                    "newCandidates": status_distribution.get("nouveau", 0),
                    "qualifiedCandidates": len([s for s in scores if s >= 70]),
                    "interviewsCount": (
                        status_distribution.get("entretien", 0)
                        + status_distribution.get("finaliste", 0)
                        + status_distribution.get("entretien_rh", 0)
                        + status_distribution.get("entretien_technique", 0)
                        + status_distribution.get("validation_manager", 0)
                    ),
                    "acceptedCandidates": status_distribution.get("accepte", 0),
                    "refusedCandidates": status_distribution.get("refuse", 0),
                    "overdueActions": overdue_count,
                    "processingDelayHours": round(sum(processing_hours) / len(processing_hours), 1) if processing_hours else 0,
                },
                "candidates": items,
                "recentCandidates": items[:6],
                "topCandidates": sorted(items, key=lambda item: item["matchScore"], reverse=True)[:5],
                "profileDistribution": profile_distribution,
                "statusDistribution": status_distribution,
                "funnel": funnel,
                "scoreDistribution": score_distribution,
                "slaAlerts": alerts,
                "jobsOverview": jobs_overview,
                "jobProfiles": [{"id": p.id, "name": p.titre} for p in postes_qs],
                "filters": {
                    "statuses": [{"value": key, "label": label} for key, label in STATUS_LABELS.items()],
                    "profiles": sorted(profile_distribution.keys()),
                },
            }
        )
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["GET"])
@permission_classes([AllowAny])
def candidates_list(request):
    bootstrap_default_domains()
    domain_filter = request.GET.get("domain", "").strip()
    candidats = scope_owned_queryset(
        request,
        Candidat.objects.prefetch_related("candidatures__poste", "candidatures__assigned_to", "cvs").all(),
    ).order_by("-created_at")
    if domain_filter:
        candidats = candidats.filter(domaine_id=domain_filter)
    items = [candidate_summary_payload(candidat) for candidat in candidats]
    items = deduplicate_candidate_items(items)
    return Response({"candidates": items})


@api_view(["GET"])
@permission_classes([AllowAny])
def candidate_detail(request, pk):
    try:
        candidat = scope_owned_queryset(
            request,
            Candidat.objects.prefetch_related("candidatures__poste", "cvs"),
        ).get(pk=pk)
    except Candidat.DoesNotExist:
        return Response({"error": "Candidat non trouve"}, status=404)
    return Response({"candidate": candidate_summary_payload(candidat)})


@api_view(["DELETE"])
@permission_classes([AllowAny])
def candidate_delete(request, pk):
    try:
        candidat = scope_owned_queryset(request, Candidat.objects).get(pk=pk)
    except Candidat.DoesNotExist:
        return Response({"error": "Candidat non trouve"}, status=404)

    full_name = f"{candidat.prenom} {candidat.nom}".strip()
    candidat.delete()
    return Response({"message": f"Candidat supprime: {full_name}"})


@api_view(["POST"])
@permission_classes([AllowAny])
def candidate_upload(request):
    try:
        from .ai_deepseek import recommander_repartition_cv_groq

        cv_file = request.FILES.get("cv")
        if not cv_file:
            return Response({"error": "Aucun fichier CV fourni"}, status=400)

        source = request.POST.get("source", "manual")
        source_email = request.POST.get("sourceEmail", "").strip()
        target_job_id = request.POST.get("targetJobId", "").strip()

        filename = cv_file.name.lower()
        if filename.endswith(".pdf"):
            format_f = "pdf"
        elif filename.endswith(".docx"):
            format_f = "docx"
        else:
            return Response({"error": "Format non supporte. PDF ou DOCX requis."}, status=400)

        content = cv_file.read()
        cv_file.seek(0)
        classifier = get_classifier()
        analysis = classifier.analyse(content, cv_file.name, sender_email=source_email)
        analysis.languages_csv = ""
        analysis.location = ""

        # Anti-doublon essentiel: si un CV quasi identique existe déjà, retourner l'existant.
        normalized_cv_text = (analysis.raw_text or "").strip()
        if normalized_cv_text:
            existing_cv = (
                CV.objects.select_related("candidat")
                .filter(texte_extrait=normalized_cv_text)
                .order_by("-created_at")
                .first()
            )
            if existing_cv and existing_cv.candidat:
                existing_candidate = existing_cv.candidat

                # Si l'utilisateur choisit un poste pendant l'import, on doit
                # aussi (re)calculer le score pour un CV doublon.
                if target_job_id:
                    selected_poste = pick_target_job(
                        analysis,
                        explicit_job_id=target_job_id,
                        owner=request.user if request.user.is_authenticated else None,
                    )
                    if selected_poste:
                        score, details, explanation, grok_used = grok_score_against_poste(
                            analysis.raw_text or "",
                            selected_poste,
                        )
                        if not grok_used:
                            score, details, explanation = score_candidate_against_job(analysis, selected_poste)
                        status = "shortlist" if score >= selected_poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")
                        Candidature.objects.update_or_create(
                            candidat=existing_candidate,
                            poste=selected_poste,
                            defaults={
                                "cv": existing_cv,
                                "statut": status,
                                "score": score,
                                "recommandation": recommendation_for_score(score),
                                "workflow_step": workflow_step_for_status(status),
                                "source_channel": source,
                                "explication_score": explanation,
                                "score_details_json": json.dumps(details),
                                "sla_due_at": sla_due_for_status(status),
                                "created_by": request.user if request.user.is_authenticated else None,
                            },
                        )

                existing_payload = candidate_summary_payload(existing_candidate)
                return Response({"candidate": existing_payload, "duplicate": True}, status=200)

        groq_repartition = {}
        groq_poste_id = None
        postes_for_ai = []
        try:
            postes_for_ai = [
                {
                    "id": p.id,
                    "titre": p.titre,
                    "description": p.description or "",
                    "competences_requises": p.competences_requises or "",
                    "departement": p.departement or "",
                }
                for p in Poste.objects.all().order_by("-created_at")[:40]
            ]
            groq_repartition = recommander_repartition_cv_groq(
                analysis.raw_text or "",
                postes_for_ai,
                DEFAULT_DOMAIN_NAMES,
            )
            if (not target_job_id) and groq_repartition.get("ia_disponible") and groq_repartition.get("poste_titre"):
                suggested = str(groq_repartition.get("poste_titre", "")).strip().lower()
                poste_match = next((p for p in postes_for_ai if str(p["titre"]).strip().lower() == suggested), None)
                if poste_match:
                    groq_poste_id = str(poste_match["id"])
        except Exception:
            groq_repartition = {}

        # Ne pas bloquer l'import si Grok est indisponible : fallback local pour garder l'app fonctionnelle.

        bootstrap_default_domains()
        prenom, nom = parse_candidate_name(analysis.full_name)
        if prenom == "Candidat" and nom == "Inconnu":
            fallback_name = (analysis.email or source_email or "").split("@")[0].replace(".", " ").replace("_", " ").strip()
            if fallback_name:
                prenom, nom = parse_candidate_name(fallback_name.title())
        email = unique_candidate_email(analysis.email or source_email)
        poste = pick_target_job(
            analysis,
            explicit_job_id=target_job_id or groq_poste_id or None,
            owner=request.user if request.user.is_authenticated else None,
        )
        domaine = resolve_domain_for_candidate(poste=poste, analysis=analysis)
        if groq_repartition.get("ia_disponible") and groq_repartition.get("domaine"):
            domaine, _ = Domaine.objects.get_or_create(
                nom=groq_repartition.get("domaine"),
                defaults={"description": f"Domaine RH: {groq_repartition.get('domaine')}"},
            )
        elif analysis.raw_text:
            grok_domain, _ = grok_recommend_domain(analysis.raw_text or "", [])
            if grok_domain:
                domaine = grok_domain
        candidat = Candidat.objects.create(
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=analysis.phone,
            source=source,
            source_detail=source_email,
            current_title=analysis.best_profile,
            niveau_etudes=analysis.education_level,
            annees_experience=analysis.years_experience,
            competences=", ".join(analysis.detected_skills),
            resume_profil=analysis.summary,
            domaine=domaine,
            created_by=request.user if request.user.is_authenticated else None,
        )

        cv = CV.objects.create(
            candidat=candidat,
            fichier=cv_file,
            format_fichier=format_f,
            texte_extrait=analysis.raw_text or "",
            email_source=source_email,
        )

        candidature = None
        if poste:
            score, details, explanation, grok_used = grok_score_against_poste(analysis.raw_text or "", poste)
            if not grok_used:
                score, details, explanation = score_candidate_against_job(analysis, poste)
            status = "shortlist" if score >= poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")
            candidature, _ = Candidature.objects.update_or_create(
                candidat=candidat,
                poste=poste,
                defaults={
                    "cv": cv,
                    "statut": status,
                    "score": score,
                    "recommandation": recommendation_for_score(score),
                    "workflow_step": workflow_step_for_status(status),
                    "source_channel": source,
                    "explication_score": explanation,
                    "score_details_json": json.dumps(details),
                    "sla_due_at": sla_due_for_status(status),
                    "created_by": request.user if request.user.is_authenticated else None,
                },
            )

        payload = candidate_summary_payload(candidat)
        if candidature:
            payload = candidature_payload(candidature)
        if groq_repartition:
            routing_payload = {
                "enabled": bool(groq_repartition.get("ia_disponible")),
                "poste_titre": groq_repartition.get("poste_titre", ""),
                "domaine": groq_repartition.get("domaine", ""),
                "confiance": groq_repartition.get("confiance", 0),
                "justification": groq_repartition.get("justification", ""),
            }
            payload["groqRouting"] = routing_payload
            payload["deepseekRouting"] = routing_payload
        return Response({"candidate": payload}, status=201)
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["PATCH"])
@permission_classes([AllowAny])
def candidate_update(request, pk):
    try:
        candidat = scope_owned_queryset(request, Candidat.objects).get(pk=pk)
    except Candidat.DoesNotExist:
        return Response({"error": "Candidat non trouve"}, status=404)

    candidature = candidat.candidatures.select_related("poste", "assigned_to").order_by("-updated_at").first()
    if not candidature:
        return Response({"candidate": candidate_summary_payload(candidat)})

    status = request.data.get("status")
    notes = request.data.get("decisionComment")
    assigned_to_id = request.data.get("assignedToId")
    status_comment = request.data.get("statusComment", "")

    if status:
        previous_status = candidature.statut
        candidature.statut = status
        candidature.workflow_step = workflow_step_for_status(status)
        candidature.sla_due_at = sla_due_for_status(status)
        if previous_status != status:
            CandidatureStatusHistory.objects.create(
                candidature=candidature,
                previous_status=previous_status,
                new_status=status,
                comment=status_comment or "",
                changed_by=request.user if request.user.is_authenticated else None,
            )
    if notes is not None:
        candidature.decision_comment = notes
    if assigned_to_id:
        try:
            candidature.assigned_to = User.objects.get(pk=assigned_to_id)
        except User.DoesNotExist:
            candidature.assigned_to = None
    candidature.save()
    return Response({"candidate": candidature_payload(candidature)})


class PosteViewSet(viewsets.ModelViewSet):
    queryset = Poste.objects.all().order_by("titre")
    serializer_class = PosteSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        return scope_owned_queryset(self.request, Poste.objects.all()).order_by("titre")

    def perform_create(self, serializer):
        poste = serializer.save(
            created_by=self.request.user if self.request.user.is_authenticated else None
        )
        self._evaluate_existing_candidates_for_poste(poste)

    def _evaluate_existing_candidates_for_poste(self, poste):
        # Inclure les CV déjà présents en base au moment de la création du poste.
        # - admin: tous les candidats
        # - utilisateur connecté: ses candidats + legacy sans propriétaire
        # - anonyme: legacy sans propriétaire
        if is_admin(self.request.user):
            candidats = Candidat.objects.prefetch_related("cvs").all()
        elif self.request.user.is_authenticated:
            candidats = Candidat.objects.prefetch_related("cvs").filter(
                Q(created_by=self.request.user) | Q(created_by__isnull=True)
            )
        else:
            candidats = Candidat.objects.prefetch_related("cvs").filter(created_by__isnull=True)
        for candidat in candidats:
            cv = candidat.cvs.order_by("-created_at").first()
            if not cv:
                continue

            candidat_data = {
                "texte_cv": cv.texte_extrait or "",
                "competences": split_csv(candidat.competences),
                "langues": candidat.langues or "",
                "soft_skills": candidat.soft_skills or "",
                "annees_experience": float(candidat.annees_experience or 0),
                "niveau_etudes": candidat.niveau_etudes or "",
                "localisation": candidat.localisation or "",
            }
            poste_data = {
                "competences_requises": poste.competences_requises or "",
                "competences_optionnelles": poste.competences_optionnelles or "",
                "langues_requises": poste.langues_requises or "",
                "experience_min_annees": float(poste.experience_min_annees or 0),
                "niveau_etudes_requis": poste.niveau_etudes_requis or "",
                "localisation": poste.localisation or "",
                "poids_competences": float(poste.poids_competences or 35),
                "poids_experience": float(poste.poids_experience or 25),
                "poids_formation": float(poste.poids_formation or 20),
                "poids_langues": float(poste.poids_langues or 10),
                "poids_localisation": float(poste.poids_localisation or 5),
                "poids_soft_skills": float(poste.poids_soft_skills or 5),
            }

            score, details_payload, explanation, grok_used = grok_score_against_poste(cv.texte_extrait or "", poste)
            if not grok_used and not ai_strict_mode_enabled():
                score_result = calculer_score_avance(candidat_data, poste_data)
                score = float(score_result.get("score_final", 0.0))
                details_payload = {
                    "skills": round(float(score_result.get("score_competences", 0.0)), 1),
                    "experience": round(float(score_result.get("score_experience", 0.0)), 1),
                    "education": round(float(score_result.get("score_formation", 0.0)), 1),
                    "languages": round(float(score_result.get("score_langues", 0.0)), 1),
                    "location": round(float(score_result.get("score_localisation", 0.0)), 1),
                    "softSkills": round(float(score_result.get("score_soft_skills", 0.0)), 1),
                    "requiredSkillMatches": len(score_result.get("details", {}).get("competences_matchees", [])),
                    "optionalSkillMatches": len(score_result.get("details", {}).get("competences_optionnelles", [])),
                }
                explanation = (
                    f"Skills {details_payload['skills']}%, experience {details_payload['experience']}%, "
                    f"education {details_payload['education']}%, languages {details_payload['languages']}%, "
                    f"location {details_payload['location']}%."
                )
            elif not grok_used and ai_strict_mode_enabled():
                continue

            status = "shortlist" if score >= poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")

            defaults = {
                "cv": cv,
                "statut": status,
                "score": score,
                "recommandation": recommendation_for_score(score),
                "workflow_step": workflow_step_for_status(status),
                "source_channel": candidat.source or "manual",
                "explication_score": explanation,
                "score_details_json": json.dumps(details_payload),
                "sla_due_at": sla_due_for_status(status),
                "created_by": self.request.user if self.request.user.is_authenticated else None,
            }
            Candidature.objects.update_or_create(
                candidat=candidat,
                poste=poste,
                defaults=defaults,
            )


class CandidatViewSet(viewsets.ModelViewSet):
    queryset = Candidat.objects.all().order_by("-created_at")
    serializer_class = CandidatSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        return scope_owned_queryset(self.request, Candidat.objects.all()).order_by("-created_at")


class CVViewSet(viewsets.ModelViewSet):
    queryset = CV.objects.all().order_by("-created_at")
    serializer_class = CVSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = CV.objects.select_related("candidat")
        if is_admin(self.request.user):
            return qs.order_by("-created_at")
        if not self.request.user.is_authenticated:
            return qs.filter(candidat__created_by__isnull=True).order_by("-created_at")
        return qs.filter(candidat__created_by=self.request.user).order_by("-created_at")


class CandidatureViewSet(viewsets.ModelViewSet):
    queryset = Candidature.objects.all().order_by("-updated_at")
    serializer_class = CandidatureSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        return scope_owned_queryset(self.request, Candidature.objects.all()).order_by("-updated_at")


class EntretienViewSet(viewsets.ModelViewSet):
    queryset = Entretien.objects.select_related(
        "candidature", "candidature__candidat", "candidature__poste"
    ).all()
    serializer_class = EntretienSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        scoped = scope_owned_queryset(self.request, Candidature.objects.all())
        return (
            Entretien.objects.filter(candidature__in=scoped)
            .select_related("candidature", "candidature__candidat", "candidature__poste")
            .order_by("debut")
        )

    def perform_create(self, serializer):
        cand = serializer.validated_data["candidature"]
        if not scope_owned_queryset(self.request, Candidature.objects.filter(pk=cand.pk)).exists():
            raise PermissionDenied("Candidature non accessible.")
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    def perform_update(self, serializer):
        cand = serializer.validated_data.get("candidature")
        if cand is not None and not scope_owned_queryset(self.request, Candidature.objects.filter(pk=cand.pk)).exists():
            raise PermissionDenied("Candidature non accessible.")
        serializer.save()


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_debug(request):
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secret_file = os.environ.get("GMAIL_CLIENT_SECRET_FILE", os.path.join(backend_dir, "client_secret.json"))
    token_file = os.environ.get("GMAIL_TOKEN_FILE", os.path.join(backend_dir, "token.json"))

    info = {
        "secret_file_exists": os.path.exists(secret_file),
        "token_file_exists": os.path.exists(token_file),
        "secret_file_path": secret_file,
        "token_file_path": token_file,
        "connection": None,
        "emails_found": 0,
        "already_processed": 0,
        "sample_emails": [],
        "error": None,
    }

    if not info["token_file_exists"]:
        info["error"] = "token.json manquant. Lancez: python manage.py gmail_auth"
        return Response(info)

    try:
        from .gmail_connector import GmailCVConnector

        connector = GmailCVConnector.from_env()
        info["connection"] = connector.test_connection()
        if info["connection"]["status"] == "ok":
            service = connector._get_service()
            query = "has:attachment (filename:pdf OR filename:docx OR filename:doc) in:inbox"
            result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
            messages = result.get("messages", [])
            info["emails_found"] = result.get("resultSizeEstimate", len(messages))
            for msg_meta in messages[:5]:
                msg = service.users().messages().get(
                    userId="me", id=msg_meta["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                info["sample_emails"].append(
                    {
                        "id": msg_meta["id"],
                        "from": headers.get("from", ""),
                        "subject": headers.get("subject", ""),
                        "date": headers.get("date", ""),
                    }
                )
        info["already_processed"] = EmailLog.objects.count()
    except Exception as exc:
        import traceback

        info["error"] = str(exc)
        info["traceback"] = traceback.format_exc()
    return Response(info)


def _persist_sync_history(report, triggered_by):
    SyncHistory.objects.create(
        started_at=datetime.fromisoformat(report.started_at) if report.started_at else datetime.now(),
        finished_at=datetime.fromisoformat(report.finished_at) if report.finished_at else datetime.now(),
        emails_scanned=report.emails_scanned,
        cvs_found=report.cvs_found,
        cvs_created=report.cvs_created,
        cvs_duplicate=report.cvs_duplicate,
        cvs_error=report.cvs_error,
        triggered_by=triggered_by,
        errors_json=json.dumps(report.errors, ensure_ascii=False),
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_sync(request):
    try:
        from .gmail_pipeline import get_gmail_pipeline

        pipeline = get_gmail_pipeline()
        report = pipeline.run()
        _persist_sync_history(report, request.data.get("triggeredBy", "manual"))
        return Response(report.to_dict())
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def gmail_status(request):
    from .gmail_pipeline import get_gmail_pipeline

    pipeline = get_gmail_pipeline()
    connection = pipeline.test_connection()
    last_syncs = SyncHistory.objects.order_by("-started_at")[:5]
    logs = EmailLog.objects.select_related("candidat").order_by("-created_at")[:20]
    return Response(
        {
            "connection": connection,
            "syncHistory": [
                {
                    "startedAt": str(sync.started_at),
                    "finishedAt": str(sync.finished_at),
                    "emailsScanned": sync.emails_scanned,
                    "cvsCreated": sync.cvs_created,
                    "cvsError": sync.cvs_error,
                    "triggeredBy": sync.triggered_by,
                }
                for sync in last_syncs
            ],
            "emailLogs": [
                {
                    "messageId": log.message_id[:16] + "...",
                    "senderEmail": log.sender_email,
                    "senderName": log.sender_name,
                    "subject": log.subject[:80],
                    "filename": log.filename,
                    "status": log.status,
                    "errorMessage": log.error_message[:200] if log.error_message else "",
                    "candidatId": log.candidat_id,
                    "candidatName": f"{log.candidat.prenom} {log.candidat.nom}" if log.candidat else None,
                    "createdAt": str(log.created_at),
                }
                for log in logs
            ],
            "totalEmailsProcessed": EmailLog.objects.count(),
            "totalSyncs": SyncHistory.objects.count(),
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def outlook_sync(request):
    try:
        from .pipeline import get_pipeline

        pipeline = get_pipeline()
        report = pipeline.run()
        _persist_sync_history(report, request.data.get("triggeredBy", "manual"))
        return Response(report.to_dict())
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def outlook_status(request):
    from .pipeline import get_pipeline

    pipeline = get_pipeline()
    connection = pipeline.test_connection()
    last_syncs = SyncHistory.objects.order_by("-started_at")[:5]
    logs = EmailLog.objects.select_related("candidat").order_by("-created_at")[:20]
    return Response(
        {
            "connection": connection,
            "syncHistory": [
                {
                    "startedAt": str(sync.started_at),
                    "finishedAt": str(sync.finished_at),
                    "emailsScanned": sync.emails_scanned,
                    "cvsCreated": sync.cvs_created,
                    "cvsError": sync.cvs_error,
                    "triggeredBy": sync.triggered_by,
                }
                for sync in last_syncs
            ],
            "emailLogs": [
                {
                    "messageId": log.message_id[:16] + "...",
                    "senderEmail": log.sender_email,
                    "senderName": log.sender_name,
                    "subject": log.subject[:80],
                    "filename": log.filename,
                    "status": log.status,
                    "errorMessage": log.error_message[:200] if log.error_message else "",
                    "candidatId": log.candidat_id,
                    "candidatName": f"{log.candidat.prenom} {log.candidat.nom}" if log.candidat else None,
                    "createdAt": str(log.created_at),
                }
                for log in logs
            ],
            "totalEmailsProcessed": EmailLog.objects.count(),
            "totalSyncs": SyncHistory.objects.count(),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def dossiers(request):
    try:
        bootstrap_default_domains()
        result = []
        domain_buckets = {}
        postes_qs = scope_owned_queryset(request, Poste.objects.all()).order_by("titre")
        for poste in postes_qs:
            candidatures = scope_owned_queryset(
                request,
                Candidature.objects.filter(poste=poste).select_related("candidat", "cv", "assigned_to"),
            )
            items = [candidature_payload(candidature) for candidature in candidatures]
            scores = [item["matchScore"] for item in items if item["matchScore"] is not None]
            domaine = classify_poste_domain(poste)
            dossier_item = {
                "id": poste.id,
                "titre": poste.titre,
                "description": poste.description,
                "departement": poste.departement,
                "localisation": poste.localisation,
                "typeContrat": poste.type_contrat,
                "priorite": poste.niveau_priorite,
                "seuilQualification": poste.score_qualification,
                "competences": poste.competences_requises,
                "langues": poste.langues_requises,
                "domaine": domaine,
                "totalCvs": len(items),
                "nouveaux": len([item for item in items if item["status"] == "nouveau"]),
                "prequalifies": len([item for item in items if item["status"] == "prequalifie"]),
                "entretiens": len([item for item in items if item["status"] == "entretien"]),
                "acceptes": len([item for item in items if item["status"] == "accepte"]),
                "refuses": len([item for item in items if item["status"] == "refuse"]),
                "outlookCvs": len([item for item in items if item["source"] == "outlook"]),
                "bestScore": round(max(scores), 1) if scores else 0,
                "avgScore": round(sum(scores) / len(scores), 1) if scores else 0,
                "cvs": items,
            }
            result.append(dossier_item)
            bucket = domain_buckets.setdefault(
                domaine,
                {
                    "domaine": domaine,
                    "totalPostes": 0,
                    "totalCvs": 0,
                    "bestScore": 0,
                    "dossiers": [],
                },
            )
            bucket["totalPostes"] += 1
            bucket["totalCvs"] += dossier_item["totalCvs"]
            bucket["bestScore"] = max(bucket["bestScore"], dossier_item["bestScore"])
            bucket["dossiers"].append(dossier_item)
        domain_folders = sorted(
            domain_buckets.values(),
            key=lambda item: (0 if item["domaine"] == "Industrie & Peinture" else 1, item["domaine"]),
        )
        return Response({"dossiers": result, "dossiersParDomaine": domain_folders})
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def analyse_cv_ia(request):
    from .ai_deepseek import analyser_cv_groq
    from .ml_scoring_engine import analyze_cv_ml
    from .ai_engine import extraire_texte

    cv_file = request.FILES.get("cv")
    job_title = request.POST.get("job_title", "")
    job_desc = request.POST.get("job_desc", "")
    if not cv_file:
        return Response({"error": "Aucun fichier CV fourni"}, status=400)
    filename = (cv_file.name or "").lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        return Response(
            {"error": "Format non supporte pour l'analyse IA. Utilisez un fichier PDF ou DOCX."},
            status=400,
        )

    try:
        import os
        import tempfile

        suffix = ".pdf" if filename.endswith(".pdf") else ".docx"
        fmt = "pdf" if suffix == ".pdf" else "docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in cv_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        cv_text = extraire_texte(tmp_path, fmt)
        os.unlink(tmp_path)
        if not cv_text.strip():
            return Response({"error": "Impossible d'extraire le texte du CV."}, status=400)
        
        # Analyse Groq (prioritaire) puis fallback ML.
        groq_result = analyser_cv_groq(cv_text, job_description=job_desc, job_title=job_title)
        if groq_result.get("ia_disponible"):
            groq_result["methode"] = "Grok"
            return Response(groq_result)

        # Fallback ML (TF-IDF + Word2Vec + XGBoost)
        result = analyze_cv_ml(cv_text, job_description=job_desc, job_title=job_title)
        
        # Formatage de la réponse
        return Response({
            'nom': result.full_name.split()[-1] if result.full_name else '',
            'prenom': ' '.join(result.full_name.split()[:-1]) if result.full_name else '',
            'email': result.email,
            'telephone': result.phone,
            'adresse': '',
            'niveau_etudes': result.education_level,
            'annees_experience': result.years_experience,
            'langues': [],
            'competences_techniques': result.detected_skills,
            'competences_soft': [],
            'formations': [],
            'experiences': [],
            'resume_profil': result.summary,
            'points_forts': result.recommendations,
            'points_faibles': [],
            'score_global': int(result.match_score),
            'recommandation': 'À retenir' if result.match_score >= 75 else ('Intéressant' if result.match_score >= 50 else 'Insuffisant'),
            'justification_score': f'TF-IDF: {result.tfidf_score:.0f}%, Word2Vec: {result.w2v_score:.0f}%, XGBoost: {result.xgb_score:.0f}%',
            'ia_disponible': bool(groq_result.get("ia_disponible", True)),
            'methode': 'TF-IDF + Word2Vec + XGBoost',
            'confidence': result.confidence,
            'groq_error': groq_result.get("error", ""),
            'deepseek_error': groq_result.get("error", ""),
        })
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def score_cv_ia(request):
    from .ai_deepseek import score_cv_contre_poste_groq
    from .ml_scoring_engine import score_cv_against_job
    from .ai_engine import extraire_texte

    cv_file = request.FILES.get("cv")
    job_title = request.POST.get("job_title", "")
    job_desc = request.POST.get("job_desc", "")
    if not cv_file:
        return Response({"error": "Aucun fichier CV fourni"}, status=400)
    filename = (cv_file.name or "").lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        return Response(
            {"error": "Format non supporte pour le scoring IA. Utilisez un fichier PDF ou DOCX."},
            status=400,
        )
    if not job_title and not job_desc:
        return Response({"error": "Titre ou description du poste requis."}, status=400)

    try:
        import os
        import tempfile

        suffix = ".pdf" if filename.endswith(".pdf") else ".docx"
        fmt = "pdf" if suffix == ".pdf" else "docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in cv_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        cv_text = extraire_texte(tmp_path, fmt)
        os.unlink(tmp_path)
        if not cv_text.strip():
            return Response({"error": "Impossible d'extraire le texte du CV."}, status=400)
        
        # Scoring Groq (prioritaire) puis fallback ML.
        groq_score = score_cv_contre_poste_groq(cv_text, job_title, job_desc)
        if groq_score.get("ia_disponible"):
            return Response(groq_score)

        # Fallback ML (TF-IDF + Word2Vec + XGBoost)
        result = score_cv_against_job(cv_text, job_title, job_desc)
        result["groq_error"] = groq_score.get("justification", "")
        result["deepseek_error"] = groq_score.get("justification", "")
        return Response(result)
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def analyse_cv_ml(request):
    cv_file = request.FILES.get("cv")
    if not cv_file:
        return Response({"error": "Aucun fichier CV fourni"}, status=400)

    try:
        classifier = get_classifier()
        result = classifier.analyse(cv_file.read(), cv_file.name)
        return Response(
            {
                "fullName": result.full_name,
                "email": result.email,
                "phone": result.phone,
                "educationLevel": result.education_level,
                "yearsExperience": result.years_experience,
                "detectedSkills": result.detected_skills,
                "summary": result.summary,
                "bestProfile": result.best_profile,
                "matchScore": result.match_score,
                "profileScores": result.profile_scores,
                "tfidfScore": result.tfidf_score,
                "ruleScore": result.rule_score,
                "confidence": result.confidence,
            }
        )
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def workflow_statuses(request):
    return Response({"statuses": WORKFLOW_STATUS_META})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def domains_list(request):
    bootstrap_default_domains()
    # Respecter les affectations manuelles : on complète seulement
    # les candidats sans domaine, sans reclassement forcé.
    backfill_candidates_domains(request)
    queryset = Domaine.objects.filter(actif=True).annotate(candidats_count=Count("candidats"))
    return Response({"domains": DomaineSerializer(queryset, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def domain_candidates(request, pk):
    # Ne pas écraser les déplacements manuels entre dossiers.
    backfill_candidates_domains(request)
    try:
        domaine = Domaine.objects.get(pk=pk, actif=True)
    except Domaine.DoesNotExist:
        return Response({"error": "Domaine non trouve."}, status=404)
    candidats = scope_owned_queryset(
        request,
        Candidat.objects.filter(domaine=domaine).prefetch_related("candidatures__poste", "cvs"),
    ).order_by("-created_at")
    return Response(
        {
            "domain": DomaineSerializer(domaine).data,
            "candidates": [candidate_summary_payload(candidat) for candidat in candidats],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def domain_create(request):
    name = (request.data.get("nom") or "").strip()
    description = (request.data.get("description") or "").strip()
    if not name:
        return Response({"error": "Le nom du dossier est obligatoire."}, status=400)
    if len(name) < 2:
        return Response({"error": "Le nom du dossier est trop court."}, status=400)
    domain, created = Domaine.objects.get_or_create(
        nom=name,
        defaults={"description": description or f"Domaine RH: {name}"},
    )
    if not created:
        return Response({"error": "Ce dossier existe deja."}, status=400)
    return Response(
        {
            "domain": {
                "id": domain.id,
                "nom": domain.nom,
                "description": domain.description,
                "actif": domain.actif,
                "created_at": domain.created_at.isoformat() if domain.created_at else None,
                "candidats_count": 0,
            }
        },
        status=201,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def candidate_move_domain(request, pk):
    domain_id = request.data.get("domainId")
    if not domain_id:
        return Response({"error": "domainId est requis."}, status=400)
    try:
        candidat = scope_owned_queryset(request, Candidat.objects).get(pk=pk)
    except Candidat.DoesNotExist:
        return Response({"error": "Candidat non trouve."}, status=404)
    try:
        domain = Domaine.objects.get(pk=domain_id, actif=True)
    except Domaine.DoesNotExist:
        return Response({"error": "Dossier cible non trouve."}, status=404)
    candidat.domaine = domain
    candidat.save(update_fields=["domaine"])
    return Response({"candidate": candidate_summary_payload(candidat)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def candidate_status_history(request, pk):
    try:
        candidat = scope_owned_queryset(
            request,
            Candidat.objects.prefetch_related("candidatures__status_history"),
        ).get(pk=pk)
    except Candidat.DoesNotExist:
        return Response({"error": "Candidat non trouve."}, status=404)
    candidatures = candidat.candidatures.all()
    history = CandidatureStatusHistory.objects.filter(candidature__in=candidatures).select_related("changed_by")
    return Response({"history": CandidatureStatusHistorySerializer(history, many=True).data})


def _chat_message_to_api_dict(msg):
    highlights = []
    suggested_actions = []
    try:
        highlights = json.loads(msg.highlights_json or "[]")
    except Exception:
        highlights = []
    try:
        suggested_actions = json.loads(msg.suggested_actions_json or "[]")
    except Exception:
        suggested_actions = []
    return {
        "id": msg.id,
        "role": msg.role,
        "text": msg.text,
        "highlights": highlights if isinstance(highlights, list) else [],
        "suggestedActions": suggested_actions if isinstance(suggested_actions, list) else [],
        "createdAt": msg.created_at.isoformat() if msg.created_at else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request):
    cid = (request.GET.get("conversation") or "").strip()
    if not cid:
        return Response({"error": "Parametre conversation requis."}, status=400)
    conv = get_object_or_404(ChatConversation, pk=cid, user=request.user)
    try:
        limit = int(request.GET.get("limit", 200))
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 500))
    qs = (
        ChatMessage.objects.filter(conversation=conv, user=request.user)
        .order_by("-created_at")[:limit]
    )
    messages = [_chat_message_to_api_dict(m) for m in reversed(list(qs))]
    return Response({"messages": messages})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_conversations(request):
    if request.method == "GET":
        convs = (
            ChatConversation.objects.filter(user=request.user)
            .annotate(message_count=Count("messages"))
            .order_by("-updated_at")[:120]
        )
        out = []
        for c in convs:
            last = c.messages.order_by("-created_at").first()
            title = (c.title or "").strip()
            if not title and last and last.text:
                raw = (last.text or "").strip()
                title = raw[:72] + ("…" if len(raw) > 72 else "")
            if not title:
                title = f"Conversation du {c.created_at:%d/%m/%Y %H:%M}"
            preview = ""
            if last and last.text:
                rawp = (last.text or "").strip()
                preview = rawp[:120] + ("…" if len(rawp) > 120 else "")
            out.append(
                {
                    "id": c.id,
                    "title": title,
                    "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
                    "createdAt": c.created_at.isoformat() if c.created_at else None,
                    "messageCount": c.message_count,
                    "preview": preview,
                }
            )
        return Response({"conversations": out})

    title = (request.data.get("title") or "").strip()[:200]
    c = ChatConversation.objects.create(user=request.user, title=title)
    return Response(
        {
            "conversation": {
                "id": c.id,
                "title": (c.title or "").strip() or f"Conversation du {c.created_at:%d/%m/%Y %H:%M}",
                "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
                "createdAt": c.created_at.isoformat() if c.created_at else None,
                "messageCount": 0,
                "preview": "",
            }
        },
        status=201,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def chat_conversation_delete(request, pk):
    conv = get_object_or_404(ChatConversation, pk=pk, user=request.user)
    conv.delete()
    return Response({"ok": True})


@api_view(["DELETE", "POST"])
@permission_classes([IsAuthenticated])
def chat_history_clear(request):
    ChatConversation.objects.filter(user=request.user).delete()
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_ask(request):
    question = (request.data.get("question") or "").strip()
    if not question:
        return Response({"error": "Question requise."}, status=400)

    conv_id = request.data.get("conversationId")
    if conv_id:
        conv = get_object_or_404(ChatConversation, pk=conv_id, user=request.user)
    else:
        conv = ChatConversation.objects.create(user=request.user, title="")

    history_msgs = list(
        ChatMessage.objects.filter(conversation=conv, user=request.user).order_by("-created_at")[:36]
    )
    history_msgs.reverse()
    lines = []
    for hm in history_msgs:
        label = "Utilisateur" if hm.role == ChatMessage.ROLE_USER else "Assistant"
        t = (hm.text or "").replace("\n", " ").strip()[:1200]
        lines.append(f"- {label}: {t}")
    history_block = (
        "\n".join(lines) if lines else "(aucun message precedent dans cette conversation)"
    )

    ChatMessage.objects.create(
        user=request.user,
        conversation=conv,
        role=ChatMessage.ROLE_USER,
        text=question,
    )

    new_title = ((conv.title or "").strip() or question)[:200]
    ChatConversation.objects.filter(pk=conv.pk).update(title=new_title, updated_at=timezone.now())

    try:
        from .ai_deepseek import _call_groq

        base_candidates_qs = scope_owned_queryset(
            request,
            Candidat.objects.prefetch_related("candidatures__poste", "cvs"),
        )
        candidates_qs = base_candidates_qs.order_by("-created_at")[:120]
        postes_qs = scope_owned_queryset(request, Poste.objects.all()).order_by("-created_at")[:40]
        domains_qs = Domaine.objects.filter(actif=True).order_by("nom")

        def candidat_chat_row(candidat_obj):
            payload = candidate_summary_payload(candidat_obj)
            phone = (payload.get("phone") or "").strip()
            return {
                "id": payload.get("candidateId") or payload.get("id"),
                "nom": payload.get("fullName"),
                "email": (payload.get("email") or "").strip(),
                "telephone": phone or None,
                "poste": payload.get("targetJob") or "",
                "domaine": payload.get("domainName") or "",
                "statut": payload.get("statusLabel"),
                "score": payload.get("matchScore"),
                "localisation": (payload.get("location") or "").strip(),
                "titre_professionnel": (payload.get("currentTitle") or "").strip(),
                "annees_experience": payload.get("yearsExperience"),
                "niveau_etudes": (payload.get("educationLevel") or "").strip(),
                "resume_court": ((payload.get("summary") or "").strip())[:400],
            }

        candidate_rows = [candidat_chat_row(c) for c in candidates_qs]
        seen_ids = {row["id"] for row in candidate_rows}

        q_lower = question.lower()
        tokens = {m.group(0) for m in re.finditer(r"[\wÀ-ÿ'-]{3,}", q_lower, flags=re.UNICODE)}
        stop = {
            "les", "des", "une", "pour", "avec", "dans", "sur", "est", "son", "ses", "leur", "veux",
            "donne", "donner", "liste", "candidat", "candidats", "numero", "telephone", "email",
            "mail", "infos", "information", "informations", "toutes", "tous", "qui", "que", "quoi",
            "comment", "merci", "bonjour", "salut",
        }
        name_tokens = [t for t in tokens if t not in stop and not t.isdigit()]
        name_q = Q()
        for t in name_tokens[:12]:
            name_q |= Q(nom__icontains=t) | Q(prenom__icontains=t)
        if name_q:
            boosted = (
                base_candidates_qs.filter(name_q)
                .order_by("-created_at")
                .distinct()[:30]
            )
            boosted_rows = []
            for c in boosted:
                row = candidat_chat_row(c)
                rid = row["id"]
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    boosted_rows.append(row)
            candidate_rows = boosted_rows + candidate_rows

        poste_rows = [
            {
                "id": p.id,
                "titre": p.titre,
                "departement": p.departement,
                "priorite": p.niveau_priorite,
                "seuil": p.score_qualification,
            }
            for p in postes_qs
        ]
        domain_rows = [{"id": d.id, "nom": d.nom, "actif": d.actif} for d in domains_qs]

        system_prompt = (
            "Tu es TalentMatch IA, assistant intelligent pour des recruteurs RH connectés à leur base interne. "
            "Tu réponds en français, clairement. "
            "Si la question concerne les candidats/postes/domaines, appuie-toi prioritairement sur le contexte JSON fourni. "
            "Le contexte candidats contient notamment email et telephone lorsqu'ils sont enregistrés : "
            "tu DOIS les citer tels quels si l'utilisateur les demande et qu'ils figurent dans le contexte pour la bonne personne. "
            "Si un champ est absent ou null pour un candidat, dis simplement qu'il n'est pas renseigné en base (ne pas inventer). "
            "Si la question est générale, réponds avec des connaissances utiles. "
            "N'invente pas de scores, noms ou coordonnées qui ne sont pas dans le contexte. "
            "Tu réponds uniquement en JSON valide."
        )
        user_prompt = (
            "Retourne EXACTEMENT ce JSON:\n"
            "{\n"
            '  "answer": "réponse claire pour l’utilisateur",\n'
            '  "highlights": ["point 1", "point 2"],\n'
            '  "suggestedActions": ["action 1", "action 2"]\n'
            "}\n\n"
            "Historique recent de cette conversation (coherence du fil; ne pas repeter mot pour mot si inutile):\n"
            f"{history_block}\n\n"
            f"Question utilisateur actuelle: {question}\n\n"
            "Contexte candidats:\n"
            f"{json.dumps(candidate_rows, ensure_ascii=False)}\n\n"
            "Contexte postes:\n"
            f"{json.dumps(poste_rows, ensure_ascii=False)}\n\n"
            "Contexte domaines:\n"
            f"{json.dumps(domain_rows, ensure_ascii=False)}\n"
        )

        llm = _call_groq(system_prompt, user_prompt, max_tokens=1400)
        if not llm.get("ok"):
            fail_answer = "Le service IA est temporairement indisponible. Reessayez dans un instant."
            ChatMessage.objects.create(
                user=request.user,
                conversation=conv,
                role=ChatMessage.ROLE_ASSISTANT,
                text=fail_answer,
                highlights_json="[]",
                suggested_actions_json="[]",
            )
            ChatConversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())
            return Response(
                {
                    "answer": fail_answer,
                    "highlights": [],
                    "suggestedActions": [],
                    "ai_provider": llm.get("provider", "Grok"),
                    "conversationId": conv.id,
                },
                status=200,
            )

        data = llm.get("data") or {}
        answer_text = data.get("answer") or "Je n'ai pas de réponse exploitable pour le moment."
        highlights = data.get("highlights") or []
        suggested = data.get("suggestedActions") or []
        ChatMessage.objects.create(
            user=request.user,
            conversation=conv,
            role=ChatMessage.ROLE_ASSISTANT,
            text=answer_text,
            highlights_json=json.dumps(highlights, ensure_ascii=False),
            suggested_actions_json=json.dumps(suggested, ensure_ascii=False),
        )
        ChatConversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())
        return Response(
            {
                "answer": answer_text,
                "highlights": highlights,
                "suggestedActions": suggested,
                "ai_provider": llm.get("provider", "Grok"),
                "conversationId": conv.id,
            }
        )
    except Exception as exc:
        err_msg = f"Erreur chatbot: {exc}"
        ChatMessage.objects.create(
            user=request.user,
            conversation=conv,
            role=ChatMessage.ROLE_ASSISTANT,
            text=err_msg,
            highlights_json="[]",
            suggested_actions_json="[]",
        )
        ChatConversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())
        return Response({"error": err_msg, "conversationId": conv.id}, status=500)
