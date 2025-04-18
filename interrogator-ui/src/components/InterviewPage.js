// src/components/InterviewPage.js

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/client';

export default function InterviewPage() {
  const { sessionId } = useParams();

  const [session, setSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [timer, setTimer] = useState(0);
  const [feedback, setFeedback] = useState(null);
  const [flags, setFlags] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState('');

  // intermission state
  const [intermission, setIntermission] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [loadingNext, setLoadingNext] = useState(false);

  const recorderRef = useRef(null);
  const [recordedBlob, setRecordedBlob] = useState(null);

  // load session & timer
  const loadSession = async () => {
    const { data } = await api.get(`sessions/${sessionId}/`);
    setSession(data);
    const startMs = new Date(data.started_at).getTime();
    setTimer(Math.max(0, Math.floor((startMs + 30 * 60 * 1000 - Date.now()) / 1000)));
  };

  // load questions
  const loadQuestions = async () => {
    const res = await api.get(`session-questions/?session=${sessionId}&ordering=asked_at`);
    setQuestions(Array.isArray(res.data) ? res.data : res.data.results ?? []);
  };

  // 1) mount: session, polling, timer
  useEffect(() => { loadSession(); }, [sessionId]);
  useEffect(() => {
    loadQuestions();
    const iq = setInterval(loadQuestions, 2000);
    return () => clearInterval(iq);
  }, [sessionId]);
  useEffect(() => {
    if (timer <= 0) return;
    const tid = setInterval(() => {
      setTimer(t => {
        if (t <= 1) { clearInterval(tid); handleFinish(); return 0; }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(tid);
  }, [timer]);

  // 2) start recording
  useEffect(() => {
    async function startRec() {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
      const chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = () => {
        setRecordedBlob(new Blob(chunks, { type: 'video/webm' }));
        stream.getTracks().forEach(t => t.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
    }
    startRec();
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
    };
  }, []);

  // 3) submit answer → evaluate → intermission
  const submitAnswer = async sq => {
    if (!currentAnswer.trim()) return;
    setSubmitting(true);
    try {
      await api.patch(`session-questions/${sq.id}/`, { answer_text: currentAnswer });
      setCurrentAnswer('');
      await loadQuestions(); // pick up score
      // begin intermission
      setIntermission(true);
      setCountdown(5);
      const cid = setInterval(() => {
        setCountdown(c => {
          if (c <= 1) {
            clearInterval(cid);
            setIntermission(false);
            fetchNextQuestion();
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    } finally {
      setSubmitting(false);
    }
  };

  // 4) explicit next question
  const fetchNextQuestion = async () => {
    setLoadingNext(true);
    try {
      await api.post(`sessions/${sessionId}/next_question/`);
      await loadQuestions();
    } catch (err) {
      console.error('Next question failed', err);
    } finally {
      setLoadingNext(false);
    }
  };

  // 5) finish interview
  const handleFinish = async () => {
    const lastQ = questions[questions.length - 1] || {};
    const waitingForScore = lastQ.answer_text && lastQ.score == null;
    if (waitingForScore) return;

    if (finishing) return;
    setFinishing(true);
    setFinishError('');
    try {
      await api.patch(`sessions/${sessionId}/`, { status: 'completed' });
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
    } catch (err) {
      setFinishError(
        err.response?.data?.detail ||
        JSON.stringify(err.response?.data) ||
        err.message
      );
    } finally {
      setFinishing(false);
    }
  };

  // 6) upload + feedback polling
  useEffect(() => {
    if (!recordedBlob) return;
    (async () => {
      setFeedback(null);
      const form = new FormData();
      form.append('session', sessionId);
      form.append('video_url', recordedBlob, 'interview.webm');
      await api.post('videos/', form);

      while (true) {
        const fbRes = await api.get(`feedback/?session=${sessionId}`);
        const arr = Array.isArray(fbRes.data) ? fbRes.data : fbRes.data.results ?? [];
        if (arr.length) { setFeedback(arr[0]); break; }
        await new Promise(r => setTimeout(r, 2000));
      }
      const flagsRes = await api.get(`flags/?recording__session=${sessionId}`);
      setFlags(flagsRes.data.results ?? flagsRes.data);
    })();
  }, [recordedBlob, sessionId]);

  // --- RENDER ---
  if (!session) return <div>Loading…</div>;
  if (feedback) {
    return (
      <div style={{ padding: '2rem' }}>
        <h2>Interview Completed</h2>
        <h3>Overall Score: {feedback.detailed_breakdown?.total_score ?? 'N/A'}</h3>
        <p>{feedback.summary}</p>
        <h4>Detailed Breakdown</h4>
        <pre>{JSON.stringify(feedback.detailed_breakdown, null, 2)}</pre>
        {flags.length > 0 && (
          <>
            <h4>Cheating Flags</h4>
            <ul>
              {flags.map(f => (
                <li key={f.id}>
                  [{f.timestamp}] <strong>{f.flag_type}</strong>: {f.description}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    );
  }

  // live view
  const mins = String(Math.floor(timer / 60)).padStart(2, '0');
  const secs = String(timer % 60).padStart(2, '0');
  const lastQ = questions[questions.length - 1] || {};
  const waitingForScore = lastQ.answer_text && lastQ.score == null;

  // **only show “old” questions during intermission**
  const displayQuestions = intermission
    ? questions.slice(0, questions.length - 1)
    : questions;

  return (
    <div style={{ display: 'flex', padding: '2rem' }}>
      <div style={{ flex: 1, marginRight: '2rem' }}>
        <h2>Interview Session #{sessionId}</h2>
        <h3>Time Remaining: {mins}:{secs}</h3>

        {displayQuestions.map(q => (
          <div key={q.id} style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '1rem' }}>
            <p><strong>Q:</strong> {q.question ? q.question.text : <em>Loading…</em>}</p>
            {q.answer_text && (
              <>
                <p><strong>Your Answer:</strong> {q.answer_text}</p>
                {q.score != null && (
                  <p><strong>Score:</strong> {q.score} (confidence {Math.round(q.confidence * 100)}%)</p>
                )}
              </>
            )}
          </div>
        ))}

        <div style={{ marginBottom: '1rem' }}>
          {waitingForScore && <p style={{ color: 'orange' }}>Waiting for evaluation…</p>}

          {!waitingForScore && lastQ.question && !lastQ.answer_text && (
            <>
              <textarea
                rows={4}
                style={{ width: '100%' }}
                value={currentAnswer}
                onChange={e => setCurrentAnswer(e.target.value)}
                disabled={submitting}
              />
              <button
                onClick={() => submitAnswer(lastQ)}
                disabled={submitting}
                style={{ marginTop: '0.5rem' }}
              >
                {submitting ? 'Submitting…' : 'Submit Answer'}
              </button>
            </>
          )}

          {!waitingForScore && lastQ.answer_text && !intermission && (
            <button
              onClick={() => {
                setIntermission(true);
                setCountdown(5);
                const cid = setInterval(() => {
                  setCountdown(c => {
                    if (c <= 1) {
                      clearInterval(cid);
                      setIntermission(false);
                      fetchNextQuestion();
                      return 0;
                    }
                    return c - 1;
                  });
                }, 1000);
              }}
              disabled={loadingNext}
              style={{ marginTop: '0.5rem' }}
            >
              {loadingNext ? 'Loading Next…' : 'Next Question'}
            </button>
          )}

          {intermission && <p>Next question in {countdown}s…</p>}
        </div>

        {finishError && <div style={{ color: 'red', marginBottom: '1rem' }}><strong>Error:</strong> {finishError}</div>}

        <button
          onClick={handleFinish}
          disabled={finishing || waitingForScore}
        >
          {finishing ? 'Finishing…' : 'Finish Interview Now'}
        </button>
      </div>
    </div>
  );
}
