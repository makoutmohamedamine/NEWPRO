"""
Pipeline ML de classification et scoring de CVs
================================================
Combine plusieurs techniques pour un scoring robuste :

1. TF-IDF + similarité cosinus (matching texte libre)
2. Règles métier pondérées (compétences, expérience, diplôme)
3. Score composite final normalisé sur 100

Architecture :
  CVText → Prétraitement → [TF-IDF | Règles] → Fusion → Score + Label
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

import fitz          # PyMuPDF
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# ─── Téléchargement silencieux des ressources NLTK ─────────────────────────────
for _resource in ("stopwords", "punkt", "punkt_tab"):
    try:
        nltk.download(_resource, quiet=True)
    except Exception:
        pass

try:
    from nltk.corpus import stopwords as _sw
    _STOPWORDS_FR = set(_sw.words("french"))
    _STOPWORDS_EN = set(_sw.words("english"))
    STOPWORDS = _STOPWORDS_FR | _STOPWORDS_EN
except Exception:
    STOPWORDS = set()


# ─── Catalogue de compétences ───────────────────────────────────────────────────

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

# ─── Profils de postes par défaut ──────────────────────────────────────────────

DEFAULT_JOB_PROFILES: dict[str, dict] = {
    "Développeur Full Stack": {
        "skills": ["python", "django", "react", "javascript", "sql", "html", "css", "git"],
        "weight": 1.0,
        "min_experience": 2,
    },
    "Data Analyst": {
        "skills": ["sql", "python", "pandas", "excel", "power bi", "data analysis", "tableau"],
        "weight": 1.0,
        "min_experience": 1,
    },
    "Ingénieur IA/NLP": {
        "skills": ["python", "machine learning", "nlp", "scikit-learn", "tensorflow", "pytorch", "deep learning"],
        "weight": 1.0,
        "min_experience": 2,
    },
    "Marketing Digital": {
        "skills": ["marketing digital", "seo", "communication", "social media", "excel"],
        "weight": 1.0,
        "min_experience": 1,
    },
    "Développeur Backend": {
        "skills": ["python", "django", "flask", "fastapi", "sql", "docker", "git", "linux"],
        "weight": 1.0,
        "min_experience": 2,
    },
    "DevOps / Cloud": {
        "skills": ["docker", "kubernetes", "aws", "azure", "linux", "ci/cd", "git"],
        "weight": 1.0,
        "min_experience": 2,
    },
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

YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}")


# ─── Structures de résultat ─────────────────────────────────────────────────────

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
    match_score: float                         # 0–100
    profile_scores: dict[str, float] = field(default_factory=dict)  # tous les scores
    tfidf_score: float = 0.0
    rule_score: float = 0.0
    confidence: str = "faible"                 # faible / moyen / élevé


# ─── Extraction de texte ────────────────────────────────────────────────────────

def extract_text_from_bytes(content: bytes, filename: str) -> str:
    """Extrait le texte brut d'un fichier PDF ou DOCX (depuis bytes)."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(content)
    if ext in (".docx", ".doc"):
        return _extract_docx(content)
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_pdf(data: bytes) -> str:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages_text = []
        for page in doc:
            text = (page.get_text("text") or "").strip()
            if not text:
                # Fallback: reconstruction depuis les blocs si extraction "text" vide.
                blocks = page.get_text("blocks") or []
                blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
                text = "\n".join((b[4] or "").strip() for b in blocks if len(b) > 4 and (b[4] or "").strip())
            if text:
                pages_text.append(text)

        final_text = "\n".join(pages_text).strip()
        if len(final_text) < 40:
            logger.warning("Texte PDF très court extrait: document possiblement scanné/image.")
        return final_text
    except Exception as exc:
        logger.warning("Erreur extraction PDF : %s", exc)
        return ""


def _extract_docx(data: bytes) -> str:
    try:
        import zipfile
        from io import BytesIO
        from xml.etree import ElementTree

        with zipfile.ZipFile(BytesIO(data)) as z:
            xml = z.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for para in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            text = "".join(
                node.text or ""
                for node in para.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
            )
            if text.strip():
                paragraphs.append(text.strip())
        return "\n".join(paragraphs)
    except Exception as exc:
        logger.warning("Erreur extraction DOCX : %s", exc)
        return ""


# ─── Prétraitement NLP ──────────────────────────────────────────────────────────

