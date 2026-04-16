import fitz  # PyMuPDF
import docx
import re
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)

# ─── Extraction du texte ───────────────────────────────────────

def extraire_texte_pdf(chemin_fichier):
    texte = ""
    try:
        doc = fitz.open(chemin_fichier)
        for page in doc:
            texte += page.get_text()
    except Exception as e:
        print(f"Erreur PDF : {e}")
    return texte

def extraire_texte_docx(chemin_fichier):
    texte = ""
    try:
        doc = docx.Document(chemin_fichier)
        for para in doc.paragraphs:
            texte += para.text + "\n"
    except Exception as e:
        print(f"Erreur DOCX : {e}")
    return texte

def extraire_texte(chemin_fichier, format_fichier):
    if format_fichier == 'pdf':
        return extraire_texte_pdf(chemin_fichier)
    elif format_fichier == 'docx':
        return extraire_texte_docx(chemin_fichier)
    return ""

# ─── Extraction des infos clés ────────────────────────────────

def extraire_email(texte):
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    resultats = re.findall(pattern, texte)
    return resultats[0] if resultats else ""

def extraire_telephone(texte):
    pattern = r'(\+?\d[\d\s\-().]{7,}\d)'
    resultats = re.findall(pattern, texte)
    return resultats[0].strip() if resultats else ""

def extraire_competences(texte):
    competences_connues = [
        'python', 'django', 'flask', 'javascript', 'react', 'vue', 'angular',
        'java', 'spring', 'sql', 'postgresql', 'mongodb', 'mysql',
        'machine learning', 'deep learning', 'nlp', 'tensorflow', 'pytorch',
        'docker', 'kubernetes', 'git', 'linux', 'aws', 'azure',
        'html', 'css', 'php', 'laravel', 'nodejs', 'express',
        'data analysis', 'scikit-learn', 'pandas', 'numpy',
    ]
    texte_lower = texte.lower()
    trouvees = [c for c in competences_connues if c in texte_lower]
    return trouvees

# ─── Nettoyage du texte ───────────────────────────────────────

def nettoyer_texte(texte):
    texte = texte.lower()
    texte = re.sub(r'[^a-záàâéèêëîïôùûüç\s]', ' ', texte)
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte

# ─── Scoring par similarité cosinus ──────────────────────────

def calculer_score(texte_cv, description_poste):
    if not texte_cv or not description_poste:
        return 0.0
    try:
        texte_cv_clean = nettoyer_texte(texte_cv)
        poste_clean = nettoyer_texte(description_poste)
        vectorizer = TfidfVectorizer()
        vecteurs = vectorizer.fit_transform([texte_cv_clean, poste_clean])
        score = cosine_similarity(vecteurs[0], vecteurs[1])[0][0]
        return round(float(score) * 100, 2)
    except Exception as e:
        print(f"Erreur scoring : {e}")
        return 0.0

# ─── Analyse complète d'un CV ─────────────────────────────────

def analyser_cv(chemin_fichier, format_fichier, description_poste=""):
    texte = extraire_texte(chemin_fichier, format_fichier)
    return {
        'texte_extrait': texte,
        'email': extraire_email(texte),
        'telephone': extraire_telephone(texte),
        'competences': extraire_competences(texte),
        'score': calculer_score(texte, description_poste) if description_poste else None,
    }   