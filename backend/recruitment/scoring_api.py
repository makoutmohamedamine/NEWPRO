"""
Endpoint API pour le calcul des scores des candidatures
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
import json

from .models import Candidat, Candidature, Poste, CV
from .ai_engine import calculer_score_avance


def _build_poste_data(poste):
    return {
        'competences_requises': poste.competences_requises or '',
        'competences_optionnelles': poste.competences_optionnelles or '',
        'langues_requises': poste.langues_requises or '',
        'experience_min_annees': float(poste.experience_min_annees or 0),
        'niveau_etudes_requis': poste.niveau_etudes_requis or '',
        'localisation': poste.localisation or '',
        'poids_competences': float(poste.poids_competences or 35),
        'poids_experience': float(poste.poids_experience or 25),
        'poids_formation': float(poste.poids_formation or 20),
        'poids_langues': float(poste.poids_langues or 10),
        'poids_localisation': float(poste.poids_localisation or 5),
        'poids_soft_skills': float(poste.poids_soft_skills or 5),
    }


def _build_candidat_data(candidature):
    return {
        'texte_cv': candidature.cv.texte_extrait if candidature.cv else '',
        'competences': candidature.candidat.competences.split(',') if candidature.candidat.competences else [],
        'langues': candidature.candidat.langues or '',
        'soft_skills': candidature.candidat.soft_skills or '',
        'annees_experience': float(candidature.candidat.annees_experience or 0),
        'niveau_etudes': candidature.candidat.niveau_etudes or '',
        'localisation': candidature.candidat.localisation or '',
    }


def _format_explanation(score_result):
    return (
        f"Competences: {score_result['score_competences']}%, "
        f"Experience: {score_result['score_experience']}%, "
        f"Formation: {score_result['score_formation']}%, "
        f"Langues: {score_result['score_langues']}%, "
        f"Localisation: {score_result['score_localisation']}%, "
        f"Soft skills: {score_result['score_soft_skills']}%"
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_score_for_candidature(request):
    """Calcule le score pour une candidature specifique."""
    try:
        candidature_id = request.data.get('candidature_id')
        if not candidature_id:
            return Response({'error': 'candidature_id requis'}, status=400)

        candidature = Candidature.objects.select_related('candidat', 'poste', 'cv').get(pk=candidature_id)
        candidat_data = _build_candidat_data(candidature)
        poste_data = _build_poste_data(candidature.poste)
        score_result = calculer_score_avance(candidat_data, poste_data)

        explanation = _format_explanation(score_result)
        Candidature.objects.filter(pk=candidature.pk).update(
            score=score_result['score_final'],
            explication_score=explanation,
            score_details_json=json.dumps({
                'competences': score_result['score_competences'],
                'experience': score_result['score_experience'],
                'formation': score_result['score_formation'],
                'langues': score_result['score_langues'],
                'localisation': score_result['score_localisation'],
                'soft_skills': score_result['score_soft_skills'],
            }),
        )

        return Response({
            'success': True,
            'score': score_result['score_final'],
            'explanation': explanation,
            'details': {
                'competences': score_result['score_competences'],
                'experience': score_result['score_experience'],
                'formation': score_result['score_formation'],
                'langues': score_result['score_langues'],
                'localisation': score_result['score_localisation'],
                'softSkills': score_result['score_soft_skills'],
                'competencesMatchees': score_result['details'].get('competences_matchees', []),
                'competencesManquantes': score_result['details'].get('competences_manquantes', []),
            }
        })

    except Candidature.DoesNotExist:
        return Response({'error': 'Candidature non trouvee'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_scores_for_job(request):
    """Calcule les scores pour TOUS les candidats d'une offre (bulk update)."""
    try:
        job_id = request.data.get('job_id')
        if not job_id:
            return Response({'error': 'job_id requis'}, status=400)

        poste = Poste.objects.get(pk=job_id)
        candidatures = list(
            Candidature.objects.select_related('candidat', 'cv').filter(poste=poste)
        )
        poste_data = _build_poste_data(poste)

        to_update = []
        results = []

        for candidature in candidatures:
            try:
                score_result = calculer_score_avance(_build_candidat_data(candidature), poste_data)
                candidature.score = score_result['score_final']
                candidature.explication_score = _format_explanation(score_result)
                candidature.score_details_json = json.dumps({
                    'competences': score_result['score_competences'],
                    'experience': score_result['score_experience'],
                    'formation': score_result['score_formation'],
                    'langues': score_result['score_langues'],
                    'localisation': score_result['score_localisation'],
                    'soft_skills': score_result['score_soft_skills'],
                })
                to_update.append(candidature)
                results.append({
                    'candidature_id': candidature.id,
                    'candidat': f"{candidature.candidat.prenom} {candidature.candidat.nom}",
                    'score': candidature.score,
                })
            except Exception as e:
                continue

        if to_update:
            Candidature.objects.bulk_update(
                to_update, ['score', 'explication_score', 'score_details_json'], batch_size=100
            )

        return Response({
            'success': True,
            'job_id': job_id,
            'job_title': poste.titre,
            'scores_calculated': len(to_update),
            'results': sorted(results, key=lambda x: x['score'], reverse=True)
        })

    except Poste.DoesNotExist:
        return Response({'error': 'Offre non trouvee'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_all_scores(request):
    """Calcule les scores pour TOUTES les candidatures (bulk update optimise)."""
    try:
        all_candidatures = list(
            Candidature.objects.select_related('candidat', 'poste', 'cv').all()
        )

        to_update = []
        errors = 0

        for candidature in all_candidatures:
            try:
                if not candidature.poste:
                    continue
                poste_data = _build_poste_data(candidature.poste)
                score_result = calculer_score_avance(_build_candidat_data(candidature), poste_data)
                candidature.score = score_result['score_final']
                candidature.explication_score = _format_explanation(score_result)
                candidature.score_details_json = json.dumps({
                    'competences': score_result['score_competences'],
                    'experience': score_result['score_experience'],
                    'formation': score_result['score_formation'],
                    'langues': score_result['score_langues'],
                    'localisation': score_result['score_localisation'],
                    'soft_skills': score_result['score_soft_skills'],
                })
                to_update.append(candidature)
            except Exception:
                errors += 1
                continue

        if to_update:
            Candidature.objects.bulk_update(
                to_update, ['score', 'explication_score', 'score_details_json'], batch_size=100
            )

        return Response({
            'success': True,
            'total_candidatures': len(all_candidatures),
            'scores_calculated': len(to_update),
            'errors': errors,
            'message': f'{len(to_update)} score(s) calcule(s) avec succes'
        })

    except Exception as e:
        return Response({'error': str(e)}, status=500)
