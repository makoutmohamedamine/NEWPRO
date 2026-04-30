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
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
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


def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 1800) -> Dict[str, Any]:
    global _GROQ_COOLDOWN_UNTIL
    cfg = _provider_config()
    if not groq_available():
        return {"ok": False, "error": f"{cfg['api_key_env']} non configuree", "provider": cfg["display_name"]}

    now = time.time()
    if _GROQ_COOLDOWN_UNTIL > now:
        return _rate_limit_error(cfg["display_name"], int(_GROQ_COOLDOWN_UNTIL - now))

    try:
        response = requests.post(
            cfg["api_url"],
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
            timeout=40,
        )

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
        data = _extract_json(raw)
        return {"ok": True, "data": data, "provider": cfg["display_name"]}
    except Exception as exc:
        logger.warning("%s call failed: %s", cfg["display_name"], exc)
        return {
            "ok": False,
            "error": f"Echec temporaire du service {cfg['display_name']}.",
            "provider": cfg["display_name"],
        }


def analyser_cv_groq(cv_text: str, job_description: str = "", job_title: str = "") -> Dict[str, Any]:
    system = (
        "Tu es un expert RH. Reponds uniquement en JSON valide, sans markdown, sans texte annexe."
    )
    user = f"""
Retourne un JSON avec EXACTEMENT ces champs:
{{
  "nom": "",
  "prenom": "",
  "email": "",
  "telephone": "",
  "adresse": "",
  "niveau_etudes": "",
  "annees_experience": 0,
  "langues": [],
  "competences_techniques": [],
  "competences_soft": [],
  "formations": [],
  "experiences": [],
  "resume_profil": "",
  "points_forts": [],
  "points_faibles": [],
  "score_global": 0,
  "recommandation": "",
  "justification_score": ""
}}

Regles:
- score_global entre 0 et 100
- recommandation: "À retenir" si score>=75, "Intéressant" si score>=50, sinon "Insuffisant"
- pas de null, seulement string/list/number

POSTE:
- titre: {job_title or "N/A"}
- description: {job_description or "N/A"}

CV:
{cv_text[:10000]}
"""
    result = _call_groq(system, user, max_tokens=1800)
    if not result["ok"]:
        return {"ia_disponible": False, "error": result["error"], "ai_provider": result.get("provider", "AI")}
    data = result["data"]
    data["ia_disponible"] = True
    data["methode"] = result.get("provider", "AI")
    data["ai_provider"] = result.get("provider", "AI")
    return data


def score_cv_contre_poste_groq(cv_text: str, job_title: str, job_description: str) -> Dict[str, Any]:
    system = "Tu es un expert matching RH. Reponds uniquement en JSON valide."
    user = f"""
Retourne EXACTEMENT ce JSON:
{{
  "score": 0,
  "score_competences": 0,
  "score_experience": 0,
  "score_formation": 0,
  "score_langues": 0,
  "score_domaine": 0,
  "niveau": "",
  "competences_matchees": [],
  "competences_manquantes": [],
  "justification": ""
}}

Regles:
- score entre 0 et 100
- niveau = Excellent/Bon/Moyen/Faible
- score doit etre calcule de facon professionnelle (pas de score arbitraire)
- utiliser une logique de pondération réaliste :
  competences 45%, experience 20%, formation 10%, langues 10%, domaine 15%
- fournir les sous-scores (0-100)

POSTE:
Titre: {job_title}
Description: {job_description}

CV:
{cv_text[:9000]}
"""
    result = _call_groq(system, user, max_tokens=1200)
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
        # Calibration légère pour éviter un plafonnement artificiel.
        score = float(data.get("score", 0) or 0)
        data["score"] = max(0.0, min(100.0, round((score * 1.08) + 3.0, 1)))
    except Exception:
        pass
    return data


def recommander_repartition_cv_groq(cv_text: str, postes: List[Dict[str, Any]], domaines: List[str]) -> Dict[str, Any]:
    system = "Tu classes des CV pour un ATS RH. Reponds uniquement en JSON valide."
    user = f"""
Choisis le meilleur poste et domaine.

Retourne EXACTEMENT:
{{
  "poste_titre": "",
  "domaine": "",
  "confiance": 0,
  "justification": ""
}}

Contraintes:
- poste_titre doit etre un titre EXACT issu de cette liste
- domaine doit etre un element EXACT issu de cette liste
- confiance entre 0 et 100

POSTES:
{json.dumps(postes, ensure_ascii=False)}

DOMAINES:
{json.dumps(domaines, ensure_ascii=False)}

CV:
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
