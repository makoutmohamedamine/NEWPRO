import fitz  # PyMuPDF
import docx
import re
import nltk
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)

# ─── Extraction du texte ───────────────────────────────────────

def extraire_texte_pdf(chemin_fichier):
    textes_pages = []
    try:
        doc = fitz.open(chemin_fichier)
        for page in doc:
            text = (page.get_text("text") or "").strip()
            if not text:
                blocks = page.get_text("blocks") or []
                blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
                text = "\n".join((b[4] or "").strip() for b in blocks if len(b) > 4 and (b[4] or "").strip())
            if text:
                textes_pages.append(text)
    except Exception as e:
        print(f"Erreur PDF : {e}")
    texte = "\n".join(textes_pages).strip()
    if len(texte) < 40:
        print("Avertissement: texte PDF très court extrait (document possiblement scanné).")
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

# ─── SCORING AVANCÉ BASÉ SUR LES CRITÈRES DU POSTE ──────────────

def extraire_annees_experience(texte):
    """Extrait les années d'expérience approximativement du CV"""
    patterns = [
        r'(\d+)\s*(?:ans?|years?)\s*(?:d\')?(?:exp|expérience)',
        r'(?:exp|expérience).*?(\d+)\s*(?:ans?|years?)',
    ]
    texte_lower = texte.lower()
    for pattern in patterns:
        match = re.search(pattern, texte_lower)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
    return 0.0

def extraire_niveau_etudes(texte):
    """Extrait le niveau d'études du CV"""
    texte_lower = texte.lower()
    niveaux = {
        'doctorat': ['doctorat', 'phd', 'ph.d'],
        'master': ['master', 'mba', 'bac+5'],
        'licence': ['licence', 'bachelor', 'bac+3', 'bac+4'],
        'bts': ['bts', 'dut', 'bac+2'],
        'baccalaureat': ['baccalauréat', 'baccalaureat', 'bac general'],
    }
    for niveau, keywords in niveaux.items():
        for keyword in keywords:
            if keyword in texte_lower:
                return niveau
    return 'non_specifiee'

def comparer_competences(competences_cv, competences_requises, competences_optionnelles=None):
    """Compare les compétences du CV avec celles requises"""
    if competences_optionnelles is None:
        competences_optionnelles = []
    
    cv_lower = [c.lower().strip() for c in competences_cv]
    req_lower = [c.lower().strip() for c in (competences_requises or [])]
    opt_lower = [c.lower().strip() for c in (competences_optionnelles or [])]
    
    # Calcul des compétences correspondantes
    competences_matchees = [c for c in cv_lower if c in req_lower]
    competences_optionnelles_matchees = [c for c in cv_lower if c in opt_lower]
    
    score_competences = 0.0
    if req_lower:
        score_competences = (len(competences_matchees) / len(req_lower)) * 100
    
    return {
        'score_competences': score_competences,
        'competences_matchees': competences_matchees,
        'competences_manquantes': [c for c in req_lower if c not in cv_lower],
        'competences_optionnelles': competences_optionnelles_matchees,
    }

