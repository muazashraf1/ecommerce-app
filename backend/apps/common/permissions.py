from rest_framework.permissions import BasePermission

class IsAdminRole(BasePermission):
    """
    Allows access only to authenticated users with role='admin'.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'admin' or request.user.is_staff or request.user.is_superuser)
        )

class IsCustomerRole(BasePermission):
    """
    Allows access to authenticated customers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'customer'
        )

class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission to only allow owners of an object or admins to view/edit it.
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == 'admin' or request.user.is_staff:
            return True
        return hasattr(obj, 'user') and obj.user == request.user
