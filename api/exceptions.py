"""Errors of the API that DRF doesn't have."""

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """409 Conflict: the request is correct, the state of the data forbids it.

    Deleting a book that is in orders, cancelling an order that is already
    paid. Raised in a view: DRF turns it into {"detail": "<text>"}, 409.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = _("The object is used by other objects and can't be deleted.")
    default_code = "conflict"