def preprocess(text: str) -> str:
    """Nettoie et normalise le texte pour TF-IDF."""
    text = text.lower()
    # Supprimer les caractères spéciaux sauf lettres, chiffres, espaces
    text = re.sub(r"[^a-záàâéèêëîïôùûüçœ0-9\s/+#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Supprimer les stopwords
    tokens = [w for w in text.split() if w not in STOPWORDS and len(w) > 1]
    return " ".join(tokens)


# ─── Extracteurs d'informations ─────────────────────────────────────────────────

def normalize_cv_text(text: str) -> str:
    """Nettoie les artefacts frequents d'extraction PDF."""
    text = (text or "").replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_email(text: str) -> str:
    text = normalize_cv_text(text)
    candidates = re.findall(r"[A-Za-z0-9._%+\-]+\s*@\s*[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    return candidates[0].replace(" ", "") if candidates else ""


def extract_phone(text: str) -> str:
    text = normalize_cv_text(text)
    candidates = re.findall(r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}", text)
    for value in candidates:
        digits = re.sub(r"\D", "", value)
        if 9 <= len(digits) <= 15:
            return value.strip()
    return ""


def _normalize_skill_text(text: str) -> str:
    """Normalise le texte pour améliorer la détection des compétences."""
    normalized = unicodedata.normalize("NFKD", (text or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[\r\n\t]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\s+#./-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _alias_pattern(alias: str) -> str:
    parts = [p for p in re.split(r"[\s./_-]+", alias) if p]
    if not parts:
        return r"$^"
    escaped_parts = [re.escape(p) for p in parts]
    core = r"[\s./_-]*".join(escaped_parts)
    return rf"(?<![a-z0-9]){core}(?![a-z0-9])"


def extract_skills(text: str) -> list[str]:
    """Détecte les compétences via le catalogue avec matching robuste."""
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
    text_lower = text.lower()
    for label, patterns in EDUCATION_PATTERNS:
        if any(p in text_lower for p in patterns):
            return label
    return "Non précisé"


def estimate_experience(text: str) -> float:
    """
    Estime les années d'expérience à partir :
    1. Des années détectées dans le texte (plage min-max)
    2. Des mentions explicites ("5 ans d'expérience")
    """
    # Méthode 1 : plage d'années
    years = sorted({int(y) for y in YEAR_RE.findall(text)})
    if len(years) >= 2:
        span = max(years) - min(years)
        if 0 < span <= 40:
            return float(min(span, 25))

    # Méthode 2 : mention explicite
    m = re.search(r"(\d{1,2})\s*\+?\s*an", text.lower())
    if m:
        return float(min(int(m.group(1)), 25))

    return 0.0


def guess_name(text: str, email: str, fallback: str = "Candidat Inconnu") -> str:
    """Devine le nom du candidat depuis la première ligne non vide."""
    text = normalize_cv_text(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        for line in lines[:6]:
            cleaned = re.sub(r"[^A-Za-zÀ-ÿ' \-]", " ", line).strip()
            words = [w for w in cleaned.split() if 1 < len(w) < 30]
            if 1 < len(words) <= 4 and not any(k in cleaned.lower() for k in ["curriculum", "vitae", "resume", "cv"]):
                return " ".join(w.capitalize() for w in words)
    if email:
        local = email.split("@")[0].replace(".", " ").replace("_", " ")
        return " ".join(p.capitalize() for p in local.split())
    return fallback


# ─── Scoring TF-IDF ─────────────────────────────────────────────────────────────

def tfidf_score(cv_text: str, job_description: str) -> float:
    """Calcule la similarité cosinus TF-IDF entre le CV et la description du poste."""
    if not cv_text.strip() or not job_description.strip():
        return 0.0
    try:
        clean_cv = preprocess(cv_text)
        clean_jd = preprocess(job_description)
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        matrix = vectorizer.fit_transform([clean_cv, clean_jd])
        score = cosine_similarity(matrix[0], matrix[1])[0][0]
        return round(float(score) * 100, 2)
    except Exception as exc:
        logger.warning("Erreur TF-IDF : %s", exc)
        return 0.0


# ─── Scoring par règles ─────────────────────────────────────────────────────────

def rule_based_score(
    detected_skills: list[str],
    education_level: str,
    years_experience: float,
    job_profile: dict,
) -> float:
    """
    Score basé sur des règles métier pondérées :
      - 65% compétences (ratio overlap)
      - 20% expérience
      - 15% diplôme
    """
    required_skills = set(job_profile.get("skills", []))
    min_exp = job_profile.get("min_experience", 0)

    if not required_skills:
        return 50.0

    # Compétences (65%)
    overlap = len(set(detected_skills) & required_skills)
    skill_ratio = overlap / len(required_skills)
    skill_score = skill_ratio * 65.0

    # Expérience (20%)
    if years_experience >= min_exp * 2:
        exp_score = 20.0
    elif years_experience >= min_exp:
        exp_score = 15.0
    elif years_experience > 0:
        exp_score = 8.0
    else:
        exp_score = 0.0

    # Diplôme (15%)
    edu_weight = EDUCATION_LEVELS.get(education_level, 1)
    edu_score = min(15.0, edu_weight * 3.0)

    total = skill_score + exp_score + edu_score
    return round(min(total, 100.0), 2)


# ─── Classificateur principal ────────────────────────────────────────────────────

class CVClassifier:
    """
    Classificateur ML de CVs.
    Combine TF-IDF et règles métier pour scorer et classer chaque CV
    par rapport aux profils de postes disponibles.
    """

    def __init__(self, job_profiles: dict[str, dict] | None = None):
        self._profiles = job_profiles or DEFAULT_JOB_PROFILES

    def analyse(
        self,
        cv_bytes: bytes,
        filename: str,
        sender_email: str = "",
        sender_name: str = "",
    ) -> CVAnalysisResult:
        """
        Analyse complète d'un CV :
        1. Extraction du texte
        2. Parsing des informations
        3. Scoring multi-profils
        4. Sélection du meilleur profil
        """
        raw_text = extract_text_from_bytes(cv_bytes, filename)
        return self.analyse_text(raw_text, sender_email=sender_email, sender_name=sender_name)

    def analyse_text(
        self,
        raw_text: str,
        sender_email: str = "",
        sender_name: str = "",
    ) -> CVAnalysisResult:
        raw_text = normalize_cv_text(raw_text)
        # ── 1. Extraction des informations ──────────────────────────────────────
        email = extract_email(raw_text) or sender_email
        phone = extract_phone(raw_text)
        skills = extract_skills(raw_text)
        education = extract_education(raw_text)
        experience = estimate_experience(raw_text)
        name = guess_name(raw_text, email, fallback=sender_name or "Candidat Inconnu")
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        summary = " ".join(lines[:4])[:300]

        # ── 2. Scoring multi-profils ────────────────────────────────────────────
        profile_scores: dict[str, float] = {}

        for profile_name, profile_data in self._profiles.items():
            # Description synthétique du poste pour TF-IDF
            job_desc = profile_name + " " + " ".join(profile_data.get("skills", []))

            t_score = tfidf_score(raw_text, job_desc)
            r_score = rule_based_score(skills, education, experience, profile_data)

            # Fusion pondérée : 40% TF-IDF + 60% règles métier
            combined = round(t_score * 0.40 + r_score * 0.60, 2)
            profile_scores[profile_name] = combined

        # ── 3. Sélection du meilleur profil ─────────────────────────────────────
        if profile_scores:
            best_profile = max(profile_scores, key=lambda k: profile_scores[k])
            best_score = profile_scores[best_profile]
        else:
            best_profile = "Profil généraliste"
            best_score = 30.0

        # Recalculer les scores partiels pour le meilleur profil
        best_profile_data = self._profiles.get(best_profile, {})
        best_job_desc = best_profile + " " + " ".join(best_profile_data.get("skills", []))
        best_tfidf = tfidf_score(raw_text, best_job_desc)
        best_rule = rule_based_score(skills, education, experience, best_profile_data)

        # ── 4. Niveau de confiance ───────────────────────────────────────────────
        if best_score >= 70:
            confidence = "élevé"
        elif best_score >= 45:
            confidence = "moyen"
        else:
            confidence = "faible"

        return CVAnalysisResult(
            raw_text=raw_text,
            email=email,
            phone=phone,
            full_name=name,
            education_level=education,
            years_experience=experience,
            detected_skills=skills,
            summary=summary,
            best_profile=best_profile,
            match_score=best_score,
            profile_scores=profile_scores,
            tfidf_score=best_tfidf,
            rule_score=best_rule,
            confidence=confidence,
        )

    def score_against_job(
        self,
        cv_text: str,
        job_skills: list[str],
        job_name: str = "",
        job_description: str = "",
        min_experience: int = 0,
    ) -> float:
        """
        Score un CV contre un poste spécifique (fourni par l'utilisateur).
        Utilisé pour le scoring manuel lors de l'upload depuis l'interface.
        """
        skills = extract_skills(cv_text)
        education = extract_education(cv_text)
        experience = estimate_experience(cv_text)

        profile_data = {
            "skills": job_skills,
            "min_experience": min_experience,
        }

        job_desc = (job_description or job_name) + " " + " ".join(job_skills)
        t_score = tfidf_score(cv_text, job_desc)
        r_score = rule_based_score(skills, education, experience, profile_data)

        return round(t_score * 0.40 + r_score * 0.60, 2)

    def load_profiles_from_db(self) -> None:
        """Charge les profils de postes depuis la base de données Django."""
        try:
            from .models import Poste
            db_profiles = {}
            for poste in Poste.objects.all():
                keywords = [
                    kw.strip().lower()
                    for kw in poste.competences_requises.split(",")
                    if kw.strip()
                ]
                db_profiles[poste.titre] = {
                    "skills": keywords,
                    "weight": 1.0,
                    "min_experience": 0,
                    "description": poste.description,
                }
            if db_profiles:
                self._profiles = db_profiles
                logger.info("Profils chargés depuis la DB : %s", list(db_profiles.keys()))
        except Exception as exc:
            logger.warning("Impossible de charger les profils depuis la DB : %s", exc)


# ─── Instance partagée ──────────────────────────────────────────────────────────

_classifier: CVClassifier | None = None


def get_classifier() -> CVClassifier:
    """Retourne l'instance partagée du classificateur (singleton)."""
    global _classifier
    if _classifier is None:
        _classifier = CVClassifier()
        _classifier.load_profiles_from_db()
    return _classifier
