"""DRF views and viewsets for Baladiya-Trust."""
from django.db.models import Count, Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAgentOrN8NSecret, IsAuditorOrAgent, IsCitizen, IsMunicipalAuditor
from .serializers import (
    AnomalyEventSerializer,
    BaladiyaTokenObtainPairSerializer,
    MilestoneReportSerializer,
    MunicipalitySerializer,
    OnChainZKReceiptSerializer,
    ProposalSerializer,
    RegisterSerializer,
    TrancheSerializer,
    VoteSerializer,
    derive_voter_hash,
)
from .models import (
    AnomalyEvent,
    MilestoneReport,
    Municipality,
    OnChainZKReceipt,
    Proposal,
    StakeholderUser,
    Tranche,
    Vote,
)


class BaladiyaTokenObtainPairView(TokenObtainPairView):
    serializer_class = BaladiyaTokenObtainPairSerializer


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
