from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView

from backend.tunisovereign_core.schema_graphql import build_loaders, schema


def health(request):
    return JsonResponse({"status": "ok", "service": "baladiya-trust"})


class BaladiyaGraphQLView(AsyncGraphQLView):
    async def get_context(self, request, response):
        return {"request": request, "response": response, **build_loaders()} # ** : déballage / unpacking


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
