"""URLs of the REST API, included at /api/ (config/urls.py), namespace "api".

    /api/                   the list of sections (DefaultRouter)
    /api/token/             JWT: username + password -> access + refresh
    /api/token/refresh/     JWT: refresh -> a new access
    /api/token/verify/      JWT: is this token valid?
    /api/schema/            OpenAPI schema (YAML; ?format=json for JSON)
    /api/docs/              Swagger UI: the documentation + "Try it out"
    /api/redoc/             ReDoc: the same documentation, for reading

The ViewSets (books, authors, categories, orders) are registered in the
router in the next stages: one register() line gives both URLs of a
ViewSet, the list (/api/books/) and one object (/api/books/<pk>/).
"""

from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import PublicAPIRootView, ThrottledTokenObtainPairView

app_name = "api"


class Router(DefaultRouter):
    # The root page /api/ without a login (see PublicAPIRootView)
    APIRootView = PublicAPIRootView


router = Router()

urlpatterns = [
    path("token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # url_name: where the page loads the schema from; "api:" because of
    # the namespace of this file
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
    # The router last: its root pattern is "^$" (/api/ itself)
    *router.urls,
]
