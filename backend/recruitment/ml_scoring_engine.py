"""
Pipeline ML avancé pour scoring et classification de CVs
==========================================================

Utilise :
  - TF-IDF : vectorisation du texte
  - Word2Vec (gensim) : embeddings vectoriels
  - XGBoost : classification et scoring robuste

Architecture :
  CVText → TF-IDF + Word2Vec → XGBoost → Score + Label
"""

import logging
import os
import pickle
import re
import unicodedata
from pathlib import Path
from typing import Optional
import numpy as np
from dataclasses import dataclass, field

# Machine Learning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import xgboost as xgb
try:
    from gensim.models import Word2Vec
    GENSIM_AVAILABLE = True
except Exception:
    Word2Vec = None
    GENSIM_AVAILABLE = False

logger = logging.getLogger(__name__)
if not GENSIM_AVAILABLE:
    logger.warning("gensim/Word2Vec indisponible: fallback sans similarite semantique W2V.")

# ─── Catalogue de compétences ─────────────────────────────────────────────────

SKILL_CATALOG: dict[str, list[str]] = {
    # Développement
    "python": ["python", "py"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi", "fast api"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "reactjs", "react.js"],
    "vue": ["vue", "vuejs", "vue.js"],
    "angular": ["angular"],
    "nodejs": ["node.js", "nodejs", "node"],
    "java": ["java"],
    "spring": ["spring", "spring boot"],
    "php": ["php"],
    "laravel": ["laravel"],
    "html": ["html", "html5"],
    "css": ["css", "css3", "sass", "scss"],
    # Données / IA
    "sql": ["sql", "mysql", "postgresql", "sqlite", "oracle", "t-sql"],
    "postgresql": ["postgresql", "postgres"],
    "mongodb": ["mongodb", "mongo"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "keras": ["keras"],
    "machine learning": ["machine learning", "ml", "apprentissage automatique"],
    "deep learning": ["deep learning", "dl", "apprentissage profond"],
    "nlp": ["nlp", "natural language processing", "traitement du langage"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "excel": ["excel", "vba"],
    "data analysis": ["data analysis", "analyse de données", "analyse de donnees"],
    # DevOps / Cloud
    "docker": ["docker", "conteneur", "container"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab", "bitbucket"],
    "aws": ["aws", "amazon web services", "s3", "ec2"],
    "azure": ["azure", "microsoft azure"],
    "linux": ["linux", "unix", "bash", "shell"],
    "ci/cd": ["ci/cd", "jenkins", "github actions", "gitlab ci"],
    # Marketing / Communication
    "marketing digital": ["marketing digital", "digital marketing"],
    "seo": ["seo", "sem", "référencement"],
    "communication": ["communication"],
    "social media": ["social media", "réseaux sociaux"],
    # Design
    "figma": ["figma"],
    "ui/ux": ["ui/ux", "ux design", "ui design", "user experience"],
}

EDUCATION_LEVELS = {
    "Doctorat": 5,
    "Master": 4,
    "Licence": 3,
    "DUT/BTS": 2,
    "Non précisé": 1,
}

EDUCATION_PATTERNS = [
    ("Doctorat", ["doctorat", "phd", "ph.d", "thèse"]),
    ("Master", ["master", "bac+5", "bac +5", "ingénieur", "ingenieur", "msc", "m.sc"]),
    ("Licence", ["licence", "bachelor", "bac+3", "bac +3", "l3", "l2"]),
    ("DUT/BTS", ["dut", "bts", "bac+2", "bac +2", "technicien"]),
]

# Regex patterns
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}")


# ─── Structures de résultat ────────────────────────────────────────────────────

@dataclass
class CVAnalysisResult:
    """Résultat complet de l'analyse ML d'un CV."""
    raw_text: str
    email: str
    phone: str
    full_name: str
    education_level: str
    years_experience: float
    detected_skills: list[str]
    summary: str
    
    # Scoring
    best_profile: str
    match_score: float  # 0–100
    profile_scores: dict[str, float] = field(default_factory=dict)
    tfidf_score: float = 0.0
    w2v_score: float = 0.0
    xgb_score: float = 0.0
    confidence: str = "moyen"  # faible / moyen / élevé
    recommendations: list[str] = field(default_factory=list)


# ─── Gestionnaire de modèles XGBoost ──────────────────────────────────────────

class XGBoostScoringManager:
    """Gère le modèle XGBoost pour le scoring des CVs."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.tfidf = TfidfVectorizer(max_features=500, stop_words='french')
        self.w2v_model = None
        self.model_dir: Optional[Path] = Path(model_path) if model_path else None
        self._model_stamp: tuple[float, float, float] | None = None
        
        if self.model_dir and self.model_dir.exists():
            self._load_models(str(self.model_dir))

    def _current_model_stamp(self) -> tuple[float, float, float]:
        """Retourne l'empreinte (mtime) des artifacts modèles."""
        if not self.model_dir:
            return (0.0, 0.0, 0.0)

        model_file = self.model_dir / "xgb_model.pkl"
        tfidf_file = self.model_dir / "tfidf_vectorizer.pkl"
        w2v_file = self.model_dir / "w2v_model.pkl"
        return (
            model_file.stat().st_mtime if model_file.exists() else 0.0,
            tfidf_file.stat().st_mtime if tfidf_file.exists() else 0.0,
            w2v_file.stat().st_mtime if w2v_file.exists() else 0.0,
        )

    def ensure_models_loaded(self) -> None:
        """
        Recharge automatiquement les modèles si les fichiers ont changé.
        Permet de prendre en compte un nouvel entraînement sans redémarrer le serveur.
        """
        if not self.model_dir or not self.model_dir.exists():
            return
        stamp = self._current_model_stamp()
        if self._model_stamp != stamp:
            self._load_models(str(self.model_dir))
    
    def _load_models(self, base_path: str):
        """Charge les modèles sauvegardés."""
        try:
            model_file = Path(base_path) / "xgb_model.pkl"
            tfidf_file = Path(base_path) / "tfidf_vectorizer.pkl"
            w2v_file = Path(base_path) / "w2v_model.pkl"
            
            if model_file.exists():
                with open(model_file, 'rb') as f:
                    self.model = pickle.load(f)
            
            if tfidf_file.exists():
                with open(tfidf_file, 'rb') as f:
                    self.tfidf = pickle.load(f)
            
            if w2v_file.exists():
                if GENSIM_AVAILABLE:
                    with open(w2v_file, 'rb') as f:
                        self.w2v_model = pickle.load(f)
                else:
                    self.w2v_model = None
                    
            self._model_stamp = self._current_model_stamp()
            logger.info("Modèles XGBoost chargés avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du chargement des modèles : {e}")
    
    def save_models(self, base_path: str):
        """Sauvegarde les modèles."""
        Path(base_path).mkdir(parents=True, exist_ok=True)
        
        if self.model:
            with open(Path(base_path) / "xgb_model.pkl", 'wb') as f:
                pickle.dump(self.model, f)
        
        with open(Path(base_path) / "tfidf_vectorizer.pkl", 'wb') as f:
            pickle.dump(self.tfidf, f)
        
        if self.w2v_model:
            with open(Path(base_path) / "w2v_model.pkl", 'wb') as f:
                pickle.dump(self.w2v_model, f)
    
    def compute_tfidf_score(self, cv_text: str, job_desc: str) -> float:
        """Calcule la similarité TF-IDF entre CV et description de poste."""
        self.ensure_models_loaded()
        try:
            vectors = self.tfidf.fit_transform([cv_text, job_desc])
            similarity = cosine_similarity(vectors[0], vectors[1])[0][0]
            return float(similarity * 100)  # 0-100
        except:
            return 0.0
    
    def compute_w2v_score(self, cv_tokens: list[str], job_tokens: list[str]) -> float:
        """Calcule la similarité Word2Vec."""
        self.ensure_models_loaded()
        if not self.w2v_model or not cv_tokens or not job_tokens:
            return 0.0
        
        try:
            # Moyennes des vecteurs
            cv_vec = np.mean([self.w2v_model.wv[t] for t in cv_tokens if t in self.w2v_model.wv], axis=0)
            job_vec = np.mean([self.w2v_model.wv[t] for t in job_tokens if t in self.w2v_model.wv], axis=0)
            
            if cv_vec.size == 0 or job_vec.size == 0:
                return 0.0
            
            similarity = cosine_similarity([cv_vec], [job_vec])[0][0]
            return float(similarity * 100)  # 0-100
        except:
            return 0.0
    
    def predict_score(self, features: np.ndarray) -> float:
        """Prédit le score avec XGBoost."""
        self.ensure_models_loaded()
        if self.model is None:
            # Modèle par défaut si pas d'entraînement
            return float(np.mean(features) * 100) if len(features) > 0 else 50.0
        
        try:
            # Cas 1: modèle sklearn XGBClassifier/XGBRegressor
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(features.reshape(1, -1))[0]
                # binaire: probabilité classe positive ; multi-classe: classe la plus probable
                score = proba[1] * 100.0 if len(proba) == 2 else (np.argmax(proba) / max(1, len(proba) - 1)) * 100.0
                return min(100.0, max(0.0, float(score)))

            # Cas 2: modèle xgboost.core.Booster (xgb.train)
            dmat = xgb.DMatrix(features.reshape(1, -1))
            pred = self.model.predict(dmat)
            if pred is None or len(pred) == 0:
                return 50.0

            # multi:softmax -> classe (0..n-1)
            value = float(pred[0])
            if value <= 10.0 and float(value).is_integer():
                num_class = 4  # cohérent avec train_models.py
                return min(100.0, max(0.0, (value / max(1, num_class - 1)) * 100.0))
            return min(100.0, max(0.0, value))
        except Exception as exc:
            logger.warning("XGBoost predict fallback: %s", exc)
            return 50.0


# Gestionnaire global
_xgb_manager = None

def get_xgb_manager():
    global _xgb_manager
    if _xgb_manager is None:
        model_dir = Path(__file__).parent / "models"
        _xgb_manager = XGBoostScoringManager(str(model_dir))
    return _xgb_manager


# ─── Extraction d'informations ────────────────────────────────────────────────

def extract_email(text: str) -> str:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
    m = PHONE_RE.search(text)
    return m.group(0).strip() if m else ""


def _normalize_skill_text(text: str) -> str:
    """Normalise le texte pour un matching de compétences plus fiable."""
    normalized = unicodedata.normalize("NFKD", (text or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[\r\n\t]+", " ", normalized)
    # Conserver les marqueurs utiles des compétences (c++, c#, node.js, ci/cd)
    normalized = re.sub(r"[^a-z0-9\s+#./-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _alias_pattern(alias: str) -> str:
    """Construit un pattern regex souple pour un alias de compétence."""
    parts = [p for p in re.split(r"[\s./_-]+", alias) if p]
    if not parts:
        return r"$^"
    escaped_parts = [re.escape(p) for p in parts]
    core = r"[\s./_-]*".join(escaped_parts)
    return rf"(?<![a-z0-9]){core}(?![a-z0-9])"


def extract_skills(text: str) -> list[str]:
    """
    Détecte les compétences via le catalogue.
    Matching robuste: accents supprimés, bornes de mots, séparateurs tolérés.
    """
    text_norm = _normalize_skill_text(text)
    found: list[str] = []

    for skill_key, aliases in SKILL_CATALOG.items():
        matched = False
        for alias in aliases:
            alias_norm = _normalize_skill_text(alias)
            if not alias_norm:
                continue
            if re.search(_alias_pattern(alias_norm), text_norm):
                matched = True
                break
        if matched:
            found.append(skill_key)
    return list(dict.fromkeys(found))


def extract_education(text: str) -> str:
    """Détecte le niveau d'études."""
    text_lower = text.lower()
    for label, patterns in EDUCATION_PATTERNS:
        if any(p in text_lower for p in patterns):
            return label
    return "Non précisé"


def estimate_experience(text: str) -> float:
    """Estime les années d'expérience."""
    # Méthode 1 : plage d'années
    years = sorted({int(y) for y in YEAR_RE.findall(text)})
    if len(years) >= 2:
        span = max(years) - min(years)
        if 0 < span <= 40:
            return float(min(span, 25))
    
    # Méthode 2 : mention explicite
    m = re.search(r"(\d{1,2})\s*\+?\s*ans?", text.lower())
    if m:
        return float(min(int(m.group(1)), 25))
    
    return 0.0


def guess_name(text: str, email: str = "", fallback: str = "Candidat Inconnu") -> str:
    """Devine le nom du candidat."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        first = re.sub(r"[^A-Za-zÀ-ÿ' \-]", " ", lines[0]).strip()
        words = [w for w in first.split() if len(w) > 1 and len(w) < 30]
        if 1 < len(words) <= 5:
            return " ".join(w.capitalize() for w in words)
    
    if email and "@" in email:
        name_part = email.split("@")[0].replace(".", " ").replace("_", " ")
        return " ".join(w.capitalize() for w in name_part.split() if w)
    
    return fallback


def preprocess_tokens(text: str) -> list[str]:
    """Tokenise et nettoie le texte."""
    text = text.lower()
    text = re.sub(r"[^a-záàâéèêëîïôùûüçœ0-9\s]", " ", text)
    tokens = [w for w in text.split() if len(w) > 2]
    return tokens


def compute_features(cv_text: str, job_desc: str = "") -> dict:
    """Calcule les features pour XGBoost."""
    manager = get_xgb_manager()
    
    cv_tokens = preprocess_tokens(cv_text)
    job_tokens = preprocess_tokens(job_desc) if job_desc else []
    
    skills = extract_skills(cv_text)
    education_level = extract_education(cv_text)
    years_exp = estimate_experience(cv_text)
    
    # TF-IDF
    tfidf_score = manager.compute_tfidf_score(cv_text, job_desc) if job_desc else 50.0
    
    # Word2Vec
    w2v_score = manager.compute_w2v_score(cv_tokens, job_tokens) if job_desc else 50.0
    
    # Features pour XGBoost
    features = {
        'tfidf_score': tfidf_score / 100.0,  # Normaliser 0-1
        'w2v_score': w2v_score / 100.0,
        'skills_count': len(skills) / 50.0,  # Normaliser
        'education_level': EDUCATION_LEVELS.get(education_level, 1) / 5.0,
        'years_experience': min(years_exp / 20.0, 1.0),  # Cap à 20 ans
        'skill_match': len(skills) > 0,  # Boolean
        'job_desc_provided': len(job_desc) > 0,  # Boolean
    }
    
    return features, cv_tokens, job_tokens, skills, education_level, years_exp


def _extract_min_experience(job_text: str) -> float:
    text = (job_text or "").lower()
    m = re.search(r"(\d{1,2})\s*\+?\s*ans?", text)
    if not m:
        return 0.0
    return float(min(int(m.group(1)), 25))


def _education_fit_score(candidate_level: str, job_text: str) -> float:
    level = candidate_level or "Non précisé"
    candidate_rank = EDUCATION_LEVELS.get(level, 1)
    text = (job_text or "").lower()
    required_rank = 1

    for label, patterns in EDUCATION_PATTERNS:
        if any(p in text for p in patterns):
            required_rank = max(required_rank, EDUCATION_LEVELS.get(label, 1))

    # Mieux calibré: pas de grosse pénalité si niveau juste en dessous.
    if candidate_rank >= required_rank:
        return 100.0
    if candidate_rank == required_rank - 1:
        return 78.0
    return 55.0


# ─── Analyse complète d'un CV ─────────────────────────────────────────────────

def analyze_cv_ml(cv_text: str, job_description: str = "", job_title: str = "") -> CVAnalysisResult:
    """
    Analyse un CV avec TF-IDF + Word2Vec + XGBoost.
    
    Paramètres
    ----------
    cv_text : str
        Texte brut du CV
    job_description : str
        Description optionnelle du poste cible
    job_title : str
        Titre optionnel du poste cible
    
    Retour
    ------
    CVAnalysisResult avec tous les détails d'analyse
    """
    manager = get_xgb_manager()
    
    # Extraction d'informations basiques
    email = extract_email(cv_text)
    phone = extract_phone(cv_text)
    full_name = guess_name(cv_text, email)
    skills = extract_skills(cv_text)
    education = extract_education(cv_text)
    years_exp = estimate_experience(cv_text)
    
    # Résumé rapide
    summary = f"{full_name} possède {years_exp:.0f} ans d'expérience avec {len(skills)} compétences détectées : {', '.join(skills[:5])}"
    if len(skills) > 5:
        summary += f" et {len(skills) - 5} autres."
    
    # Calcul des features
    features_dict, cv_tokens, job_tokens, _, _, _ = compute_features(cv_text, job_description)
    
    # Conversion en array pour XGBoost
    feature_array = np.array([
        features_dict['tfidf_score'],
        features_dict['w2v_score'],
        features_dict['skills_count'],
        features_dict['education_level'],
        features_dict['years_experience'],
    ]).reshape(1, -1)
    
    # Score XGBoost
    xgb_score = manager.predict_score(feature_array[0])
    
    # Scoring final adaptatif, orienté adéquation CV <-> poste.
    tfidf_pct = features_dict['tfidf_score'] * 100.0
    w2v_pct = features_dict['w2v_score'] * 100.0
    required_skills = set(extract_skills(f"{job_title or ''} {job_description or ''}"))
    candidate_skills = set(skills)
    matched_skills = required_skills & candidate_skills
    min_experience = _extract_min_experience(f"{job_title or ''} {job_description or ''}")

    if required_skills:
        skill_match_pct = (len(matched_skills) / max(1, len(required_skills))) * 100.0
    else:
        # Sans skills explicites dans la fiche, on valorise la richesse technique du CV.
        skill_match_pct = min(100.0, len(candidate_skills) * 12.0)

    if min_experience > 0:
        experience_fit_pct = min(100.0, (years_exp / min_experience) * 100.0)
    else:
        experience_fit_pct = min(100.0, 45.0 + years_exp * 11.0)

    education_fit_pct = _education_fit_score(education, f"{job_title or ''} {job_description or ''}")
    profile_strength_pct = min(100.0, (len(candidate_skills) * 8.0) + (years_exp * 6.0))

    if job_description:
        if GENSIM_AVAILABLE:
            raw_score = (
                tfidf_pct * 0.24
                + w2v_pct * 0.12
                + xgb_score * 0.18
                + skill_match_pct * 0.28
                + experience_fit_pct * 0.10
                + education_fit_pct * 0.05
                + profile_strength_pct * 0.03
            )
        else:
            raw_score = (
                tfidf_pct * 0.30
                + xgb_score * 0.20
                + skill_match_pct * 0.30
                + experience_fit_pct * 0.12
                + education_fit_pct * 0.05
                + profile_strength_pct * 0.03
            )

        # Calibration: évite le plafonnement artificiel autour de 60.
        match_score = (raw_score * 1.12) + 6.0
        if required_skills and len(matched_skills) == 0:
            match_score = min(match_score, 58.0)
        if required_skills and skill_match_pct >= 70 and experience_fit_pct >= 70:
            match_score += 5.0
    else:
        # Mode analyse générale (sans fiche poste): valoriser le potentiel du CV.
        match_score = (
            xgb_score * 0.45
            + profile_strength_pct * 0.30
            + education_fit_pct * 0.15
            + min(100.0, years_exp * 10.0) * 0.10
        )
    
    # Confiance
    if len(skills) > 5 and years_exp > 2:
        confidence = "élevée"
    elif len(skills) > 2 or years_exp > 0:
        confidence = "moyen"
    else:
        confidence = "faible"
    
    # Recommandations
    recommendations = []
    match_score = max(0.0, min(100.0, match_score))

    if match_score >= 75:
        recommendations.append("Candidat fortement recommandé")
    elif match_score >= 50:
        recommendations.append("Candidat intéressant")
    else:
        recommendations.append("Candidat à approfondir")
    
    if years_exp == 0:
        recommendations.append("Expérience non détectée - À vérifier")
    
    if len(skills) == 0:
        recommendations.append("Aucune compétence détectée - CV peu structuré")
    
    return CVAnalysisResult(
        raw_text=cv_text,
        email=email,
        phone=phone,
        full_name=full_name,
        education_level=education,
        years_experience=years_exp,
        detected_skills=skills,
        summary=summary,
        best_profile=job_title or "Profil générique",
        match_score=match_score,
        profile_scores={job_title or "match": match_score} if job_description else {},
        tfidf_score=tfidf_pct,
        w2v_score=w2v_pct,
        xgb_score=xgb_score,
        confidence=confidence,
        recommendations=recommendations,
    )


def score_cv_against_job(cv_text: str, job_title: str, job_description: str) -> dict:
    """
    Évalue la correspondance CV vs poste.
    
    Retour
    ------
    dict avec score, niveau, compétences matchées/manquantes, justification
    """
    result = analyze_cv_ml(cv_text, job_description, job_title)
    
    # Compétences manquantes (basé sur heuristiques)
    detected_skills = set(result.detected_skills)
    job_skills = set(extract_skills(job_description))
    
    matched = list(detected_skills & job_skills)
    missing = list(job_skills - detected_skills)
    
    # Niveau
    score = result.match_score
    if score >= 85:
        niveau = "Excellent"
    elif score >= 70:
        niveau = "Bon"
    elif score >= 50:
        niveau = "Moyen"
    else:
        niveau = "Faible"
    
    justification = f"Score TF-IDF: {result.tfidf_score:.0f}%, "
    justification += f"Word2Vec: {result.w2v_score:.0f}%, XGBoost: {result.xgb_score:.0f}%. "
    justification += f"Compétences matchées: {len(matched)}/{len(job_skills)}"
    
    return {
        'score': int(score),
        'niveau': niveau,
        'competences_matchees': matched,
        'competences_manquantes': missing,
        'justification': justification,
        'ia_disponible': True,
        'tfidf_score': result.tfidf_score,
        'w2v_score': result.w2v_score,
        'xgb_score': result.xgb_score,
        'confidence': result.confidence,
    }
