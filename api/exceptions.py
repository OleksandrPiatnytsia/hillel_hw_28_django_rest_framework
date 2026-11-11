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


class IdempotencyKeyReused(APIException):
    """422: the Idempotency-Key was already used for a DIFFERENT request.

    The same key means "the same request again"; other books or another
    address with an old key is a mistake of the client (a key copied
    instead of a new one), not a retry. Returning the old order would hide
    it, creating a new one would break the promise of the key.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _(
        "This Idempotency-Key was already used for a different order. "
        "Send a new key for a new order."
    )
    default_code = "idempotency_key_reused"
