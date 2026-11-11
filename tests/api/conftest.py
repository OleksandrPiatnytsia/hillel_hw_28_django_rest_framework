"""Fixtures of the API tests (on top of tests/conftest.py: customer, manager, ...).

APIClient (Django REST Framework) instead of django.test.Client:
    - post(url, data, format="json") sends JSON, not a form;
    - credentials(HTTP_AUTHORIZATION="Bearer ...") adds the header to
      every next request;
    - force_authenticate(user) logs in without a token and without a
      session: for the tests that are not about authentication.
response.json() of APIClient is the parsed JSON answer.
"""

import pytest
from rest_framework.test import APIClient

from tests.factories import DEFAULT_PASSWORD


@pytest.fixture
def api_client():
    """Not logged in: an anonymous visitor / an external service without a token."""
    return APIClient()


@pytest.fixture
def get_tokens(api_client):
    """POST /api/token/ for a user -> {"access": ..., "refresh": ...}.

    A function, not ready tokens: a test calls it for the user it needs,
    get_tokens(customer). The real login (password check), like a client of
    the API does it.
    """

    def _get_tokens(user, password=DEFAULT_PASSWORD):
        response = api_client.post(
            "/api/token/",
            {"username": user.username, "password": password},
            format="json",
        )
        assert response.status_code == 200, response.content
        return response.json()

    return _get_tokens
