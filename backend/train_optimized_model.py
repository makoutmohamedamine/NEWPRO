#!/usr/bin/env python3
"""
Training pipeline IA optimisee pour matching CV <-> poste.

Usage:
  python train_optimized_model.py --dataset data/matching_dataset.csv
"""

import argparse
import csv
import json
import pickle
from pathlib import Path
from typing import Dict, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

try:
    from gensim.models import Word2Vec
except Exception:
    Word2Vec = None

from recruitment.ml_feature_engineering import (
    cosine,
    dense_w2v_document_vector,
    handcrafted_features,
    tokenize_clean,
)


def load_dataset(dataset_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cv_text = row.get("cv_text", "").strip()
            job_text = row.get("job_text", "").strip()
            if not cv_text or not job_text:
                continue
            row["label"] = int(row.get("label", "0"))
            rows.append(row)
    if not rows:
        raise ValueError("Dataset vide ou colonnes manquantes (cv_text, job_text, label).")
    return rows


def _safe_split(X: np.ndarray, y: np.ndarray):
    """
    Split robuste pour petits datasets:
    - utilise stratify seulement si chaque classe a au moins 2 échantillons
    - garantit une taille de test >= nombre de classes
    """
    n_samples = len(y)
    classes, counts = np.unique(y, return_counts=True)
    n_classes = len(classes)
    min_count = int(np.min(counts))

    stratify = y if min_count >= 2 else None
    test_size = max(n_classes, int(round(n_samples * 0.2)))
    test_size = min(test_size, max(1, n_samples - n_classes))
    if test_size <= 0:
        test_size = 1

    return train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=42,
        stratify=stratify,
    )


def build_features(rows: List[Dict[str, str]]):
    cv_texts = [r["cv_text"] for r in rows]
    job_texts = [r["job_text"] for r in rows]
    labels = np.array([int(r["label"]) for r in rows], dtype=np.int32)

    tfidf = TfidfVectorizer(
        max_features=25000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    tfidf.fit(cv_texts + job_texts)
    cv_tfidf = tfidf.transform(cv_texts)
    job_tfidf = tfidf.transform(job_texts)
    tfidf_cosines = np.array(
        [cosine(cv_tfidf[i].toarray().ravel(), job_tfidf[i].toarray().ravel()) for i in range(len(rows))],
        dtype=np.float32,
    )

    tokenized_corpus = [tokenize_clean(t) for t in (cv_texts + job_texts)]
    w2v_model = None
    w2v_cosines = np.zeros((len(rows),), dtype=np.float32)
    if Word2Vec is not None:
        w2v_model = Word2Vec(
            sentences=tokenized_corpus,
            vector_size=200,
            window=5,
            min_count=2,
            workers=4,
            sg=1,
            epochs=20,
        )
        vocab = tfidf.vocabulary_
        for i in range(len(rows)):
            cv_tokens = tokenize_clean(cv_texts[i])
            job_tokens = tokenize_clean(job_texts[i])
            cv_vec = dense_w2v_document_vector(cv_tokens, w2v_model, vocab, cv_tfidf[i])
            job_vec = dense_w2v_document_vector(job_tokens, w2v_model, vocab, job_tfidf[i])
            w2v_cosines[i] = cosine(cv_vec, job_vec)

    handcrafted = []
    for i in range(len(rows)):
        feats, _ = handcrafted_features(cv_texts[i], job_texts[i])
        handcrafted.append(feats)
    handcrafted_arr = np.vstack(handcrafted).astype(np.float32)

    X = np.hstack(
        [
            tfidf_cosines.reshape(-1, 1),
            w2v_cosines.reshape(-1, 1),
            handcrafted_arr,
        ]
    ).astype(np.float32)
    return X, labels, tfidf, w2v_model


def train_and_evaluate(X: np.ndarray, y: np.ndarray):
    x_train, x_test, y_train, y_test = _safe_split(X, y)
    scaler = StandardScaler()
    x_train_s = scaler.fit_transform(x_train)
    x_test_s = scaler.transform(x_test)

    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=4,
        tree_method="hist",
    )
    param_dist = {
        "n_estimators": [200, 400, 600, 800],
        "learning_rate": [0.01, 0.03, 0.05, 0.1],
        "max_depth": [3, 4, 5, 6],
        "min_child_weight": [1, 3, 5],
        "subsample": [0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.7, 0.8, 0.9, 1.0],
        "reg_alpha": [0.0, 0.3, 0.5, 1.0],
        "reg_lambda": [1.0, 1.5, 2.0, 3.0],
    }
    class_counts = np.unique(y_train, return_counts=True)[1]
    min_class_count = int(np.min(class_counts)) if len(class_counts) > 0 else 1
    if min_class_count < 2:
        # Dataset trop petit pour cross-validation stratifiée.
        best = model.set_params(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            min_child_weight=1,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_alpha=0.3,
            reg_lambda=1.5,
        )
        best.fit(x_train_s, y_train)
        best_params = best.get_params()
        best_cv_f1 = None
        n_splits = 0
    else:
        n_splits = max(2, min(5, min_class_count))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        search = RandomizedSearchCV(
            model,
            param_distributions=param_dist,
            n_iter=25,
            scoring="f1",
            cv=cv,
            n_jobs=2,
            verbose=1,
            random_state=42,
        )
        search.fit(x_train_s, y_train)
        best = search.best_estimator_
        best_params = search.best_params_
        best_cv_f1 = float(search.best_score_)
    y_pred = best.predict(x_test_s)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(y_test, y_pred, zero_division=0),
        "best_params": best_params,
        "cv_best_f1": best_cv_f1,
        "cv_splits": int(n_splits),
    }
    return best, scaler, metrics


def save_artifacts(output_dir: Path, tfidf, w2v_model, scaler, model, metrics: Dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "optimized_tfidf.pkl").open("wb") as f:
        pickle.dump(tfidf, f)
    with (output_dir / "optimized_scaler.pkl").open("wb") as f:
        pickle.dump(scaler, f)
    with (output_dir / "optimized_xgb.pkl").open("wb") as f:
        pickle.dump(model, f)
    if w2v_model is not None:
        with (output_dir / "optimized_w2v.pkl").open("wb") as f:
            pickle.dump(w2v_model, f)
    with (output_dir / "optimized_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path CSV dataset with columns: cv_text,job_text,label")
    parser.add_argument("--output", default="recruitment/models_optimized", help="Output directory for artifacts")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    rows = load_dataset(dataset_path)
    labels = [int(r["label"]) for r in rows]
    class_counts = {int(c): int(v) for c, v in zip(*np.unique(labels, return_counts=True))}
    if len(class_counts) < 2:
        raise ValueError("Le dataset doit contenir au moins 2 classes de labels.")

    if Word2Vec is None:
        print("[INFO] gensim indisponible: entraînement sans Word2Vec (fallback TF-IDF + features métier).")

    X, y, tfidf, w2v_model = build_features(rows)
    model, scaler, metrics = train_and_evaluate(X, y)
    save_artifacts(Path(args.output), tfidf, w2v_model, scaler, model, metrics)

    print("\n=== Optimized training finished ===")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
