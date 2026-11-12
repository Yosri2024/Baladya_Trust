"""
Baladiya-Trust REST API (Django REST Framework + SimpleJWT).

Routes:
- POST /api/auth/register/ and POST /api/auth/token/
- CRUD /api/v1/municipalities/, /proposals/, /votes/, /milestones/
- Read /api/v1/anomalies/, /zk-receipts/
- POST /api/v1/darja-intent/ (agent webhook, JWT or n8n shared secret)
"""
import hashlib
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

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
    """Residency rule: a CITIZEN may only act in their own municipality.
    Auditors, admins and the agent are not restricted."""
    if user.role != StakeholderUser.Role.CITIZEN:
        return True
    return user.municipality.strip().casefold() == municipality.name.strip().casefold()


def derive_voter_hash(user) -> str:
    """Deterministic pseudonymous commitment: never store the raw identity."""
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


class BaladiyaTokenObtainPairView(TokenObtainPairView):
    serializer_class = BaladiyaTokenObtainPairSerializer


class IsCitizen(permissions.BasePermission):
    """Only CITIZEN accounts may create proposals or votes."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == StakeholderUser.Role.CITIZEN
        )


class IsMunicipalAuditor(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role
            in (StakeholderUser.Role.MUNICIPAL_AUDITOR, StakeholderUser.Role.NATIONAL_ADMIN)
        )


class IsNationalAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == StakeholderUser.Role.NATIONAL_ADMIN
        )


class IsAuditorOrAgent(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role
            in (
                StakeholderUser.Role.MUNICIPAL_AUDITOR,
                StakeholderUser.Role.NATIONAL_ADMIN,
                StakeholderUser.Role.AGENT_SERVICE,
            )
        )


class IsAgentOrN8NSecret(permissions.BasePermission):
    """Accept an AGENT_SERVICE JWT or the n8n shared secret header."""

    def has_permission(self, request, view):
        secret = os.getenv("N8N_WEBHOOK_SECRET", "")
        provided = request.headers.get("X-N8N-Secret", "")
        if secret and provided and provided == secret:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (StakeholderUser.Role.AGENT_SERVICE, StakeholderUser.Role.NATIONAL_ADMIN)
        )


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


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "role": user.role,
                "municipality": user.municipality,
            },
            status=status.HTTP_201_CREATED,
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
            if not citizen_resides_in(request.user, attrs["proposal"].municipality):
                raise serializers.ValidationError("Vous ne pouvez voter que dans votre municipalité.")
            voter_hash = derive_voter_hash(request.user)
            if Vote.objects.filter(proposal=attrs["proposal"], voter_hash=voter_hash).exists():
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


class MunicipalityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Municipality.objects.all().order_by("name")
    serializer_class = MunicipalitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["governorate"]


class ProposalViewSet(viewsets.ModelViewSet):
    serializer_class = ProposalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["municipality", "status", "category", "cluster_id"]
    search_fields = ["project_code", "title", "text"]
    ordering_fields = ["created_at", "estimated_cost_tnd"]

    def get_queryset(self):
        from django.db.models import Count, Sum

        return (
            Proposal.objects.select_related("municipality", "author")
            .annotate(votes_count=Count("votes"), raised_tnd=Sum("votes__amount_tnd"))
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_permissions(self):
        if self.action == "create":
            return [IsCitizen()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsMunicipalAuditor()]
        return [permissions.IsAuthenticated()]


class VoteViewSet(viewsets.ModelViewSet):
    queryset = Vote.objects.select_related("proposal").order_by("-created_at")
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["proposal"]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsCitizen()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if user.is_authenticated and user.role in (
            StakeholderUser.Role.MUNICIPAL_AUDITOR,
            StakeholderUser.Role.NATIONAL_ADMIN,
        ):
            return queryset
        if user.is_authenticated:
            return queryset.filter(voter_hash=derive_voter_hash(user))
        return queryset.none()


class MilestoneReportViewSet(viewsets.ModelViewSet):
    queryset = MilestoneReport.objects.select_related("proposal").order_by("-timestamp")
    serializer_class = MilestoneReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["proposal"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuditorOrAgent()]
        return [permissions.IsAuthenticated()]


class TrancheViewSet(viewsets.ModelViewSet):
    queryset = Tranche.objects.select_related("proposal").order_by("proposal", "index")
    serializer_class = TrancheSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["proposal"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsMunicipalAuditor()]
        return [permissions.IsAuthenticated()]


class AnomalyEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AnomalyEvent.objects.select_related("proposal").order_by("-detected_at")
    serializer_class = AnomalyEventSerializer
    permission_classes = [IsMunicipalAuditor]
    filterset_fields = ["proposal", "kind", "severity"]


class OnChainZKReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OnChainZKReceipt.objects.select_related("agent_execution", "tranche").order_by(
        "-block_number"
    )
    serializer_class = OnChainZKReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["tranche", "is_verified_on_chain"]


@api_view(["POST"])
@permission_classes([IsAgentOrN8NSecret])
def darja_intent_webhook(request):
    """
    POST /api/v1/darja-intent/
    Accepts a Darja transcript and triggers the LangGraph agent loop.
    """
    from agent.langgraph_agent import run_baladiya_agent_loop

    payload = request.data
    state_in = {
        "thread_id": payload.get("thread_id", "baladiya-webhook-001"),
        "municipality": payload.get("municipality", "Kasserine"),
        "proposal_code": payload.get("proposal_code", ""),
        "darja_input": payload.get("darja_input", ""),
        "trigger_source": "REST_Darja_Webhook",
        "parsed_intent": {},
        "anomaly_report": {},
        "budget_decision": {},
        "zk_receipt": {},
        "skills_trace": [],
        "final_explanation": "",
    }
    state_out = run_baladiya_agent_loop(state_in)
    return Response(state_out, status=status.HTTP_200_OK)
