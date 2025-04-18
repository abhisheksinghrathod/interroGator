from django.contrib import admin
from .models import Resume, Question, InterviewSession, SessionQuestion, Feedback, VideoRecording, CheatingFlag

admin.site.register([Resume, Question, InterviewSession, SessionQuestion, Feedback, VideoRecording, CheatingFlag])

