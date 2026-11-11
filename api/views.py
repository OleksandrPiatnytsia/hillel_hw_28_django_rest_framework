"""Views of the API that are not about one model: tokens and the API root.

The ViewSets of the catalog and the orders come in their own modules.
"""

import logging

from rest_framework.permissions import AllowAny
from rest_framework.routers import APIRootView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

logger = logging.getLogger(__name__)  # "api.views"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """POST /api/token/: username + password -> access and refresh tokens.

    The same view as in simplejwt, with two additions:

    1. Its own request limit, "token" in DEFAULT_THROTTLE_RATES (10 per
       minute from one IP address). Every request checks a password, so
       the general 100/hour of anonymous users would allow too many
       guesses in a burst. ScopedRateThrottle reads throttle_scope and
       counts the requests of this scope only.
    2. A log line for every issued pair of tokens. A wrong password is
       already logged: simplejwt calls django.contrib.auth.authenticate(),
       which sends the user_login_failed signal (users/signals.py).

    Request:   {"username": "ann", "password": "..."}
    Answer:    200 {"access": "eyJ...", "refresh": "eyJ..."}
               401 {"detail": "No active account found with the given credentials"}
               429 {"detail": "Request was throttled. Expected available in 42 seconds."}
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Here only after a successful login: a wrong password raises
        # AuthenticationFailed inside super().post() and DRF answers 401
        # without coming back here
        logger.info(
            "API token issued: user=%s ip=%s",
            request.data.get("username", "-"),
            request.META.get("REMOTE_ADDR", "-"),
        )
        return response


class PublicAPIRootView(APIRootView):
    """GET /api/: the list of the API sections, open to everybody.

    DefaultRouter builds this page from the registered ViewSets
    ({"books": "http://.../api/books/", ...}). By default it would take
    DEFAULT_PERMISSION_CLASSES (IsAuthenticated) and answer 401 to an
    anonymous visitor, although the catalog behind its links is public.
    """

    permission_classes = [AllowAny]
