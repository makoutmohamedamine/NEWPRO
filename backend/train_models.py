#!/usr/bin/env python3
"""
Script d'entraînement des modèles XGBoost pour le scoring de CVs
=================================================================

Entraîne les modèles machine learning :
  - TF-IDF Vectorizer
  - Word2Vec (gensim)
  - XGBoost Classifier

Données de test synthétiques incluses pour démarrage rapide.
Pour améliorer la qualité : ajouter des données d'entraînement réelles
"""

import os
import sys
import logging
from pathlib import Path
import pickle
import numpy as np

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_models():
    """Entraîne les modèles ML."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from gensim.models import Word2Vec
        import xgboost as xgb
        from recruitment.ml_scoring_engine import preprocess_tokens
    except ImportError as e:
        logger.error(f"Dépendances manquantes : {e}")
        logger.info("Installez les dépendances : pip install xgboost gensim scikit-learn")
        sys.exit(1)
    
    logger.info("🚀 Démarrage de l'entraînement des modèles...")
    
    # ─── Données d'entraînement synthétiques ──────────────────────────────────
    # En production, utilisez des données réelles
    
    training_texts = [
        "Développeur Python Django REST API SQL PostgreSQL 5 ans expérience",
        "Data Scientist Machine Learning TensorFlow Scikit-learn Pandas 3 ans",
        "Ingénieur DevOps Docker Kubernetes AWS CI/CD 4 ans Linux",
        "Full Stack JavaScript React Node.js MongoDB 6 ans HTML CSS",
        "Manager RH Recrutement Leadership Communication 8 ans",
        "Développeur Java Spring Boot Microservices 4 ans",
        "Data Analyst SQL Power BI Excel Analytics 2 ans",
        "Frontend React TypeScript UI/UX Design 3 ans",
        "Administrateur Linux Bash Shell Networking 5 ans",
        "Consultant IT Agile Scrum Project Management 7 ans",
    ]
    
    # Labels synthétiques (0: faible, 1: moyen, 2: bon, 3: excellent)
    training_labels = np.array([2, 2, 2, 2, 1, 2, 1, 1, 2, 1])
    
    # ─── Entraînement TF-IDF ──────────────────────────────────────────────────
    logger.info("📊 Entraînement TF-IDF Vectorizer...")
    tfidf = TfidfVectorizer(
        max_features=500,
        stop_words='french',
        min_df=1,
        max_df=0.9
    )
    tfidf_features = tfidf.fit_transform(training_texts)
    logger.info(f"✅ TF-IDF : {tfidf_features.shape}")
    
    # ─── Entraînement Word2Vec ────────────────────────────────────────────────
    logger.info("🧠 Entraînement Word2Vec...")
    tokenized_texts = [preprocess_tokens(text) for text in training_texts]
    w2v_model = Word2Vec(
        sentences=tokenized_texts,
        vector_size=100,
        window=5,
        min_count=1,
        workers=4,
        epochs=10
    )
    logger.info(f"✅ Word2Vec : {len(w2v_model.wv)} mots")
    
    # ─── Extraction de features pour XGBoost ──────────────────────────────────
    logger.info("🔧 Extraction des features XGBoost...")
    X_train = []
    
    for text in training_texts:
        tokens = preprocess_tokens(text)
        
        # Feature 1: TF-IDF score (moyenne)
        tfidf_vec = tfidf.transform([text])
        tfidf_score = tfidf_vec.mean()
        
        # Feature 2: Word2Vec score (moyenne des embeddings)
        w2v_vecs = [w2v_model.wv[t] for t in tokens if t in w2v_model.wv]
        w2v_score = np.mean(w2v_vecs) if w2v_vecs else 0.0
        
        # Features 3-5: Complexité du texte
        vocab_size = len(set(tokens))
        text_length = len(text.split())
        token_diversity = vocab_size / max(text_length, 1)
        
        X_train.append([
            tfidf_score,
            w2v_score,
            vocab_size / 50.0,        # Normaliser
            text_length / 100.0,      # Normaliser
            token_diversity,
        ])
    
    X_train = np.array(X_train)
    logger.info(f"✅ Features XGBoost : shape {X_train.shape}")
    
    # ─── Entraînement XGBoost ─────────────────────────────────────────────────
    logger.info("🎯 Entraînement XGBoost...")
    dtrain = xgb.DMatrix(X_train, label=training_labels)
    
    params = {
        'objective': 'multi:softmax',
        'num_class': 4,
        'max_depth': 5,
        'eta': 0.1,
        'eval_metric': 'mlogloss',
    }
    
    xgb_model = xgb.train(params, dtrain, num_boost_round=100, verbose_eval=False)
    logger.info("✅ XGBoost entraîné")
    
    # ─── Sauvegarde des modèles ───────────────────────────────────────────────
    logger.info("💾 Sauvegarde des modèles...")
    model_dir = Path(__file__).parent / "recruitment" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    with open(model_dir / "tfidf_vectorizer.pkl", 'wb') as f:
        pickle.dump(tfidf, f)
    logger.info(f"✅ TF-IDF sauvegardé : {model_dir / 'tfidf_vectorizer.pkl'}")
    
    with open(model_dir / "w2v_model.pkl", 'wb') as f:
        pickle.dump(w2v_model, f)
    logger.info(f"✅ Word2Vec sauvegardé : {model_dir / 'w2v_model.pkl'}")
    
    xgb_model.save_model(str(model_dir / "xgb_model.json"))
    with open(model_dir / "xgb_model.pkl", 'wb') as f:
        pickle.dump(xgb_model, f)
    logger.info(f"✅ XGBoost sauvegardé : {model_dir / 'xgb_model.pkl'}")
    
    logger.info("🎉 Entraînement terminé avec succès!")
    return True


if __name__ == "__main__":
    try:
        train_models()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erreur : {e}", exc_info=True)
        sys.exit(1)