def calculer_score_avance(candidat_data, poste_data):
    """
    Calcul du score avancé basé sur plusieurs critères:
    - Compétences (poids_competences)
    - Expérience (poids_experience)
    - Formation (poids_formation)
    - Langues (poids_langues)
    - Localisation (poids_localisation)
    - Soft skills (poids_soft_skills)
    """
    try:
        # Extraction des données
        texte_cv = candidat_data.get('texte_cv', '')
        competences_cv = candidat_data.get('competences', [])
        langues_cv = [l.lower().strip() for l in (candidat_data.get('langues', '') or '').split(',') if l.strip()]
        soft_skills_cv = [s.lower().strip() for s in (candidat_data.get('soft_skills', '') or '').split(',') if s.strip()]
        experience_cv = candidat_data.get('annees_experience', 0)
        niveau_etudes_cv = candidat_data.get('niveau_etudes', '').lower()
        localisation_cv = (candidat_data.get('localisation', '') or '').lower().strip()
        
        # Données du poste
        competences_requises = [c.lower().strip() for c in (poste_data.get('competences_requises', '') or '').split(',') if c.strip()]
        competences_optionnelles = [c.lower().strip() for c in (poste_data.get('competences_optionnelles', '') or '').split(',') if c.strip()]
        langues_requises = [l.lower().strip() for l in (poste_data.get('langues_requises', '') or '').split(',') if l.strip()]
        experience_min = poste_data.get('experience_min_annees', 0)
        niveau_etudes_requis = poste_data.get('niveau_etudes_requis', '').lower()
        localisation_poste = (poste_data.get('localisation', '') or '').lower().strip()
        
        # Poids du scoring
        poids = {
            'competences': poste_data.get('poids_competences', 35),
            'experience': poste_data.get('poids_experience', 25),
            'formation': poste_data.get('poids_formation', 20),
            'langues': poste_data.get('poids_langues', 10),
            'localisation': poste_data.get('poids_localisation', 5),
            'soft_skills': poste_data.get('poids_soft_skills', 5),
        }
        
        total_poids = sum(poids.values())
        
        # SCORE COMPÉTENCES
        score_competences_det = comparer_competences(competences_cv, competences_requises, competences_optionnelles)
        score_competences = score_competences_det['score_competences']
        
        # Bonus pour compétences optionnelles
        if score_competences_det['competences_optionnelles']:
            score_competences = min(100, score_competences + (len(score_competences_det['competences_optionnelles']) * 5))
        
        # SCORE EXPÉRIENCE
        score_experience = 0.0
        if experience_min > 0:
            experience_ratio = min(1.0, experience_cv / experience_min)
            score_experience = experience_ratio * 100
        else:
            score_experience = 100.0 if experience_cv >= 0 else 0.0
        
        # SCORE FORMATION
        score_formation = 0.0
        niveaux_ordre = ['baccalaureat', 'bts', 'licence', 'master', 'doctorat']
        if niveau_etudes_requis:
            try:
                idx_requis = niveaux_ordre.index(niveau_etudes_requis)
                idx_cv = niveaux_ordre.index(niveau_etudes_cv) if niveau_etudes_cv in niveaux_ordre else -1
                
                if idx_cv >= idx_requis:
                    score_formation = 100.0
                elif idx_cv >= 0:
                    score_formation = max(0, ((idx_cv - idx_requis) / (len(niveaux_ordre) - 1)) * 100)
                else:
                    score_formation = 50.0  # Formation non spécifiée
            except:
                score_formation = 50.0
        else:
            score_formation = 100.0 if niveau_etudes_cv else 50.0
        
        # SCORE LANGUES
        score_langues = 0.0
        if langues_requises:
            langues_matchees = [l for l in langues_cv if l in langues_requises]
            score_langues = (len(langues_matchees) / len(langues_requises)) * 100
        else:
            score_langues = 100.0 if langues_cv else 50.0
        
        # SCORE LOCALISATION
        score_localisation = 0.0
        if localisation_poste:
            if localisation_cv == localisation_poste:
                score_localisation = 100.0
            else:
                score_localisation = 50.0  # Pas sur place mais peut être compatible
        else:
            score_localisation = 100.0
        
        # SCORE SOFT SKILLS
        score_soft_skills = 100.0 if soft_skills_cv else 50.0
        
        # CALCUL DU SCORE FINAL PONDÉRÉ
        score_final = (
            (score_competences * poids['competences']) +
            (score_experience * poids['experience']) +
            (score_formation * poids['formation']) +
            (score_langues * poids['langues']) +
            (score_localisation * poids['localisation']) +
            (score_soft_skills * poids['soft_skills'])
        ) / total_poids
        
        # Arrondir à 2 décimales
        score_final = round(float(score_final), 2)
        
        return {
            'score_final': score_final,
            'score_competences': round(score_competences, 2),
            'score_experience': round(score_experience, 2),
            'score_formation': round(score_formation, 2),
            'score_langues': round(score_langues, 2),
            'score_localisation': round(score_localisation, 2),
            'score_soft_skills': round(score_soft_skills, 2),
            'details': {
                'competences_matchees': score_competences_det['competences_matchees'],
                'competences_manquantes': score_competences_det['competences_manquantes'],
                'experience_annees': experience_cv,
                'experience_requise': experience_min,
                'niveau_etudes': niveau_etudes_cv,
                'niveau_requis': niveau_etudes_requis,
                'langues': langues_cv,
                'soft_skills': soft_skills_cv,
                'localisation': localisation_cv,
            }
        }
    except Exception as e:
        print(f"Erreur scoring avancé : {e}")
        return {
            'score_final': 0.0,
            'score_competences': 0.0,
            'score_experience': 0.0,
            'score_formation': 0.0,
            'score_langues': 0.0,
            'score_localisation': 0.0,
            'score_soft_skills': 0.0,
            'details': {'error': str(e)}
        }