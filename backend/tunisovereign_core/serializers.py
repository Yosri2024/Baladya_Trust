"""DRF serializers for Baladiya-Trust."""
import hashlib

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    AgentLoopExecution,
    AnomalyEvent,
    MilestoneReport,
    Municipality,
    OnChainZKReceipt,
    Proposal,
    StakeholderUser,
    Tranche,
    Vote,
)

VOTER_HASH_PREFIX = "0x"


def citizen_resides_in(user, municipality) -> bool:
    """A CITIZEN may only act in their own municipality."""
    if user.role != StakeholderUser.Role.CITIZEN:
        return True
    return user.municipality.strip().casefold() == municipality.name.strip().casefold()


def derive_voter_hash(user) -> str:
    """Pseudonymous commitment: never store the raw identity."""
    seed = user.residency_commitment or user.wallet_address or f"{user.username}:{user.pk}"
    if seed.startswith(VOTER_HASH_PREFIX) and len(seed) == 66:
        return seed
    return VOTER_HASH_PREFIX + hashlib.sha256(seed.encode("utf-8")).hexdigest()


class BaladiyaTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: StakeholderUser):
        token = super().get_token(user)
        token["role"] = user.role
        token["municipality"] = user.municipality
        token["wallet_address"] = user.wallet_address or ""
        token["preferred_dialect"] = user.preferred_dialect
        return token


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)
    municipality = serializers.CharField(max_length=64, default="Kasserine")
    wallet_address = serializers.CharField(max_length=42, required=False, allow_blank=True)
    residency_commitment = serializers.CharField(max_length=66, required=False, allow_blank=True)
    preferred_dialect = serializers.CharField(max_length=16, default="ar-TN")

    def validate_username(self, value):
        if StakeholderUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur existe déjà.")
        return value

    def validate(self, attrs):
        candidate = StakeholderUser(username=attrs["username"], email=attrs.get("email", ""))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        return StakeholderUser.objects.create_user(
            role=StakeholderUser.Role.CITIZEN,
            **validated_data,
        )


class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = "__all__"


class ProposalSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    votes_count = serializers.IntegerField(read_only=True)
    raised_tnd = serializers.FloatField(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "municipality",
            "author",
            "project_code",
            "title",
            "text",
            "language",
            "category",
            "cluster_id",
            "estimated_cost_tnd",
            "status",
            "created_at",
            "votes_count",
            "raised_tnd",
        ]
        read_only_fields = ["status", "created_at"]

    def validate_estimated_cost_tnd(self, value):
        if value < 0:
            raise serializers.ValidationError("Le coût estimé doit être positif.")
        return value

    def validate_municipality(self, value):
        request = self.context.get("request")
        if request and request.user.is_authenticated and not citizen_resides_in(request.user, value):
            raise serializers.ValidationError("Vous ne pouvez proposer que dans votre municipalité.")
        return value


class VoteSerializer(serializers.ModelSerializer):
    voter_hash = serializers.CharField(read_only=True)

    class Meta:
        model = Vote
        fields = ["id", "proposal", "voter_hash", "amount_tnd", "created_at"]
        read_only_fields = ["created_at"]

    def validate_amount_tnd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant du vote doit être strictement positif.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            proposal = attrs["proposal"]
            if not citizen_resides_in(request.user, proposal.municipality):
                raise serializers.ValidationError("Vous ne pouvez voter que dans votre municipalité.")
            voter_hash = derive_voter_hash(request.user)
            if Vote.objects.filter(proposal=proposal, voter_hash=voter_hash).exists():
                raise serializers.ValidationError("Un seul vote par proposition et par citoyen.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["voter_hash"] = derive_voter_hash(request.user)
        return super().create(validated_data)


class MilestoneReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MilestoneReport
        fields = "__all__"

    def validate_progress_pct(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("progress_pct doit être entre 0 et 100.")
        return value

    def validate_paid_pct(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("paid_pct doit être entre 0 et 100.")
        return value


class TrancheSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tranche
        fields = "__all__"


class AnomalyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyEvent
        fields = "__all__"


class OnChainZKReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnChainZKReceipt
        fields = "__all__"


class AgentLoopExecutionSerializer(serializers.ModelSerializer):
    zk_receipt = OnChainZKReceiptSerializer(read_only=True)

    class Meta:
        model = AgentLoopExecution
        fields = "__all__"
