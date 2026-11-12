"""Role-based DRF permissions."""
import os

from rest_framework import permissions

from .models import StakeholderUser


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
            and request.user.role
            in (StakeholderUser.Role.AGENT_SERVICE, StakeholderUser.Role.NATIONAL_ADMIN)
        )
