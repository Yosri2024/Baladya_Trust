from asgiref.sync import sync_to_async
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from strawberry.django.views import AsyncGraphQLView

from backend.tunisovereign_core.schema_graphql import build_loaders, schema


def health(request):
    return JsonResponse({"status": "ok", "service": "baladiya-trust"})


_jwt = JWTAuthentication()


@sync_to_async
def _authenticate(request):
    """Same JWT check as REST. Returns the user, or None if missing/invalid."""
    try:
        result = _jwt.authenticate(request)
    except (AuthenticationFailed, TokenError):
        return None
    return result[0] if result else None


class BaladiyaGraphQLView(AsyncGraphQLView):
    async def get_context(self, request, response):
        user = await _authenticate(request)
        return {"request": request, "response": response, "user": user, **build_loaders()}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path(
        "graphql/",
        csrf_exempt(BaladiyaGraphQLView.as_view(schema=schema)),
        name="graphql",
    ),
    path("", include("backend.tunisovereign_core.urls")),
]
