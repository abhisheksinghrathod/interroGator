from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Resume,
    Question,
    InterviewSession,
    SessionQuestion,
    Feedback,
    VideoRecording,
    CheatingFlag,
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class ResumeSerializer(serializers.ModelSerializer):
    candidate = UserSerializer(read_only=True)

    class Meta:
        model = Resume
        fields = ['id', 'candidate', 'file', 'parsed_data', 'uploaded_at']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'skill_tag', 'difficulty', 'created_at']


class SessionQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)
    question_id = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(),
        source='question',
        write_only=True
    )

    class Meta:
        model = SessionQuestion
        fields = [
            'id', 'session', 'question', 'question_id',
            'asked_at', 'answer_text', 'answered_at',
            'time_spent', 'score', 'confidence', 'follow_up',
        ]


class InterviewSessionSerializer(serializers.ModelSerializer):
    candidate = UserSerializer(read_only=True)
    resume_id = serializers.PrimaryKeyRelatedField(
        queryset=Resume.objects.all(),
        source='resume',
        write_only=True
    )
    questions = SessionQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = InterviewSession
        fields = [
            'id', 'candidate', 'resume', 'resume_id',
            'started_at', 'ended_at', 'status',
            'total_score', 'questions',
        ]
        read_only_fields = ['started_at', 'ended_at', 'total_score']


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'session', 'summary', 'detailed_breakdown', 'created_at']


class VideoRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoRecording
        fields = ['id', 'session', 'video_url', 'processed', 'created_at']


class CheatingFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheatingFlag
        fields = ['id', 'recording', 'flag_type', 'description', 'timestamp']
