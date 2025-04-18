from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminOrReadOnly(BasePermission):
    """
    Allow anyone to GET, but only staff users to POST/PUT/DELETE.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

class IsOwnerOrAdmin(BasePermission):
    """
    Object-level: allow access if user is staff OR
    (for objects with .candidate) user == obj.candidate.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # for models that have a `candidate` FK
        if hasattr(obj, 'candidate'):
            return obj.candidate == request.user
        return False

class IsSessionOwnerOrAdmin(BasePermission):
    """
    Object-level: allow if user is staff OR
    user == obj.session.candidate.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # for SessionQuestion, VideoRecording, Feedback, CheatingFlag
        session = getattr(obj, 'session', None)
        if session is not None:
            return session.candidate == request.user
        # for CheatingFlag which has recording.session
        recording = getattr(obj, 'recording', None)
        if recording is not None:
            return recording.session.candidate == request.user
        return False

