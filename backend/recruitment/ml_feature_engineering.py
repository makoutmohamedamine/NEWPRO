import re
import unicodedata
from typing import Dict, List, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer, SnowballStemmer, WordNetLemmatizer
except Exception:  # pragma: no cover
    nltk = None
    stopwords = None
    PorterStemmer = None
    SnowballStemmer = None
    WordNetLemmatizer = None


EDUCATION_RANK = {
    "non precise": 0,
    "baccalaureat": 1,
    "bts": 2,
    "dut": 2,
    "licence": 3,
    "master": 4,
    "ingenieur": 4,
    "doctorat": 5,
    "phd": 5,
}

TECH_SKILL_HINTS = {
    "python",
    "django",
    "react",
    "java",
    "spring",
    "sql",
    "postgresql",
    "docker",
    "kubernetes",
    "sap",
    "hse",
    "qse",
    "maintenance",
    "lean",
    "production",
    "colorimetrie",
}

LANG_HINTS = {"francais", "francais", "french", "anglais", "english", "espagnol", "arabic", "arabe"}

_FR_STEMMER = SnowballStemmer("french") if SnowballStemmer else None
_EN_STEMMER = PorterStemmer() if PorterStemmer else None
_LEMMATIZER = WordNetLemmatizer() if WordNetLemmatizer else None


def _safe_download_nltk() -> None:
    if not nltk:
        return
    for pkg in ("stopwords", "wordnet", "omw-1.4"):
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass


_safe_download_nltk()
_STOPWORDS = set()
if stopwords:
    try:
        _STOPWORDS |= set(stopwords.words("french"))
        _STOPWORDS |= set(stopwords.words("english"))
    except Exception:
        _STOPWORDS = set()


def normalize_text(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s+#./-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_lang(text: str) -> str:
    t = normalize_text(text)
    fr_hits = len(re.findall(r"\b(le|la|les|des|pour|avec|ingenieur|experience)\b", t))
    en_hits = len(re.findall(r"\b(the|and|with|experience|engineer|skills)\b", t))
    return "fr" if fr_hits >= en_hits else "en"


def tokenize_clean(text: str, use_lemma: bool = True) -> List[str]:
    lang = detect_lang(text)
    tokens = re.findall(r"[a-z0-9+#./-]{2,}", normalize_text(text))
    out: List[str] = []
    for token in tokens:
        if token in _STOPWORDS and token not in TECH_SKILL_HINTS:
            continue
        normalized = token
        if use_lemma and _LEMMATIZER and lang == "en":
            normalized = _LEMMATIZER.lemmatize(normalized)
        elif lang == "fr" and _FR_STEMMER:
            normalized = _FR_STEMMER.stem(normalized)
        elif lang == "en" and _EN_STEMMER:
            normalized = _EN_STEMMER.stem(normalized)
        if len(normalized) >= 2:
            out.append(normalized)
    return out


def extract_experience_years(text: str) -> float:
    t = normalize_text(text)
    m = re.search(r"(\d{1,2})\s*\+?\s*(ans|years?)", t)
    if m:
        return float(min(int(m.group(1)), 30))
    return 0.0


def extract_education_rank(text: str) -> int:
    t = normalize_text(text)
    best = 0
    for keyword, rank in EDUCATION_RANK.items():
        if keyword in t:
            best = max(best, rank)
    return best


def extract_technical_skills(tokens: List[str]) -> List[str]:
    raw = {tok for tok in tokens if tok in TECH_SKILL_HINTS}
    return sorted(raw)


def extract_languages(tokens: List[str]) -> List[str]:
    raw = {tok for tok in tokens if tok in LANG_HINTS}
    return sorted(raw)


def infer_domain(text: str) -> str:
    t = normalize_text(text)
    mapping = [
        ("Production Industrielle", ["production", "usine", "industrie", "peinture", "coating"]),
        ("Maintenance", ["maintenance", "electromecanique", "mecanique"]),
        ("Qualite & Securite", ["qualite", "hse", "qse", "securite"]),
        ("Informatique & IT", ["python", "java", "react", "devops", "data"]),
        ("Ressources Humaines", ["rh", "recrutement", "talent"]),
        ("Finance & Comptabilite", ["finance", "comptabilite", "comptable"]),
        ("Marketing & Communication", ["marketing", "communication", "brand"]),
        ("Commerce & Vente", ["vente", "commercial", "sales"]),
        ("Logistique", ["logistique", "supply", "transport"]),
    ]
    for name, keys in mapping:
        if any(k in t for k in keys):
            return name
    return "Administration"


def dense_w2v_document_vector(tokens: List[str], w2v_model, tfidf_vocab: Dict[str, int], tfidf_vector) -> np.ndarray:
    if w2v_model is None:
        return np.zeros((200,), dtype=np.float32)
    weighted = []
    for token in tokens:
        if token in w2v_model.wv:
            idx = tfidf_vocab.get(token)
            weight = float(tfidf_vector[0, idx]) if idx is not None else 1.0
            weighted.append(w2v_model.wv[token] * max(weight, 1e-6))
    if not weighted:
        return np.zeros((w2v_model.vector_size,), dtype=np.float32)
    return np.mean(weighted, axis=0)


def handcrafted_features(cv_text: str, job_text: str) -> Tuple[np.ndarray, Dict[str, float]]:
    cv_tokens = tokenize_clean(cv_text)
    job_tokens = tokenize_clean(job_text)
    cv_skills = set(extract_technical_skills(cv_tokens))
    job_skills = set(extract_technical_skills(job_tokens))
    overlap = len(cv_skills & job_skills)
    required = max(1, len(job_skills))
    skill_ratio = overlap / required

    cv_lang = set(extract_languages(cv_tokens))
    job_lang = set(extract_languages(job_tokens))
    lang_ratio = len(cv_lang & job_lang) / max(1, len(job_lang)) if job_lang else (1.0 if cv_lang else 0.5)

    exp_cv = extract_experience_years(cv_text)
    exp_job = extract_experience_years(job_text)
    exp_ratio = min(1.0, exp_cv / max(1.0, exp_job)) if exp_job > 0 else min(1.0, exp_cv / 5.0)

    edu_cv = extract_education_rank(cv_text)
    edu_job = extract_education_rank(job_text)
    edu_ratio = 1.0 if edu_cv >= edu_job else max(0.0, edu_cv / max(1.0, edu_job))

    domain_match = 1.0 if infer_domain(cv_text) == infer_domain(job_text) else 0.0
    features = np.array([skill_ratio, lang_ratio, exp_ratio, edu_ratio, domain_match], dtype=np.float32)
    explain = {
        "skill_ratio": float(skill_ratio),
        "lang_ratio": float(lang_ratio),
        "exp_ratio": float(exp_ratio),
        "edu_ratio": float(edu_ratio),
        "domain_match": float(domain_match),
    }
    return features, explain


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(cosine_similarity(a.reshape(1, -1), b.reshape(1, -1))[0, 0])
