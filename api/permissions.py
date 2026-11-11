"""Permission classes of the API.

A permission class answers "may this request go on?":
    has_permission(request, view)            before the view, for every request
    has_object_permission(request, view, obj) for one object (retrieve,
                                              update, delete), after get_object()
False -> 401 for an anonymous user (with a token or a session the request could
pass), 403 for a logged-in one.

Several classes in permission_classes = ALL of them must allow.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsStaffOrReadOnly(BasePermission):
    """Read (GET, HEAD, OPTIONS) for everybody; write only for staff (is_staff).

    The same as IsAdminUser of DRF for writing; DRF has no "or read only"
    version of it. Used together with DjangoModelPermissionsOrAnonReadOnly
    for authors and categories: like in the admin, a write needs BOTH the
    staff flag and the permission of the group ("Managers" may delete a
    category, "Editors" may not).
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrReadOnly(BasePermission):
    """Read for everybody who got the object; change only for its owner.

    An object-level permission: DRF calls has_object_permission() after
    get_object() found the object (retrieve, update, delete, our "cancel"
    action), not for lists.

    Orders: the queryset of OrderViewSet already decides WHAT a user may
    see (a customer: own orders, someone else's -> 404; staff: all). This
    class decides who may CHANGE an order: only its owner. A manager reads
    every order, but cancels a customer's order in the admin, where the
    rules of a manager apply (refund, the shipped state), not here: 403.

    The model needs a "user" field (the owner).
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user_id == request.user.pk
