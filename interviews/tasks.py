# interviews/tasks.py

import os
import json
import re
from pathlib import Path
from django.db import transaction

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from dotenv import load_dotenv
import openai

from .models import (
    InterviewSession,
    SessionQuestion,
    VideoRecording,
    CheatingFlag,
    Question,
    Feedback,
)

# ─── Load your .env so OPENAI_API_KEY is in os.environ ───────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
# ────────────────────────────────────────────────────────────────────────────────

def get_openai_client():
    """
    Create an OpenAI client on demand, pulling the key
    from environment or Django settings.
    """
    api_key = (
            getattr(settings, 'OPENAI_API_KEY', None)
            or os.environ.get('OPENAI_API_KEY')
    )
    # DEBUG: log to verify (remove or lower level in production)
    if not api_key:
        raise openai.OpenAIError(
            "OPENAI_API_KEY must be set in .env or in settings.py"
        )
    return openai.OpenAI(api_key=api_key)


@shared_task
def generate_question(session_id):
    """
    Generate a new question for the given session using the LLM,
    then persist it by linking to or creating a Question instance.
    """
    session = InterviewSession.objects.get(pk=session_id)

    # Build the prompt
    prompt = (
        f"You are an AI interviewer. Candidate resume data:\n"
        f"{session.resume.parsed_data}\n\nPrevious Q&A:\n"
    )
    for sq in session.questions.all().order_by('asked_at'):
        prompt += f"Q: {sq.question.text}\nA: {sq.answer_text or '[no answer]'}\n\n"
    prompt += "Now generate one more relevant, role‑specific technical question."

    client = get_openai_client()
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=150,
    )
    q_text = resp.choices[0].message.content.strip()

    # Persist under a real Question record
    with transaction.atomic():
        question_obj, _ = Question.objects.get_or_create(
            text=q_text,
            defaults={
                'skill_tag': 'general',
                'difficulty': 1
            }
        )
        SessionQuestion.objects.create(
            session=session,
            question=question_obj,
            answer_text='',
            follow_up=False
        )

    return q_text


@shared_task
def evaluate_answer(session_question_id):
    """
    Score the candidate’s answer and mark follow‑up if needed.
    """
    sq = SessionQuestion.objects.get(pk=session_question_id)

    prompt = (
        f"You are an expert interviewer reviewing candidate answer.\n\n"
        f"Question:\n{sq.question.text}\n\n"
        f"Answer:\n{sq.answer_text}\n\n"
        "Return JSON with:\n"
        "  score: 0–10,\n"
        "  confidence: 0.0–1.0,\n"
        "  follow_up: boolean,\n"
        "  follow_up_question: string (if follow_up is true)\n"
    )

    client = get_openai_client()
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=200,
    )
    result = json.loads(resp.choices[0].message.content)

    sq.score = result.get('score')
    sq.confidence = result.get('confidence')
    if result.get('follow_up'):
        sq.follow_up = True
        # Optionally store follow_up_question somewhere
    sq.save()

    return result


@shared_task
def process_video(recording_id):
    """
    Analyze the interview video for cheating flags, using current datetime
    for the flag timestamp field.
    """
    rec = VideoRecording.objects.get(pk=recording_id)

    # TODO: replace with real CV/cheat-detection integration
    # Here we simulate two flags, but use timezone.now() for the DB
    raw_flags = [
        {
            'flag_type': 'multiple_faces',
            'description': 'Detected 2 faces at 00:02:34',
        },
        {
            'flag_type': 'off_screen_lookup',
            'description': 'Gaze away > 10s starting 00:10:12',
        },
    ]

    for f in raw_flags:
        CheatingFlag.objects.create(
            recording=rec,
            flag_type=f['flag_type'],
            description=f['description'],
            timestamp=timezone.now()  # use a valid datetime
        )

    rec.processed = True
    rec.save()
    return [ { **f, 'timestamp': str(timezone.now()) } for f in raw_flags ]


@shared_task
def generate_feedback(session_id):
    session = InterviewSession.objects.get(pk=session_id)
    sqs = list(session.questions.order_by('asked_at').all())

    # 1) Compute totals
    num_q = len(sqs)
    total_raw = sum((sq.score or 0) for sq in sqs)
    total_pct = (total_raw / (num_q * 10) * 100) if num_q else 0

    # Per‑skill breakdown
    tag_sums = {}
    tag_counts = {}
    for sq in sqs:
        tag = sq.question.skill_tag or 'other'
        tag_sums[tag] = tag_sums.get(tag, 0) + (sq.score or 0)
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    categories = {
        tag: (tag_sums[tag] / tag_counts[tag]) if tag_counts[tag] else 0
        for tag in tag_sums
    }

    # 2) Build QA pairs
    qa_pairs = []
    for sq in sqs:
        qa_pairs.append({
            "question": sq.question.text if sq.question else None,
            "answer": sq.answer_text,
            "score": sq.score or 0
        })

    data = {
        "total_score": round(total_pct, 1),
        "categories": {tag: round(score, 1) for tag, score in categories.items()},
        "qa_pairs": qa_pairs,
    }

    # 3) Build summary
    answered = sum(1 for sq in sqs if sq.answer_text)
    avg_score = (total_raw / num_q) if num_q else 0
    summary = (
        f"Candidate answered {answered} out of {num_q} questions, "
        f"with an average score of {avg_score:.1f}/10 "
        f"({data['total_score']}%)."
    )
    flags = CheatingFlag.objects.filter(recording__session=session)
    if flags.exists():
        summary += f" Detected {flags.count()} cheating flag(s)."

    # 4) Persist Feedback
    Feedback.objects.update_or_create(
        session=session,
        defaults={
            "detailed_breakdown": data,
            "summary": summary,
        }
    )

    return {"session": session_id, "breakdown": data}
