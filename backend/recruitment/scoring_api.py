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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_score_for_candidature(request):
    """
    Calcule le score pour une candidature spécifique
    POST /api/scoring/candidature/<candidature_id>/
    """
    try:
        candidature_id = request.data.get('candidature_id')
        
        if not candidature_id:
            return Response({'error': 'candidature_id requis'}, status=400)
        
        candidature = Candidature.objects.select_related(
            'candidat', 'poste', 'cv'
        ).get(pk=candidature_id)
        
        # Préparer les données du candidat
        candidat_data = {
            'texte_cv': candidature.cv.texte_extrait if candidature.cv else '',
            'competences': candidature.candidat.competences.split(',') if candidature.candidat.competences else [],
            'langues': candidature.candidat.langues or '',
            'soft_skills': candidature.candidat.soft_skills or '',
            'annees_experience': float(candidature.candidat.annees_experience or 0),
            'niveau_etudes': candidature.candidat.niveau_etudes or '',
            'localisation': candidature.candidat.localisation or '',
        }
        
        # Préparer les données du poste
        poste_data = {
            'competences_requises': candidature.poste.competences_requises or '',
            'competences_optionnelles': candidature.poste.competences_optionnelles or '',
            'langues_requises': candidature.poste.langues_requises or '',
            'experience_min_annees': float(candidature.poste.experience_min_annees or 0),
            'niveau_etudes_requis': candidature.poste.niveau_etudes_requis or '',
            'localisation': candidature.poste.localisation or '',
            'poids_competences': float(candidature.poste.poids_competences or 35),
            'poids_experience': float(candidature.poste.poids_experience or 25),
            'poids_formation': float(candidature.poste.poids_formation or 20),
            'poids_langues': float(candidature.poste.poids_langues or 10),
            'poids_localisation': float(candidature.poste.poids_localisation or 5),
            'poids_soft_skills': float(candidature.poste.poids_soft_skills or 5),
        }
        
        # Calculer le score
        score_result = calculer_score_avance(candidat_data, poste_data)
        
        # Mettre à jour la candidature
        candidature.score = score_result['score_final']
        candidature.score_details_json = json.dumps({
            'competences': score_result['score_competences'],
            'experience': score_result['score_experience'],
            'formation': score_result['score_formation'],
            'langues': score_result['score_langues'],
            'localisation': score_result['score_localisation'],
            'soft_skills': score_result['score_soft_skills'],
        })
        
        # Générer l'explication du score
        explanation = (
            f"Compétences: {score_result['score_competences']}%, "
            f"Expérience: {score_result['score_experience']}%, "
            f"Formation: {score_result['score_formation']}%, "
            f"Langues: {score_result['score_langues']}%, "
            f"Localisation: {score_result['score_localisation']}%, "
            f"Soft skills: {score_result['score_soft_skills']}%"
        )
        candidature.explication_score = explanation
        candidature.save()
        
        return Response({
            'success': True,
            'score': candidature.score,
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
        return Response({'error': 'Candidature non trouvée'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_scores_for_job(request):
    """
    Calcule les scores pour TOUS les candidats d'une offre
    POST /api/scoring/job/<job_id>/
    """
    try:
        job_id = request.data.get('job_id')
        
        if not job_id:
            return Response({'error': 'job_id requis'}, status=400)
        
        poste = Poste.objects.get(pk=job_id)
        candidatures = Candidature.objects.select_related(
            'candidat', 'cv'
        ).filter(poste=poste)
        
        # Préparer les données du poste
        poste_data = {
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
        
        scores_calculated = 0
        results = []
        
        for candidature in candidatures:
            try:
                # Préparer les données du candidat
                candidat_data = {
                    'texte_cv': candidature.cv.texte_extrait if candidature.cv else '',
                    'competences': candidature.candidat.competences.split(',') if candidature.candidat.competences else [],
                    'langues': candidature.candidat.langues or '',
                    'soft_skills': candidature.candidat.soft_skills or '',
                    'annees_experience': float(candidature.candidat.annees_experience or 0),
                    'niveau_etudes': candidature.candidat.niveau_etudes or '',
                    'localisation': candidature.candidat.localisation or '',
                }
                
                # Calculer le score
                score_result = calculer_score_avance(candidat_data, poste_data)
                
                # Mettre à jour la candidature
                candidature.score = score_result['score_final']
                candidature.score_details_json = json.dumps({
                    'competences': score_result['score_competences'],
                    'experience': score_result['score_experience'],
                    'formation': score_result['score_formation'],
                    'langues': score_result['score_langues'],
                    'localisation': score_result['score_localisation'],
                    'soft_skills': score_result['score_soft_skills'],
                })
                
                explanation = (
                    f"Compétences: {score_result['score_competences']}%, "
                    f"Expérience: {score_result['score_experience']}%, "
                    f"Formation: {score_result['score_formation']}%, "
                    f"Langues: {score_result['score_langues']}%, "
                    f"Localisation: {score_result['score_localisation']}%, "
                    f"Soft skills: {score_result['score_soft_skills']}%"
                )
                candidature.explication_score = explanation
                candidature.save()
                
                scores_calculated += 1
                results.append({
                    'candidature_id': candidature.id,
                    'candidat': f"{candidature.candidat.prenom} {candidature.candidat.nom}",
                    'score': candidature.score,
                })
            except Exception as e:
                print(f"Erreur scoring candidat {candidature.id}: {e}")
                continue
        
        return Response({
            'success': True,
            'job_id': job_id,
            'job_title': poste.titre,
            'scores_calculated': scores_calculated,
            'results': sorted(results, key=lambda x: x['score'], reverse=True)
        })
    
    except Poste.DoesNotExist:
        return Response({'error': 'Offre non trouvée'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_all_scores(request):
    """
    Calcule les scores pour TOUTES les candidatures du système
    POST /api/scoring/all/
    """
    try:
        all_candidatures = Candidature.objects.select_related(
            'candidat', 'poste', 'cv'
        ).all()
        
        scores_calculated = 0
        
        for candidature in all_candidatures:
            try:
                poste = candidature.poste
                if not poste:
                    continue
                
                # Préparer les données du poste
                poste_data = {
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
                
                # Préparer les données du candidat
                candidat_data = {
                    'texte_cv': candidature.cv.texte_extrait if candidature.cv else '',
                    'competences': candidature.candidat.competences.split(',') if candidature.candidat.competences else [],
                    'langues': candidature.candidat.langues or '',
                    'soft_skills': candidature.candidat.soft_skills or '',
                    'annees_experience': float(candidature.candidat.annees_experience or 0),
                    'niveau_etudes': candidature.candidat.niveau_etudes or '',
                    'localisation': candidature.candidat.localisation or '',
                }
                
                # Calculer le score
                score_result = calculer_score_avance(candidat_data, poste_data)
                
                # Mettre à jour la candidature
                candidature.score = score_result['score_final']
                candidature.score_details_json = json.dumps({
                    'competences': score_result['score_competences'],
                    'experience': score_result['score_experience'],
                    'formation': score_result['score_formation'],
                    'langues': score_result['score_langues'],
                    'localisation': score_result['score_localisation'],
                    'soft_skills': score_result['score_soft_skills'],
                })
                
                explanation = (
                    f"Compétences: {score_result['score_competences']}%, "
                    f"Expérience: {score_result['score_experience']}%, "
                    f"Formation: {score_result['score_formation']}%, "
                    f"Langues: {score_result['score_langues']}%, "
                    f"Localisation: {score_result['score_localisation']}%, "
                    f"Soft skills: {score_result['score_soft_skills']}%"
                )
                candidature.explication_score = explanation
                candidature.save()
                
                scores_calculated += 1
            except Exception as e:
                print(f"Erreur scoring candidature {candidature.id}: {e}")
                continue
        
        return Response({
            'success': True,
            'total_candidatures': all_candidatures.count(),
            'scores_calculated': scores_calculated,
            'message': f'{scores_calculated} score(s) calculé(s) avec succès'
        })
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)
