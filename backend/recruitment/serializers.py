from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Candidat, CV, Candidature, Poste, Domaine, CandidatureStatusHistory, Entretien

User = get_user_model()


class PosteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Poste
        fields = '__all__'


class CandidatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidat
        fields = '__all__'


class CVSerializer(serializers.ModelSerializer):
    class Meta:
        model = CV
        fields = '__all__'


class CandidatureSerializer(serializers.ModelSerializer):
    candidat_nom = serializers.CharField(source='candidat.nom', read_only=True)
    candidat_prenom = serializers.CharField(source='candidat.prenom', read_only=True)
    poste_titre = serializers.CharField(source='poste.titre', read_only=True)

    class Meta:
        model = Candidature
        fields = '__all__'


class EntretienSerializer(serializers.ModelSerializer):
    candidat_nom = serializers.CharField(source="candidature.candidat.nom", read_only=True)
    candidat_prenom = serializers.CharField(source="candidature.candidat.prenom", read_only=True)
    poste_titre = serializers.CharField(source="candidature.poste.titre", read_only=True)
    type_entretien_label = serializers.SerializerMethodField()

    class Meta:
        model = Entretien
        fields = "__all__"

    def get_type_entretien_label(self, obj):
        return obj.get_type_entretien_display()

    def validate(self, attrs):
        debut = attrs.get("debut") or getattr(self.instance, "debut", None)
        fin = attrs.get("fin") or getattr(self.instance, "fin", None)
        if debut and fin and fin <= debut:
            raise serializers.ValidationError({"fin": "L'heure de fin doit être après le début."})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Serializer pour afficher les infos d'un utilisateur (sans mot de passe)."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class CreateUserSerializer(serializers.ModelSerializer):
    """Serializer pour créer un utilisateur avec mot de passe (admin uniquement)."""
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)  # Hachage sécurisé du mot de passe
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class DomaineSerializer(serializers.ModelSerializer):
    candidats_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Domaine
        fields = ["id", "nom", "description", "actif", "created_at", "candidats_count"]


class CandidatureStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True)

    class Meta:
        model = CandidatureStatusHistory
        fields = [
            "id",
            "candidature",
            "previous_status",
            "new_status",
            "comment",
            "changed_by",
            "changed_by_name",
            "changed_at",
        ]