"""
Integration LLM Groq pour:
- extraction structuree de CV
- scoring CV vs poste
- recommandation de repartition (poste + domaine)
"""

import json
import logging
import os
import time
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)
_GROQ_COOLDOWN_UNTIL = 0.0

ALLOWED_DOMAINS = [
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


def _provider_config() -> Dict[str, str]:
    # Mode projet: Grok/Groq uniquement.
    provider = os.environ.get("AI_PROVIDER", "grok").strip().lower()
    if provider in {"groq", "grok"}:
        return {
            "provider": "grok",
            "display_name": "Grok",
            "api_key_env": "GROQ_API_KEY",
            "api_key": os.environ.get("GROQ_API_KEY", "").strip(),
            "api_url": os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
            "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        }
    # Fallback durci: si AI_PROVIDER invalide, rester sur Grok.
    return {
        "provider": "grok",
        "display_name": "Grok",
        "api_key_env": "GROQ_API_KEY",
        "api_key": os.environ.get("GROQ_API_KEY", "").strip(),
        "api_url": os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
        "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
    }


def groq_available() -> bool:
    cfg = _provider_config()
    key = cfg["api_key"]
    if not key:
        return False
    if key.startswith("votre-cle-") or key.endswith("-ici"):
        return False
    return True


def _extract_json(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    # Supprimer les balises markdown ```json ... ```
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue
    # Extraire le premier objet JSON {} dans le texte
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return json.loads(raw)


def _normalize_domain(value: str) -> str:
    domain = (value or "").strip()
    if domain in ALLOWED_DOMAINS:
        return domain
    lowered = domain.lower()
    mapping = {
        "it": "Informatique & IT",
        "informatique": "Informatique & IT",
        "rh": "Ressources Humaines",
        "hr": "Ressources Humaines",
        "finance": "Finance & Comptabilite",
        "comptabilite": "Finance & Comptabilite",
        "marketing": "Marketing & Communication",
        "communication": "Marketing & Communication",
        "commerce": "Commerce & Vente",
        "vente": "Commerce & Vente",
        "production": "Production Industrielle",
        "industrie": "Production Industrielle",
        "logistique": "Logistique",
        "maintenance": "Maintenance",
        "qualite": "Qualite & Securite",
        "securite": "Qualite & Securite",
        "administration": "Administration",
    }
    for key, canonical in mapping.items():
        if key in lowered:
            return canonical
    return "Administration"


def _rate_limit_error(provider: str, wait_seconds: int) -> Dict[str, Any]:
    wait_seconds = max(1, int(wait_seconds))
    return {
        "ok": False,
        "error": f"{provider} limite temporairement les requetes. Reessayez dans ~{wait_seconds}s.",
        "provider": provider,
        "error_code": "rate_limited",
        "retry_after_seconds": wait_seconds,
    }


def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 1800, force_json: bool = False) -> Dict[str, Any]:
    global _GROQ_COOLDOWN_UNTIL
    cfg = _provider_config()
    if not groq_available():
        return {"ok": False, "error": f"{cfg['api_key_env']} non configuree", "provider": cfg["display_name"]}

    now = time.time()
    if _GROQ_COOLDOWN_UNTIL > now:
        return _rate_limit_error(cfg["display_name"], int(_GROQ_COOLDOWN_UNTIL - now))

    try:
        request_payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if force_json:
            request_payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            cfg["api_url"],
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=60,
        )

        if response.status_code == 400:
            logger.warning("%s bad request (400): %s", cfg["display_name"], response.text[:300])
            return {"ok": False, "error": f"Requete invalide vers {cfg['display_name']}: {response.text[:200]}", "provider": cfg["display_name"]}

        if response.status_code == 401:
            logger.error("%s cle API invalide ou expiree (401). Veuillez renouveler GROQ_API_KEY dans .env", cfg["display_name"])
            return {
                "ok": False,
                "error": "Cle API Groq invalide ou expiree. Rendez-vous sur https://console.groq.com/keys pour obtenir une nouvelle cle, puis mettez a jour GROQ_API_KEY dans backend/.env",
                "provider": cfg["display_name"],
                "error_code": "invalid_api_key",
            }

        if response.status_code == 429:
            retry_header = response.headers.get("Retry-After", "30")
            try:
                retry_after = int(float(retry_header))
            except Exception:
                retry_after = 30
            _GROQ_COOLDOWN_UNTIL = max(_GROQ_COOLDOWN_UNTIL, time.time() + max(5, retry_after))
            logger.warning("%s rate limited (429), cooldown=%ss", cfg["display_name"], max(5, retry_after))
            return _rate_limit_error(cfg["display_name"], max(5, retry_after))

        response.raise_for_status()
        payload = response.json()
        raw = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            data = _extract_json(raw)
        except json.JSONDecodeError as exc:
            logger.warning("%s returned non-JSON content: %s", cfg["display_name"], raw[:300])
            return {
                "ok": False,
                "error": f"Reponse {cfg['display_name']} non JSON: {str(exc)[:120]}",
                "provider": cfg["display_name"],
                "error_code": "json_parse_error",
                "raw": raw,
            }
        return {"ok": True, "data": data, "raw": raw, "provider": cfg["display_name"]}
    except Exception as exc:
        logger.error("%s call failed: %s | type=%s", cfg["display_name"], exc, type(exc).__name__)
        return {
            "ok": False,
            "error": f"Echec service {cfg['display_name']}: {type(exc).__name__}: {str(exc)[:150]}",
            "provider": cfg["display_name"],
        }


def analyser_cv_groq(cv_text: str, job_description: str = "", job_title: str = "") -> Dict[str, Any]:
    system = (
        "Tu es un expert senior en ressources humaines et recrutement avec 15 ans d'experience. "
        "Ton role est d'analyser des CV de facon precise, objective et professionnelle. "
        "Tu DOIS extraire uniquement les informations REELLEMENT presentes dans le CV - ne jamais inventer ou supposer. "
        "Si une information n'est pas dans le CV, utilise une chaine vide ou 0. "
        "Reponds UNIQUEMENT en JSON valide strict, sans markdown, sans commentaire, sans texte supplementaire."
    )

    job_context = ""
    if job_title or job_description:
        job_context = f"""
POSTE CIBLE:
- Titre: {job_title or "Non specifie"}
- Description: {(job_description or "")[:2000]}

Instructions scoring: Evalue la compatibilite du candidat avec CE poste specifique.
- score_global = ponderation: competences techniques 40% + experience 25% + formation 20% + langues 10% + soft skills 5%
- Sois realiste: un candidat junior obtient 40-60, intermediaire 60-75, senior qualifie 75-90, expert parfait 90+
"""
    else:
        job_context = "\nPOSTE: Non specifie. Evalue le profil global du candidat objectivement."

    user = f"""Analyse ce CV de facon professionnelle et retourne EXACTEMENT ce JSON (toutes les valeurs extraites du CV reel):
{{
  "nom": "nom de famille exact du CV",
  "prenom": "prenom exact du CV",
  "email": "email exact du CV ou vide",
  "telephone": "telephone exact du CV ou vide",
  "adresse": "ville/pays si mentionnes ou vide",
  "niveau_etudes": "Bac+2/Bac+3/Bac+5/Master/Doctorat/Bac ou equivalent",
  "annees_experience": 0,
  "langues": ["langue1 (niveau)", "langue2 (niveau)"],
  "competences_techniques": ["competence1", "competence2"],
  "competences_soft": ["soft skill1", "soft skill2"],
  "formations": ["Diplome - Institution - Annee"],
  "experiences": ["Poste - Entreprise - Duree - Missions principales"],
  "resume_profil": "Resume professionnel objectif en 2-3 phrases basé sur le contenu réel du CV",
  "points_forts": ["point fort 1 concret", "point fort 2 concret", "point fort 3 concret"],
  "points_faibles": ["point faible 1 constructif", "point faible 2 constructif"],
  "score_global": 72,
  "recommandation": "A retenir",
  "justification_score": "Explication detaillee et argumentee du score avec reference aux elements du CV"
}}

Regles strictes:
- score_global: nombre entier entre 0 et 100, CALCULE rigoureusement selon l'experience et les competences reelles
- recommandation: exactement "A retenir" si score>=75, "Interessant" si score>=50, "Insuffisant" si score<50
- competences_techniques: liste les technologies/logiciels/frameworks EXACTEMENT mentionnes dans le CV
- annees_experience: calcule le total reel des annees travaillees
- formations et experiences: extrais les elements REELS du CV, ne pas inventer
- justification_score: doit expliquer le score avec des arguments concrets tires du CV
{job_context}

CV A ANALYSER:
{cv_text[:12000]}
"""
    result = _call_groq(system, user, max_tokens=2400)
    if not result["ok"]:
        return {"ia_disponible": False, "error": result["error"], "ai_provider": result.get("provider", "AI")}
    data = result["data"]
    data["ia_disponible"] = True
    data["methode"] = result.get("provider", "AI")
    data["ai_provider"] = result.get("provider", "AI")
    return data


def score_cv_contre_poste_groq(cv_text: str, job_title: str, job_description: str) -> Dict[str, Any]:
    system = (
        "Tu es un expert en matching RH avec une approche analytique rigoureuse. "
        "Tu evalues objectivement la compatibilite entre un CV et un poste. "
        "Tes scores sont bases sur les elements REELS du CV vs les exigences du poste. "
        "Reponds UNIQUEMENT en JSON valide strict, sans markdown ni texte supplementaire."
    )
    user = f"""Evalue la compatibilite entre ce CV et ce poste. Retourne EXACTEMENT ce JSON:
{{
  "score": 68,
  "score_competences": 70,
  "score_experience": 65,
  "score_formation": 75,
  "score_langues": 80,
  "score_domaine": 60,
  "niveau": "Bon",
  "competences_matchees": ["competence presente dans CV ET requise par le poste"],
  "competences_manquantes": ["competence requise par le poste ABSENTE du CV"],
  "justification": "Analyse detaillee du matching avec references aux elements concrets du CV et du poste"
}}

Methode de calcul rigoureuse:
- score_competences (poids 40%): % des competences cles du poste presentes dans le CV
- score_experience (poids 25%): adequation duree et nature experience vs exigences poste
- score_formation (poids 20%): adequation niveau et domaine formation vs exigences
- score_langues (poids 10%): langues requises presentes dans le CV
- score_domaine (poids 5%): coherence secteur/domaine candidat vs poste
- score final = somme ponderee des sous-scores (0-100, entier)
- niveau: "Excellent" si score>=85, "Bon" si score>=65, "Moyen" si score>=45, "Faible" si score<45
- competences_matchees: UNIQUEMENT les competences reellement presentes dans les deux
- competences_manquantes: competences cles du poste absentes du CV (max 5)
- justification: 2-3 phrases argumentant le score avec elements concrets

POSTE:
Titre: {job_title}
Description: {(job_description or "")[:2500]}

CV:
{cv_text[:9000]}
"""
    result = _call_groq(system, user, max_tokens=1400)
    if not result["ok"]:
        provider = result.get("provider", "AI")
        return {
            "score": 0,
            "niveau": "N/A",
            "competences_matchees": [],
            "competences_manquantes": [],
            "justification": f"{provider} indisponible",
            "ia_disponible": False,
            "ai_provider": provider,
        }
    data = result["data"]
    data["ia_disponible"] = True
    data["methode"] = result.get("provider", "AI")
    data["ai_provider"] = result.get("provider", "AI")
    try:
        score = float(data.get("score", 0) or 0)
        data["score"] = max(0.0, min(100.0, round(score, 1)))
    except Exception:
        pass
    return data


def recommander_repartition_cv_groq(cv_text: str, postes: List[Dict[str, Any]], domaines: List[str]) -> Dict[str, Any]:
    system = (
        "Tu es un expert en orientation et matching RH. "
        "Tu analyses les profils CV et identifies le meilleur poste et domaine correspondant. "
        "Tu bases ton choix sur les competences reelles, l'experience et la formation du candidat. "
        "Reponds UNIQUEMENT en JSON valide strict."
    )
    user = f"""Analyse ce CV et identifie le poste et domaine les plus adaptes au profil du candidat.

Retourne EXACTEMENT ce JSON:
{{
  "poste_titre": "titre exact de la liste des postes",
  "domaine": "domaine exact de la liste",
  "confiance": 78,
  "justification": "Explication concrete basee sur les competences et experience du candidat"
}}

Contraintes absolues:
- poste_titre DOIT etre un titre EXACT de la liste POSTES (copie exacte, meme casse)
- domaine DOIT etre un element EXACT de la liste DOMAINES (copie exacte)
- confiance entre 0 et 100 (reflete le niveau de certitude du matching)
- justification: 1-2 phrases expliquant pourquoi ce poste/domaine correspond au profil

POSTES DISPONIBLES:
{json.dumps(postes, ensure_ascii=False)}

DOMAINES DISPONIBLES:
{json.dumps(domaines, ensure_ascii=False)}

CV DU CANDIDAT:
{cv_text[:10000]}
"""
    result = _call_groq(system, user, max_tokens=1000)
    if not result["ok"]:
        return {"ia_disponible": False, "error": result["error"], "ai_provider": result.get("provider", "AI")}
    data = result["data"]
    data["ia_disponible"] = True
    data["ai_provider"] = result.get("provider", "AI")
    data["domaine"] = _normalize_domain(str(data.get("domaine", "")))
    return data


# Backward compatibility aliases (legacy names).
def deepseek_available() -> bool:
    return groq_available()


def _call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 1800) -> Dict[str, Any]:
    return _call_groq(system_prompt, user_prompt, max_tokens=max_tokens)


def analyser_cv_deepseek(cv_text: str, job_description: str = "", job_title: str = "") -> Dict[str, Any]:
    return analyser_cv_groq(cv_text, job_description=job_description, job_title=job_title)


def score_cv_contre_poste_deepseek(cv_text: str, job_title: str, job_description: str) -> Dict[str, Any]:
    return score_cv_contre_poste_groq(cv_text, job_title=job_title, job_description=job_description)


def recommander_repartition_cv(cv_text: str, postes: List[Dict[str, Any]], domaines: List[str]) -> Dict[str, Any]:
    return recommander_repartition_cv_groq(cv_text, postes=postes, domaines=domaines)
