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


def _municipality(name: str = "Kasserine") -> Municipality:
    return Municipality.objects.create(
        name=name,
        governorate="Kasserine",
        total_budget_tnd=100_000,
        matching_pool_tnd=10_000,
    )


def _proposal(municipality: Municipality, author: StakeholderUser, code: str) -> Proposal:
    return Proposal.objects.create(
        municipality=municipality,
        author=author,
        project_code=code,
        title="Route",
        text="tarmim triq",
        category=Proposal.Category.ROAD,
    )


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
    municipality = _municipality()
    citizen = _user("citizen2", StakeholderUser.Role.CITIZEN)
    auditor = _user("auditor2", StakeholderUser.Role.MUNICIPAL_AUDITOR)
    proposal = _proposal(municipality, citizen, "KAS-PERM-001")

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
def test_permission_classes():
    citizen = _user("citizen3", StakeholderUser.Role.CITIZEN)
    auditor = _user("auditor3", StakeholderUser.Role.MUNICIPAL_AUDITOR)
    admin = _user("admin3", StakeholderUser.Role.NATIONAL_ADMIN)
    agent = _user("agent3", StakeholderUser.Role.AGENT_SERVICE)

    assert IsCitizen().has_permission(_request(citizen), None) is True
    assert IsCitizen().has_permission(_request(auditor), None) is False
    assert IsCitizen().has_permission(_request(admin), None) is False
    assert IsCitizen().has_permission(_request(agent), None) is False
    assert IsMunicipalAuditor().has_permission(_request(auditor), None) is True
    assert IsMunicipalAuditor().has_permission(_request(admin), None) is True
    assert IsMunicipalAuditor().has_permission(_request(citizen), None) is False
    assert IsNationalAdmin().has_permission(_request(admin), None) is True
    assert IsNationalAdmin().has_permission(_request(auditor), None) is False


@pytest.mark.django_db
def test_proposal_create_role_matrix():
    municipality = _municipality()
    roles = [
        ("citizen-proposal", StakeholderUser.Role.CITIZEN, 201),
        ("auditor-proposal", StakeholderUser.Role.MUNICIPAL_AUDITOR, 403),
        ("admin-proposal", StakeholderUser.Role.NATIONAL_ADMIN, 403),
        ("agent-proposal", StakeholderUser.Role.AGENT_SERVICE, 403),
    ]

    for username, role, expected in roles:
        user = _user(username, role)
        response = _client(user).post(
            "/api/v1/proposals/",
            {
                "municipality": str(municipality.pk),
                "project_code": f"CODE-{user.pk}",
                "title": "Route",
                "text": "tarmim triq",
                "category": Proposal.Category.ROAD,
            },
            format="json",
        )
        assert response.status_code == expected, (role, response.content)


@pytest.mark.django_db
def test_proposal_read_role_matrix():
    municipality = _municipality()
    citizen = _user("citizen-read", StakeholderUser.Role.CITIZEN)
    proposal = _proposal(municipality, citizen, "KAS-READ-001")
    users = [
        citizen,
        _user("auditor-read", StakeholderUser.Role.MUNICIPAL_AUDITOR),
        _user("admin-read", StakeholderUser.Role.NATIONAL_ADMIN),
        _user("agent-read", StakeholderUser.Role.AGENT_SERVICE),
    ]

    for user in users:
        assert _client(user).get(f"/api/v1/proposals/{proposal.pk}/").status_code == 200

    assert APIClient().get(f"/api/v1/proposals/{proposal.pk}/").status_code == 401


@pytest.mark.django_db
def test_vote_create_role_matrix():
    municipality = _municipality()
    citizen = _user("citizen-vote", StakeholderUser.Role.CITIZEN)
    proposal = _proposal(municipality, citizen, "KAS-VOTE-001")
    roles = [
        (citizen, 201),
        (_user("auditor-vote", StakeholderUser.Role.MUNICIPAL_AUDITOR), 403),
        (_user("admin-vote", StakeholderUser.Role.NATIONAL_ADMIN), 403),
        (_user("agent-vote", StakeholderUser.Role.AGENT_SERVICE), 403),
    ]

    for user, expected in roles:
        response = _client(user).post(
            "/api/v1/votes/",
            {"proposal": proposal.pk, "amount_tnd": 5},
            format="json",
        )
        assert response.status_code == expected, (user.role, response.content)


@pytest.mark.django_db
def test_protected_endpoints_reject_missing_or_invalid_token():
    paths = [
        "/api/v1/proposals/",
        "/api/v1/votes/",
        "/api/v1/municipalities/",
        "/api/v1/zk-receipts/",
        "/api/v1/anomalies/",
    ]

    for path in paths:
        assert APIClient().get(path).status_code == 401
        invalid = APIClient()
        invalid.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        assert invalid.get(path).status_code == 401
