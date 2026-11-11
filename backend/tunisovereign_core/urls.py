from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .api_rest import (
    AnomalyEventViewSet,
    BaladiyaTokenObtainPairView,
    MilestoneReportViewSet,
    MunicipalityViewSet,
    OnChainZKReceiptViewSet,
    ProposalViewSet,
    RegisterView,
    TrancheViewSet,
    VoteViewSet,
    darja_intent_webhook,
)

router = DefaultRouter()
router.register(r"municipalities", MunicipalityViewSet, basename="municipality")
router.register(r"proposals", ProposalViewSet, basename="proposal")
router.register(r"votes", VoteViewSet, basename="vote")
router.register(r"milestones", MilestoneReportViewSet, basename="milestone")
router.register(r"tranches", TrancheViewSet, basename="tranche")
router.register(r"anomalies", AnomalyEventViewSet, basename="anomaly")
router.register(r"zk-receipts", OnChainZKReceiptViewSet, basename="zk-receipt")

urlpatterns = [
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/token/", BaladiyaTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/darja-intent/", darja_intent_webhook, name="darja_intent"),
    path("api/v1/", include(router.urls)),
]
