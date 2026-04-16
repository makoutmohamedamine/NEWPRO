"""
Module d'analyse de CV par Intelligence Artificielle (Claude d'Anthropic).

Fonctions principales :
  - analyser_cv_claude(cv_text, job_description)  → dict avec toutes les infos extraites
  - score_cv_contre_poste(cv_text, job_title, job_description) → score + justification

Le module se dégrade gracieusement si la clé API n'est pas configurée :
il retourne alors des données vides plutôt que de lever une exception.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# ── Client Anthropic (lazy init) ───────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key or api_key == 'votre-cle-api-anthropic-ici':
                logger.warning("ANTHROPIC_API_KEY non configurée — analyse IA désactivée.")
                return None
            _client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.error("Package 'anthropic' non installé. Lancez : pip install anthropic")
            return None
    return _client


# ── Prompt système ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un expert RH spécialisé dans l'analyse de CV.
Tu extrais des informations structurées et tu évalues les candidats avec précision.
Tu réponds UNIQUEMENT en JSON valide, sans texte supplémentaire ni balises markdown."""


# ── Analyse complète d'un CV ──────────────────────────────────────────────────

def analyser_cv_claude(cv_text: str, job_description: str = "", job_title: str = "") -> dict:
    """
    Analyse un CV en texte brut avec Claude et retourne un dict structuré.

    Paramètres
    ----------
    cv_text : str
        Texte extrait du CV (PDF ou DOCX).
    job_description : str
        Description du poste cible (optionnel).
    job_title : str
        Titre du poste cible (optionnel).

    Retour
    ------
    dict avec les clés :
        nom, prenom, email, telephone, adresse,
        niveau_etudes, annees_experience, langues,
        competences_techniques, competences_soft,
        formations, experiences,
        resume_profil, points_forts, points_faibles,
        score_global (0-100, si poste fourni),
        recommandation, justification_score,
        ia_disponible (bool)
    """
    client = _get_client()
    if client is None:
        return _resultat_vide(ia_disponible=False)

    # Construire le prompt
    poste_block = ""
    if job_title or job_description:
        poste_block = f"""
--- POSTE CIBLE ---
Titre : {job_title or 'Non précisé'}
Description : {job_description or 'Non précisée'}
-------------------
"""

    prompt = f"""Analyse le CV suivant et retourne un objet JSON avec exactement ces champs :

{{
  "nom": "...",
  "prenom": "...",
  "email": "...",
  "telephone": "...",
  "adresse": "...",
  "niveau_etudes": "Bac / Bac+2 / Bac+3 / Bac+5 / Doctorat / Autre",
  "annees_experience": 0,
  "langues": ["Français", "Anglais"],
  "competences_techniques": ["Python", "Django", ...],
  "competences_soft": ["Communication", "Travail en équipe", ...],
  "formations": [
    {{"diplome": "...", "etablissement": "...", "annee": "..."}}
  ],
  "experiences": [
    {{"poste": "...", "entreprise": "...", "duree": "...", "description": "..."}}
  ],
  "resume_profil": "Résumé professionnel en 2-3 phrases.",
  "points_forts": ["...", "..."],
  "points_faibles": ["...", "..."],
  "score_global": 0,
  "recommandation": "À retenir / Intéressant / Insuffisant",
  "justification_score": "Explication courte du score."
}}

Règles :
- score_global : de 0 à 100. Si aucun poste cible n'est fourni, utilise 50 comme base neutre.
- recommandation : "À retenir" si score ≥ 75, "Intéressant" si 50-74, "Insuffisant" si < 50.
- Toutes les valeurs manquantes → chaîne vide ou liste vide, jamais null.
- Réponds UNIQUEMENT avec le JSON, aucun texte avant ou après.
{poste_block}
--- CV ---
{cv_text[:6000]}
---------"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Nettoyer les éventuels blocs markdown ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        data['ia_disponible'] = True
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Claude a retourné un JSON invalide : {e}")
        return _resultat_vide(ia_disponible=True, erreur="Réponse IA non parseable")
    except Exception as e:
        logger.error(f"Erreur appel Claude : {e}")
        return _resultat_vide(ia_disponible=True, erreur=str(e))


# ── Score ciblé contre un poste ───────────────────────────────────────────────

def score_cv_contre_poste(cv_text: str, job_title: str, job_description: str) -> dict:
    """
    Calcule un score de correspondance entre un CV et un poste précis.

    Retour
    ------
    dict :
        score (int 0-100), niveau ("Excellent" / "Bon" / "Moyen" / "Faible"),
        competences_matchees (list), competences_manquantes (list),
        justification (str), ia_disponible (bool)
    """
    client = _get_client()
    if client is None:
        return {
            'score': 0, 'niveau': 'N/A',
            'competences_matchees': [], 'competences_manquantes': [],
            'justification': 'IA non disponible', 'ia_disponible': False,
        }

    prompt = f"""Évalue la correspondance entre ce CV et le poste proposé.
Retourne UNIQUEMENT ce JSON :

{{
  "score": 0,
  "niveau": "Excellent / Bon / Moyen / Faible",
  "competences_matchees": ["...", "..."],
  "competences_manquantes": ["...", "..."],
  "justification": "Explication en 2-3 phrases."
}}

Règles pour le score (0-100) :
- 85-100 : profil idéal, maîtrise toutes les compétences requises
- 70-84  : très bon profil, quelques points mineurs manquants
- 50-69  : profil correct, lacunes non bloquantes
- 30-49  : profil partiel, plusieurs compétences clés absentes
- 0-29   : profil inadapté au poste

--- POSTE ---
Titre : {job_title}
Description : {job_description[:2000]}
-------------

--- CV ---
{cv_text[:4000]}
---------"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        data['ia_disponible'] = True
        return data

    except Exception as e:
        logger.error(f"Erreur score_cv_contre_poste : {e}")
        return {
            'score': 0, 'niveau': 'Erreur',
            'competences_matchees': [], 'competences_manquantes': [],
            'justification': str(e), 'ia_disponible': True,
        }


# ── Résultat vide (fallback) ──────────────────────────────────────────────────

def _resultat_vide(ia_disponible: bool = False, erreur: str = "") -> dict:
    return {
        'nom': '', 'prenom': '', 'email': '', 'telephone': '', 'adresse': '',
        'niveau_etudes': '', 'annees_experience': 0, 'langues': [],
        'competences_techniques': [], 'competences_soft': [],
        'formations': [], 'experiences': [],
        'resume_profil': '', 'points_forts': [], 'points_faibles': [],
        'score_global': 0, 'recommandation': '', 'justification_score': '',
        'ia_disponible': ia_disponible,
        'erreur': erreur,
    }
