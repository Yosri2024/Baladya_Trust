import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class StakeholderUser(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "CITIZEN", "Citoyen de la municipalité"
        MUNICIPAL_AUDITOR = "MUNICIPAL_AUDITOR", "Auditeur municipal"
        NATIONAL_ADMIN = "NATIONAL_ADMIN", "Admin ministère / gouvernorat"
        AGENT_SERVICE = "AGENT_SERVICE", "Agent IA et compte MCP"

    role = models.CharField(max_length=24, choices=Role.choices, default=Role.CITIZEN)
    municipality = models.CharField(max_length=64, db_index=True, default="Kasserine")
    wallet_address = models.CharField(max_length=42, blank=True, null=True)
    residency_commitment = models.CharField(max_length=66, blank=True)
    preferred_dialect = models.CharField(max_length=16, default="ar-TN")


class Municipality(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    governorate = models.CharField(max_length=64, db_index=True)
    total_budget_tnd = models.FloatField()
    matching_pool_tnd = models.FloatField()
    contract_address = models.CharField(max_length=42, blank=True)

    def __str__(self):
        return f"{self.name} ({self.governorate})"


class Proposal(models.Model):
    class Category(models.TextChoices):
        ROAD = "ROAD", "Route"
        LIGHTING = "LIGHTING", "Éclairage"
        SCHOOL = "SCHOOL", "École"
        WASTE = "WASTE", "Déchets"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Soumis"
        MERGED = "MERGED", "Fusionné"
        FUNDED = "FUNDED", "Financé"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        BLOCKED = "BLOCKED", "Bloqué"

    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name="proposals")
    author = models.ForeignKey(StakeholderUser, on_delete=models.CASCADE, related_name="proposals")
    project_code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=160)
    text = models.TextField()
    language = models.CharField(max_length=8, default="ar-TN")
    category = models.CharField(max_length=16, choices=Category.choices)
    cluster_id = models.CharField(max_length=32, blank=True, db_index=True)
    estimated_cost_tnd = models.FloatField(default=0.0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["municipality", "status", "-created_at"])]

    def __str__(self):
        return f"{self.project_code} - {self.title}"


class Vote(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="votes")
    voter_hash = models.CharField(max_length=66, db_index=True)
    amount_tnd = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["proposal", "voter_hash"], name="one_vote")]
        indexes = [models.Index(fields=["proposal", "-created_at"])]


# Rôle : l'entrepreneur déclare l'avancement d'un chantier via un rapport de jalon (streaming gRPC).
class MilestoneReport(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="milestones")
    timestamp = models.DateTimeField(db_index=True)
    progress_pct = models.FloatField()
    paid_pct = models.FloatField()
    photo_hash = models.CharField(max_length=64)
    latitude = models.FloatField()
    longitude = models.FloatField()
    ingestion_protocol = models.CharField(max_length=16, default="gRPC")

    class Meta:
        indexes = [models.Index(fields=["proposal", "-timestamp"])]


# Rôle : découpe le budget d'un projet en tranches de paiement (ex. 4 tranches de 25 %).
class Tranche(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="tranches")
    index = models.PositiveSmallIntegerField()
    amount_tnd = models.FloatField()
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["proposal", "index"], name="uniq_tranche")]


# Rôle : trace les anomalies détectées par le module ML (IsolationForest + règles déterministes).
class AnomalyEvent(models.Model):
    class Kind(models.TextChoices):
        SYBIL_VOTES = "SYBIL_VOTES", "Votes sybil"
        PROGRESS_LAG = "PROGRESS_LAG", "Retard de chantier"
        DUPLICATE_PHOTO = "DUPLICATE_PHOTO", "Photo réutilisée"

    class Severity(models.TextChoices):
        LOW = "LOW", "Faible"
        MEDIUM = "MEDIUM", "Moyenne"
        CRITICAL = "CRITICAL", "Critique"

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="anomalies")
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    isolation_forest_score = models.FloatField()


# Rôle : audit de chaque exécution du graphe LangGraph. Permet de tracer "comment l'IA a raisonné".
class AgentLoopExecution(models.Model):
    thread_id = models.CharField(max_length=64, db_index=True)
    trigger_source = models.CharField(max_length=64)
    darja_transcript = models.TextField(blank=True)
    parsed_intent_json = models.JSONField(default=dict)
    mcp_tools_invoked = models.JSONField(default=list)
    skills_executed = models.JSONField(default=list)
    final_recommendation = models.TextField()
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)


# Rôle : preuve cryptographique d'une action écrite on-chain (Anvil / Polygon Amoy).
class OnChainZKReceipt(models.Model):
    agent_execution = models.OneToOneField(
        AgentLoopExecution, on_delete=models.CASCADE, related_name="zk_receipt"
    )
    tranche = models.ForeignKey(
        Tranche, on_delete=models.SET_NULL, related_name="zk_receipts", null=True, blank=True
    )
    zk_commitment_hash = models.CharField(max_length=66, unique=True)
    public_inputs_json = models.JSONField(default=dict)
    tx_hash = models.CharField(max_length=66, unique=True)
    block_number = models.PositiveIntegerField()
    network_name = models.CharField(max_length=32, default="Foundry-Anvil-Local")
    is_verified_on_chain = models.BooleanField(default=True)
