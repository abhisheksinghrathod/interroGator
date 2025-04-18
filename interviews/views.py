# interviews/views.py

import os
import logging

import PyPDF2
import docx
import textract
from django.core.files.storage import default_storage
from rest_framework import viewsets, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .tasks import (
    generate_question,
    evaluate_answer,
    process_video,
    generate_feedback,
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin, IsSessionOwnerOrAdmin
from .models import (
    Resume,
    Question,
    InterviewSession,
    SessionQuestion,
    Feedback,
    VideoRecording,
    CheatingFlag,
)
from .serializers import (
    ResumeSerializer,
    QuestionSerializer,
    InterviewSessionSerializer,
    SessionQuestionSerializer,
    FeedbackSerializer,
    VideoRecordingSerializer,
    CheatingFlagSerializer,
)

logger = logging.getLogger(__name__)


class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.order_by('-uploaded_at')
    serializer_class = ResumeSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        logger.info("Received resume upload request")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resume = serializer.save(
            candidate=request.user if request.user.is_authenticated else None
        )
        logger.info("Saved Resume(id=%d) file=%s", resume.id, resume.file.name)

        # parse for PDF/DOCX or fallback to textract
        try:
            path = resume.file.path
            ext = os.path.splitext(path)[1].lower()
            text = ""

            if ext == '.pdf':
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text() or ""
                        text += t + "\n"
            elif ext in ('.doc', '.docx'):
                doc_obj = docx.Document(path)
                for para in doc_obj.paragraphs:
                    text += para.text + "\n"
            else:
                text = textract.process(path).decode('utf-8')

            resume.parsed_data = text[:5000]
            resume.save()
            logger.info("Parsed Resume(id=%d): %d chars", resume.id, len(resume.parsed_data))
        except Exception as e:
            logger.exception("Resume parsing failed for Resume(id=%d)", resume.id)

        return Response(
            self.get_serializer(resume).data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data)
        )


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]


class InterviewSessionViewSet(viewsets.ModelViewSet):
    """
    Publicly callable: start sessions and seed the first question.
    """
    queryset = InterviewSession.objects.all()
    serializer_class = InterviewSessionSerializer

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def perform_create(self, serializer):
        session = serializer.save()
        logger.info("Created InterviewSession(id=%d)", session.id)
        try:
            generate_question(session.id)
            logger.info("generate_question run for Session(id=%d)", session.id)
        except Exception:
            logger.exception("generate_question failed for Session(id=%d)", session.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        logger.info("InterviewSession.create called with data: %s", request.data)

        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except ValidationError:
            logger.error("Session creation validation errors: %s", request.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data)
        )


class SessionQuestionViewSet(viewsets.ModelViewSet):
    """
    Questions are system-generated; on answer update we evaluate and generate the next question.
    """
    queryset = SessionQuestion.objects.select_related('question', 'session').all()
    serializer_class = SessionQuestionSerializer

    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        session_id = self.request.query_params.get('session')
        qs = SessionQuestion.objects.select_related('question', 'session')
        if session_id:
            qs = qs.filter(session_id=session_id)
        return qs.order_by('asked_at')

    def perform_create(self, serializer):
        raise ValidationError("SessionQuestions are created by the system.")

    def perform_update(self, serializer):
        sq = serializer.save()
        logger.info("Answer submitted for SessionQuestion(id=%d)", sq.id)
        if sq.answer_text:
            try:
                evaluate_answer(sq.id)
                logger.info("evaluate_answer run for SQ(id=%d)", sq.id)
            except Exception:
                logger.exception("evaluate_answer failed for SQ(id=%d)", sq.id)
            try:
                generate_question(sq.session.id)
                logger.info("generate_question run for Session(id=%d)", sq.session.id)
            except Exception:
                logger.exception("generate_question failed for Session(id=%d)", sq.session.id)
        return sq


class FeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint for final feedback summaries.
    """
    queryset = Feedback.objects.all().order_by('-id')
    serializer_class = FeedbackSerializer

    authentication_classes = []
    permission_classes = [AllowAny]
    # disable the browsable API here so DRF never looks for api.html
    renderer_classes = [JSONRenderer]


class VideoRecordingViewSet(viewsets.ModelViewSet):
    """
    Accepts a multipart upload under 'video_url', stores it,
    converts to an absolute URL, then kicks off processing & feedback.
    """
    queryset = VideoRecording.objects.all()
    serializer_class = VideoRecordingSerializer

    # Accept multipart form data
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """
        Accept a multipart upload under 'video_url', store it to MEDIA,
        convert to an absolute URL, then save the VideoRecording.
        """
        # 1) Get the session ID safely
        session_id = request.POST.get('session') or request.data.get('session')
        logger.info("Video upload start for session=%s", session_id)

        # 2) Ensure a file was uploaded
        if 'video_url' not in request.FILES:
            logger.error("No 'video_url' file in request")
            return Response(
                {"video_url": ["No file provided."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3) Save the uploaded file to MEDIA_ROOT/videos/
        uploaded = request.FILES['video_url']
        path = default_storage.save(f'videos/{uploaded.name}', uploaded)
        rel_url = default_storage.url(path)
        abs_url = request.build_absolute_uri(rel_url)
        logger.info("Stored uploaded video to %s (URL: %s)", path, abs_url)

        # 4) Build our clean data dict
        data = {
            "session": session_id,
            "video_url": abs_url,
        }

        # 5) Validate & save via serializer
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            logger.error("VideoRecording validation errors: %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        video = serializer.save()
        logger.info("Saved VideoRecording(id=%d) for Session(id=%s)", video.id, video.session_id)

        # 6) Run cheat‑detection inline
        try:
            process_video.run(video.id)
            logger.info("process_video.run() completed for VideoRecording(id=%d)", video.id)
        except Exception:
            logger.exception("process_video.run() failed for VideoRecording(id=%d)", video.id)

        # 7) Generate final feedback inline
        try:
            generate_feedback.run(video.session_id)
            logger.info("generate_feedback.run() completed for Session(id=%d)", video.session_id)
        except Exception:
            logger.exception("generate_feedback.run() failed for Session(id=%d)", video.session_id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CheatingFlagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only listing of cheating flags.
    """
    queryset = CheatingFlag.objects.all()
    serializer_class = CheatingFlagSerializer

    authentication_classes = []
    permission_classes = [AllowAny]
