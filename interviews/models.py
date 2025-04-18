from django.db import models
from django.contrib.auth.models import User

class Resume(models.Model):
    #candidate    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resumes')
    candidate    = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='resumes',
        null=True,
        blank=True,
        help_text="Null for unauthenticated uploads")
    file         = models.FileField(upload_to='resumes/')
    parsed_data  = models.JSONField(blank=True, null=True,
                                    help_text="Structured skills/experience extracted from the resume")
    uploaded_at  = models.DateTimeField(auto_now_add=True)

class Question(models.Model):
    text        = models.TextField()
    skill_tag   = models.CharField(max_length=100)
    difficulty  = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    created_at  = models.DateTimeField(auto_now_add=True)

class InterviewSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    candidate   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interviews',
        help_text="Null for unauthenticated sessions"
    )
    resume      = models.ForeignKey(Resume, on_delete=models.SET_NULL, null=True)
    started_at  = models.DateTimeField(auto_now_add=True)
    ended_at    = models.DateTimeField(blank=True, null=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_score = models.FloatField(blank=True, null=True)

class SessionQuestion(models.Model):
    session      = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='questions')
    question     = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True)
    asked_at     = models.DateTimeField(auto_now_add=True)
    answer_text  = models.TextField(blank=True, null=True)
    answered_at  = models.DateTimeField(blank=True, null=True)
    time_spent   = models.DurationField(
        blank=True,
        null=True,
        help_text="Time delta between asked_at and answered_at"
    )
    score        = models.FloatField(blank=True, null=True,
                                     help_text="Score for this question, e.g. 0–10")
    confidence   = models.FloatField(blank=True, null=True,
                                     help_text="Model confidence in its evaluation (0–1)")
    follow_up    = models.BooleanField(default=False)

    class Meta:
        ordering = ['asked_at']

    def save(self, *args, **kwargs):
        # Auto-calc time_spent when answered_at is set
        if self.answered_at and self.asked_at:
            self.time_spent = self.answered_at - self.asked_at
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Q#{self.question_id} in S#{self.session_id}"


class Feedback(models.Model):
    session            = models.OneToOneField(InterviewSession, on_delete=models.CASCADE, related_name='feedback')
    summary            = models.TextField()
    detailed_breakdown = models.JSONField()
    created_at         = models.DateTimeField(auto_now_add=True)

class VideoRecording(models.Model):
    session    = models.OneToOneField(InterviewSession, on_delete=models.CASCADE, related_name='video')
    video_url  = models.URLField()
    processed  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class CheatingFlag(models.Model):
    recording   = models.ForeignKey(VideoRecording, on_delete=models.CASCADE, related_name='flags')
    flag_type   = models.CharField(max_length=100)
    description = models.TextField()
    timestamp   = models.DateTimeField()
