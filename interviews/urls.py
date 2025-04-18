from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResumeViewSet,
    QuestionViewSet,
    InterviewSessionViewSet,
    SessionQuestionViewSet,
    FeedbackViewSet,
    VideoRecordingViewSet,
    CheatingFlagViewSet,
)

router = DefaultRouter()
router.register(r'resumes', ResumeViewSet)
router.register(r'questions', QuestionViewSet)
router.register(r'sessions', InterviewSessionViewSet)
router.register(r'session-questions', SessionQuestionViewSet)
router.register(r'feedback', FeedbackViewSet)
router.register(r'videos', VideoRecordingViewSet)
router.register(r'flags', CheatingFlagViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
