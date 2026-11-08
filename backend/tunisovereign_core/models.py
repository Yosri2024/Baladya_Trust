from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class StakeholderUser(AbstractUser):
    class Role(models.TextChoices):
        COOP_MEMBER = "COOP_MEMBER", "Farmer / Citizen / Field Operator"
        REGIONAL_AUDITOR = "REGIONAL_AUDITOR", "Regional GDA / PCT / Municipal Auditor"
        NATIONAL_ADMIN = "NATIONAL_ADMIN", "Governorate / National Ministry Admin"
        AGENT_SERVICE = "AGENT_SERVICE", "Autonomous AI Agent & MCP Service Account"

    role = models.CharField(max_length=24, choices=Role.choices, default=Role.COOP_MEMBER)
    governorate = models.CharField(max_length=64, db_index=True, default="Kasserine")
    wallet_address = models.CharField(max_length=42, blank=True, null=True)
    preferred_dialect = models.CharField(max_length=16, default="ar-TN")


class CooperativeUnit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    governorate = models.CharField(max_length=64, db_index=True)
    track_domain = models.CharField(max_length=64, default="Track_01_Water_Agri")
    daily_quota_limit = models.FloatField(help_text="Max daily resource/water/medicine quota")
    contract_address = models.CharField(max_length=42, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ResourceNodePlot(models.Model):
    coop = models.ForeignKey(CooperativeUnit, on_delete=models.CASCADE, related_name="nodes")
    owner = models.ForeignKey(StakeholderUser, on_delete=models.CASCADE, related_name="owned_nodes")
    node_code = models.CharField(max_length=32, unique=True)
    crop_or_sector_type = models.CharField(max_length=64)
    allocated_share_pct = models.FloatField(default=10.0)
    is_valve_or_dispatch_active = models.BooleanField(default=False)


class TelemetryReading(models.Model):
    class MetricType(models.TextChoices):
        SOIL_MOISTURE = "MOISTURE", "Soil Moisture (%)"
        AQUIFER_FLOW = "FLOW", "Flow / Dispensation Rate (L/min or Units/h)"
        TEMPERATURE = "TEMP", "Ambient / Cold-Chain Temperature (C)"
        PRESSURE_OR_STOCK = "STOCK", "Piezo Pressure / Inventory Level"

    node = models.ForeignKey(ResourceNodePlot, on_delete=models.CASCADE, related_name="readings")
    timestamp = models.DateTimeField(db_index=True)
    metric_type = models.CharField(max_length=16, choices=MetricType.choices)
    value = models.FloatField()
    ingestion_protocol = models.CharField(max_length=16, default="gRPC")

    class Meta:
        indexes = [models.Index(fields=["node", "metric_type", "-timestamp"])]


class AnomalyAndForecastEvent(models.Model):
    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        CRITICAL = "CRITICAL", "Critical Breach / Leak / Diversion"

    node = models.ForeignKey(ResourceNodePlot, on_delete=models.CASCADE, related_name="anomalies")
    detected_at = models.DateTimeField(auto_now_add=True)
    anomaly_type = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    isolation_forest_score = models.FloatField()
    forecasted_deficit_24h = models.FloatField(default=0.0)


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


class OnChainZKReceipt(models.Model):
    agent_execution = models.OneToOneField(AgentLoopExecution, on_delete=models.CASCADE, related_name="zk_receipt")
    zk_commitment_hash = models.CharField(max_length=66, unique=True)
    public_inputs_json = models.JSONField(default=dict)
    tx_hash = models.CharField(max_length=66, unique=True)
    block_number = models.PositiveIntegerField()
    network_name = models.CharField(max_length=32, default="Foundry-Anvil-Local")
    is_verified_on_chain = models.BooleanField(default=True)
