#!/usr/bin/env python3
"""
Exporte un dataset d'entrainement CV <-> Job depuis la base Django.

Colonnes de sortie:
- cv_id
- candidate_id
- job_id
- cv_text
- job_text
- label (0/1)
- source

Usage:
  python export_training_dataset.py --output data/matching_dataset_real.csv
"""

import argparse
import csv
import os
import random
from pathlib import Path

import django


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    django.setup()


POSITIVE_STATUSES = {"accepte", "shortlist", "entretien_rh", "entretien_technique", "validation_manager", "finaliste"}


def candidature_is_positive(candidature) -> bool:
    # Priorite au score si present.
    if candidature.score is not None:
        try:
            return float(candidature.score) >= 70.0
        except Exception:
            pass
    return candidature.statut in POSITIVE_STATUSES


def build_job_text(poste) -> str:
    parts = [
        poste.titre or "",
        poste.description or "",
        poste.competences_requises or "",
        poste.competences_optionnelles or "",
        poste.langues_requises or "",
        poste.departement or "",
        poste.localisation or "",
        poste.niveau_etudes_requis or "",
    ]
    return " ".join(p.strip() for p in parts if p and p.strip())


def build_cv_text(cv, candidat) -> str:
    parts = [
        cv.texte_extrait or "",
        candidat.resume_profil or "",
        candidat.competences or "",
        candidat.langues or "",
        candidat.soft_skills or "",
        candidat.current_title or "",
        candidat.niveau_etudes or "",
    ]
    return " ".join(p.strip() for p in parts if p and p.strip())


def export_dataset(output_path: Path, negatives_per_positive: int, seed: int, min_text_chars: int):
    from recruitment.models import Candidature, Poste

    random.seed(seed)

    candidatures = (
        Candidature.objects.select_related("candidat", "cv", "poste")
        .exclude(cv__isnull=True)
        .order_by("id")
    )
    all_postes = list(Poste.objects.all())
    if not all_postes:
        raise ValueError("Aucun poste trouve dans la base.")

    rows = []
    scored_buffer = []
    positive_rows = 0
    negative_rows = 0

    for c in candidatures:
        candidat = c.candidat
        cv = c.cv
        poste = c.poste
        if not cv or not poste:
            continue

        cv_text = build_cv_text(cv, candidat)
        job_text = build_job_text(poste)
        if len(cv_text) < min_text_chars or len(job_text) < min_text_chars:
            continue

        label = 1 if candidature_is_positive(c) else 0
        score_value = float(c.score) if c.score is not None else None
        rows.append(
            {
                "cv_id": cv.id,
                "candidate_id": candidat.id,
                "job_id": poste.id,
                "cv_text": cv_text,
                "job_text": job_text,
                "label": label,
                "source": "application",
            }
        )
        scored_buffer.append({"idx": len(rows) - 1, "score": score_value})
        positive_rows += int(label == 1)
        negative_rows += int(label == 0)

        # Hard negatives: meme CV avec d'autres postes.
        if label == 1 and negatives_per_positive > 0:
            other_postes = [p for p in all_postes if p.id != poste.id]
            random.shuffle(other_postes)
            selected = other_postes[:negatives_per_positive]
            for p in selected:
                alt_job_text = build_job_text(p)
                if len(alt_job_text) < min_text_chars:
                    continue
                rows.append(
                    {
                        "cv_id": cv.id,
                        "candidate_id": candidat.id,
                        "job_id": p.id,
                        "cv_text": cv_text,
                        "job_text": alt_job_text,
                        "label": 0,
                        "source": "hard_negative",
                    }
                )
                negative_rows += 1

    # Si aucun positif en base, transformer automatiquement le top 30% des scores en positifs.
    if positive_rows == 0:
        scored_items = [item for item in scored_buffer if item["score"] is not None]
        if scored_items:
            scored_items.sort(key=lambda x: x["score"], reverse=True)
            top_n = max(1, int(round(len(scored_items) * 0.30)))
            top_indices = {item["idx"] for item in scored_items[:top_n]}
            for idx in top_indices:
                if rows[idx]["label"] == 0:
                    rows[idx]["label"] = 1
                    rows[idx]["source"] = "auto_positive_from_score"
                    positive_rows += 1
                    negative_rows -= 1

    if not rows:
        raise ValueError("Aucune paire exportable. Verifiez vos candidatures/CV.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["cv_id", "candidate_id", "job_id", "cv_text", "job_text", "label", "source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    print(f"Dataset exporte: {output_path}")
    print(f"Lignes totales: {total}")
    print(f"Positifs: {positive_rows}")
    print(f"Negatifs: {negative_rows}")
    if total > 0:
        print(f"Taux positif: {round((positive_rows / total) * 100, 2)}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/matching_dataset_real.csv", help="Chemin CSV de sortie")
    parser.add_argument("--negatives-per-positive", type=int, default=2, help="Nombre de hard negatives par positif")
    parser.add_argument("--seed", type=int, default=42, help="Seed random")
    parser.add_argument("--min-text-chars", type=int, default=30, help="Longueur min texte CV/poste")
    args = parser.parse_args()

    setup_django()
    export_dataset(
        output_path=Path(args.output),
        negatives_per_positive=max(0, args.negatives_per_positive),
        seed=args.seed,
        min_text_chars=max(0, args.min_text_chars),
    )


if __name__ == "__main__":
    main()

