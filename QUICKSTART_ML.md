# ⚡ Démarrage Rapide - ML Scoring (TF-IDF + Word2Vec + XGBoost)

## Qu'est-ce qui a changé?

❌ **Avant :** Claude IA (API Anthropic) pour scorer les CVs  
✅ **Après :** Machine Learning local (TF-IDF + Word2Vec + XGBoost)

**Bénéfices immédits :**
- 🚀 **20-30x plus rapide** (~100ms vs 3-5s)
- 💰 **Gratuit** (zéro coût API)
- 🔒 **Privé** (données locales)
- ⚙️ **Customizable** (modèles personnalisables)

---

## 📦 Installation (2 minutes)

### 1️⃣ Installer les dépendances

```bash
cd backend

# Installer tous les packages (recommandé)
pip install -r requirements.txt

# Ou seulement les nouveaux packages ML
pip install xgboost gensim numpy scikit-learn
```

### 2️⃣ Entraîner les modèles

```bash
python train_models.py
```

**Attendre le message :** `🎉 Entraînement terminé avec succès!`

Cela crée 3 fichiers dans `recruitment/models/` :
- `tfidf_vectorizer.pkl` (~1 MB)
- `w2v_model.pkl` (~5 MB)
- `xgb_model.pkl` (~1 MB)

### 3️⃣ Démarrer le serveur

```bash
python manage.py runserver
```

---

## 🧪 Test rapide

### Via l'API

```bash
# 1. Upload & analyse un CV
curl -X POST http://localhost:8000/api/analyse-cv-ia/ \
  -F "cv=@mon_cv.pdf" \
  -F "job_title=Développeur Python"

# 2. Réponse exemple (instant !)
{
  "score_global": 82,
  "niveau": "Excellent",
  "justification_score": "TF-IDF: 78%, Word2Vec: 85%, XGBoost: 82%",
  "ia_disponible": true,
  "methode": "TF-IDF + Word2Vec + XGBoost"
}
```

### Via Python

```python
from recruitment.ml_scoring_engine import analyze_cv_ml

cv_text = "Développeur Python Django 5 ans expérience"
result = analyze_cv_ml(cv_text, "Senior Python Developer")

print(f"Score: {result.match_score:.0f}%")
print(f"Compétences: {result.detected_skills}")
print(f"Confiance: {result.confidence}")
```

---

## 📚 Architecture Simplifiée

```
CV (PDF/DOCX)
    ↓ [Extract text]
    ↓
┌─ TF-IDF (40%) ──┐
├─ Word2Vec (30%)┤ → Score composite (0-100)
└─ XGBoost (30%) ┘
    ↓
    Résultat JSON avec justification
```

---

## ❓ FAQ

### Q: Comment le score est calculé?
A: Fusion de 3 techniques ML :
- **TF-IDF** : Similarité textuelle CV ↔ Description
- **Word2Vec** : Similarité sémantique (embeddings)
- **XGBoost** : Classification avec features complexes

### Q: Pourquoi 3 modèles?
A: Pour robustesse et couverture :
- TF-IDF = rapide, basé mots-clés
- Word2Vec = sémantique, variations vocabulaire
- XGBoost = patterns complexes, non-linéarité

### Q: Combien de CVs peuvent être traités?
A: **Illimité** ! Aucune limite API.

### Q: Comment améliorer les scores?
A: Réentraîner avec données réelles :
```python
# Dans train_models.py
training_texts = [cv.texte_extrait for cv in CVs réels]
training_labels = [score assigné par RH]
```

### Q: Que faire si les scores sont trop bas?
A: 
1. Vérifier extraction du texte CV
2. Augmenter volume données d'entraînement
3. Réentraîner : `python train_models.py`

---

## 🔧 Commandes utiles

```bash
# Réentraîner les modèles
python train_models.py

# Voir la taille des modèles
ls -lh recruitment/models/

# Tester import
python -c "from recruitment.ml_scoring_engine import analyze_cv_ml; print('✅ OK')"

# Logs détaillés
export DEBUG=1
python manage.py runserver --verbosity 2
```

---

## 📖 Documentation complète

Voir : [MIGRATION_CLAUDE_TO_ML.md](../MIGRATION_CLAUDE_TO_ML.md)

---

## ✅ Checklist démarrage

- [ ] Installer dépendances (`pip install -r requirements.txt`)
- [ ] Entraîner modèles (`python train_models.py`)
- [ ] Vérifier fichiers modèles dans `recruitment/models/`
- [ ] Démarrer serveur (`python manage.py runserver`)
- [ ] Tester endpoint `/api/analyse-cv-ia/`
- [ ] Vérifier score en <200ms
- [ ] Célébrer ! 🎉

---

## ⚠️ Troubleshooting

| Problème | Solution |
|----------|----------|
| `ImportError: No module named 'xgboost'` | `pip install xgboost` |
| `FileNotFoundError: recruitment/models/` | `python train_models.py` |
| Score toujours = 50 | Vérifier extraction texte CV |
| Score réponse lent | Vérifier CPU, relancer serveur |

---

**Besoin d'aide?** Voir MIGRATION_CLAUDE_TO_ML.md pour documentation complète.
