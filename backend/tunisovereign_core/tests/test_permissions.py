import pytest
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from backend.tunisovereign_core.api_rest import IsCitizen, IsMunicipalAuditor, IsNationalAdmin
from backend.tunisovereign_core.models import Municipality, Proposal, StakeholderUser


def _user(username: str, role: str) -> StakeholderUser:
    return StakeholderUser.objects.create_user(
        username=username,
        password="test-pass-123",
        role=role,
    )


def _client(user: StakeholderUser) -> APIClient:
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def _request(user: StakeholderUser):
    request = APIRequestFactory().get("/")
    request.user = user
    return request


@pytest.mark.django_db
def test_anomaly_endpoint_role_matrix():
    citizen = _user("citizen", StakeholderUser.Role.CITIZEN)
    auditor = _user("auditor", StakeholderUser.Role.MUNICIPAL_AUDITOR)
    admin = _user("admin", StakeholderUser.Role.NATIONAL_ADMIN)
    agent = _user("agent", StakeholderUser.Role.AGENT_SERVICE)

    matrix = [
        (citizen, 403),
        (auditor, 200),
        (admin, 200),
        (agent, 403),
    ]
    for user, expected in matrix:
        response = _client(user).get("/api/v1/anomalies/")
        assert response.status_code == expected, (user.role, response.content)

    assert APIClient().get("/api/v1/anomalies/").status_code == 401


@pytest.mark.django_db
def test_citizen_reads_but_cannot_modify_proposals():
    municipality = Municipality.objects.create(
        name="Kasserine",
        governorate="Kasserine",
        total_budget_tnd=100_000,
        matching_pool_tnd=10_000,
    )
    citizen = _user("citizen2", StakeholderUser.Role.CITIZEN)
    auditor = _user("auditor2", StakeholderUser.Role.MUNICIPAL_AUDITOR)
    proposal = Proposal.objects.create(
        municipality=municipality,
        author=citizen,
        project_code="KAS-PERM-001",
        title="Route",
        text="tarmim triq",
        category=Proposal.Category.ROAD,
    )

    assert _client(citizen).get("/api/v1/municipalities/").status_code == 200
    citizen_patch = _client(citizen).patch(
        f"/api/v1/proposals/{proposal.pk}/", {"title": "Changed"}, format="json"
    )
    auditor_patch = _client(auditor).patch(
        f"/api/v1/proposals/{proposal.pk}/", {"title": "Changed"}, format="json"
    )

    assert citizen_patch.status_code == 403
    assert auditor_patch.status_code == 200


@pytest.mark.django_db
def test_national_admin_permission_class():
    citizen = _user("citizen3", StakeholderUser.Role.CITIZEN)
    auditor = _user("auditor3", StakeholderUser.Role.MUNICIPAL_AUDITOR)
    admin = _user("admin3", StakeholderUser.Role.NATIONAL_ADMIN)

    assert IsCitizen().has_permission(_request(citizen), None) is True
    assert IsMunicipalAuditor().has_permission(_request(auditor), None) is True
    assert IsMunicipalAuditor().has_permission(_request(citizen), None) is False
    assert IsNationalAdmin().has_permission(_request(admin), None) is True
    assert IsNationalAdmin().has_permission(_request(auditor), None) is False
