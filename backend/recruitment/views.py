import json
from datetime import datetime, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .ml_classifier import get_classifier
from .ai_engine import calculer_score_avance
from .models import Candidat, Candidature, CV, EmailLog, Poste, SyncHistory
from .serializers import (
    CVSerializer,
    CandidatSerializer,
    CandidatureSerializer,
    CreateUserSerializer,
    PosteSerializer,
    UserSerializer,
)

User = get_user_model()


STATUS_LABELS = {
    "nouveau": "Nouveau",
    "prequalifie": "Pre-qualifie",
    "shortlist": "Shortlist",
    "entretien": "Entretien",
    "finaliste": "Finaliste",
    "offre": "Offre",
    "en_cours": "En cours",
    "accepte": "Accepte",
    "refuse": "Refuse",
    "archive": "Archive",
}

STATUS_FLOW = [
    "nouveau",
    "prequalifie",
    "shortlist",
    "entretien",
    "finaliste",
    "offre",
    "accepte",
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
    return queryset.filter(**{owner_field: request.user})


def split_csv(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


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
        "entretien": "Entretien",
        "finaliste": "Decision finale",
        "offre": "Offre envoyee",
        "accepte": "Cloture",
        "refuse": "Cloture",
        "archive": "Archive",
        "en_cours": "Evaluation RH",
    }.get(status, "Evaluation RH")


def sla_due_for_status(status):
    now = timezone.now()
    hours = {
        "nouveau": 24,
        "prequalifie": 48,
        "shortlist": 72,
        "entretien": 7 * 24,
        "finaliste": 48,
        "offre": 72,
        "en_cours": 24,
    }.get(status, 72)
    return now + timedelta(hours=hours)


def parse_candidate_name(full_name):
    parts = [part for part in (full_name or "").split() if part]
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
        posts_qs = posts_qs.filter(created_by=owner)

    if explicit_job_id:
        try:
            return posts_qs.get(pk=explicit_job_id)
        except Poste.DoesNotExist:
            return None

    for poste in posts_qs:
        if poste.titre.lower() == (analysis.best_profile or "").lower():
            return poste
    return posts_qs.order_by("-created_at").first()


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
    candidature = candidat.candidatures.select_related("poste", "assigned_to").order_by("-updated_at").first()
    if candidature:
        return candidature_payload(candidature)
    cv = candidat.cvs.order_by("-created_at").first()
    return {
        "id": candidat.id,
        "candidateId": candidat.id,
        "fullName": f"{candidat.prenom} {candidat.nom}".strip(),
        "email": candidat.email,
        "phone": candidat.telephone,
        "location": candidat.localisation,
        "profileLabel": candidat.current_title or "Non classe",
        "currentTitle": candidat.current_title,
        "matchScore": 0.0,
        "status": "nouveau",
        "statusLabel": STATUS_LABELS["nouveau"],
        "recommendation": "A evaluer",
        "workflowStep": "Ingestion",
        "educationLevel": candidat.niveau_etudes or "Non precise",
        "yearsExperience": float(candidat.annees_experience or 0),
        "summary": candidat.resume_profil or (cv.texte_extrait[:240] if cv and cv.texte_extrait else ""),
        "skills": split_csv(candidat.competences),
        "languages": split_csv(candidat.langues),
        "softSkills": split_csv(candidat.soft_skills),
        "notes": "",
        "scoreDetails": {},
        "scoreExplanation": "",
        "source": candidat.source,
        "sourceEmail": cv.email_source if cv else candidat.source_detail,
        "cvUrl": cv.fichier.url if cv and cv.fichier else None,
        "cvFileName": cv.fichier.name.split("/")[-1] if cv and cv.fichier else None,
        "targetJob": "",
        "assignedTo": "",
        "slaDueAt": None,
        "createdAt": candidat.created_at.isoformat(),
        "updatedAt": candidat.created_at.isoformat(),
    }


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
@authentication_classes([])
@permission_classes([AllowAny])
def dashboard(request):
    try:
        q = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        profile_filter = request.GET.get("profile", "").strip()

        candidatures = scope_owned_queryset(
            request,
            Candidature.objects.select_related("candidat", "poste", "cv", "assigned_to"),
        )
        if q:
            candidatures = candidatures.filter(
                Q(candidat__nom__icontains=q)
                | Q(candidat__prenom__icontains=q)
                | Q(candidat__email__icontains=q)
                | Q(poste__titre__icontains=q)
            )
        if status_filter:
            candidatures = candidatures.filter(statut=status_filter)
        if profile_filter:
            candidatures = candidatures.filter(poste__titre=profile_filter)

        items = [candidature_payload(item) for item in candidatures.order_by("-updated_at")]
        scores = [item["matchScore"] for item in items if item["matchScore"] is not None]

        status_distribution = {
            row["statut"]: row["count"]
            for row in candidatures.values("statut").annotate(count=Count("id"))
        }
        profile_distribution = {
            row["poste__titre"] or "Non classe": row["count"]
            for row in candidatures.values("poste__titre").annotate(count=Count("id"))
        }

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
            if item["matchScore"] >= 85 and item["status"] in {"nouveau", "prequalifie", "en_cours"}
        ][:6]

        jobs_overview = []
        postes_qs = scope_owned_queryset(request, Poste.objects.all()).order_by("titre")
        candidats_qs = scope_owned_queryset(request, Candidat.objects.all())
        candidatures_global_qs = scope_owned_queryset(request, Candidature.objects.all())

        for poste in postes_qs:
            job_candidatures = candidatures.filter(poste=poste)
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
        for candidature in candidatures:
            if candidature.created_at and candidature.updated_at:
                processing_hours.append((candidature.updated_at - candidature.created_at).total_seconds() / 3600)
        overdue_count = len([c for c in candidatures if c.sla_due_at and c.sla_due_at < now and c.statut not in {"accepte", "refuse", "archive"}])

        return Response(
            {
                "stats": {
                    "totalApplications": candidatures_global_qs.count(),
                    "openJobs": postes_qs.filter(workflow_actif=True).count(),
                    "totalCandidates": candidats_qs.count(),
                    "averageScore": round(sum(scores) / len(scores), 1) if scores else 0,
                    "bestScore": round(max(scores), 1) if scores else 0,
                    "newCandidates": status_distribution.get("nouveau", 0),
                    "qualifiedCandidates": len([s for s in scores if s >= 70]),
                    "interviewsCount": status_distribution.get("entretien", 0) + status_distribution.get("finaliste", 0),
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
@authentication_classes([])
@permission_classes([AllowAny])
def candidates_list(request):
    candidats = scope_owned_queryset(
        request,
        Candidat.objects.prefetch_related("candidatures__poste", "candidatures__assigned_to", "cvs").all(),
    ).order_by("-created_at")
    items = [candidate_summary_payload(candidat) for candidat in candidats]
    return Response({"candidates": items})


@api_view(["GET"])
@authentication_classes([])
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


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def candidate_upload(request):
    try:
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

        prenom, nom = parse_candidate_name(analysis.full_name)
        email = unique_candidate_email(analysis.email or source_email)
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
            created_by=request.user if request.user.is_authenticated else None,
        )

        cv = CV.objects.create(
            candidat=candidat,
            fichier=cv_file,
            format_fichier=format_f,
            texte_extrait=analysis.raw_text or "",
            email_source=source_email,
        )

        poste = pick_target_job(
            analysis,
            explicit_job_id=target_job_id or None,
            owner=request.user if request.user.is_authenticated else None,
        )
        candidature = None
        if poste:
            score, details, explanation = score_candidate_against_job(analysis, poste)
            status = "shortlist" if score >= poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")
            candidature = Candidature.objects.create(
                candidat=candidat,
                poste=poste,
                cv=cv,
                statut=status,
                score=score,
                recommandation=recommendation_for_score(score),
                workflow_step=workflow_step_for_status(status),
                source_channel=source,
                explication_score=explanation,
                score_details_json=json.dumps(details),
                sla_due_at=sla_due_for_status(status),
                created_by=request.user if request.user.is_authenticated else None,
            )

        payload = candidate_summary_payload(candidat)
        if candidature:
            payload = candidature_payload(candidature)
        return Response({"candidate": payload}, status=201)
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["PATCH"])
@authentication_classes([])
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

    if status:
        candidature.statut = status
        candidature.workflow_step = workflow_step_for_status(status)
        candidature.sla_due_at = sla_due_for_status(status)
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

            score_result = calculer_score_avance(candidat_data, poste_data)
            score = float(score_result.get("score_final", 0.0))
            status = "shortlist" if score >= poste.score_qualification else ("prequalifie" if score >= 50 else "refuse")
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
@authentication_classes([])
@permission_classes([AllowAny])
def dossiers(request):
    try:
        result = []
        postes_qs = scope_owned_queryset(request, Poste.objects.all()).order_by("titre")
        for poste in postes_qs:
            candidatures = scope_owned_queryset(
                request,
                Candidature.objects.filter(poste=poste).select_related("candidat", "cv", "assigned_to"),
            )
            items = [candidature_payload(candidature) for candidature in candidatures]
            scores = [item["matchScore"] for item in items if item["matchScore"] is not None]
            result.append(
                {
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
            )
        return Response({"dossiers": result})
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def analyse_cv_ia(request):
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
        
        # Analyse avec ML (TF-IDF + Word2Vec + XGBoost)
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
            'ia_disponible': True,
            'methode': 'TF-IDF + Word2Vec + XGBoost',
            'confidence': result.confidence,
        })
    except Exception as exc:
        import traceback

        return Response({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def score_cv_ia(request):
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
        
        # Scoring avec ML (TF-IDF + Word2Vec + XGBoost)
        result = score_cv_against_job(cv_text, job_title, job_desc)
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
