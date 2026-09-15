import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getNextQuestion, submitAnswer, transcribeAudio } from "../api";
import { useAuth } from "../context/AuthContext";

export function Interview() {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useAuth();

  // Seeded from router state when arriving fresh from NewSession; re-fetched from the backend
  // on mount otherwise (page refresh, or arriving via a bookmarked/shared URL) — the pending
  // question lives in Supabase now, not just in this router state.
  const [question, setQuestion] = useState(
    location.state?.questionId
      ? {
          questionId: location.state.questionId,
          questionText: location.state.questionText,
          isFollowup: false,
        }
      : null,
  );
  const [loadingQuestion, setLoadingQuestion] = useState(!location.state?.questionId);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [speaking, setSpeaking] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (question) return;

    let cancelled = false;
    getNextQuestion({ sessionId })
      .then((data) => {
        if (cancelled) return;
        setQuestion({
          questionId: data.question_id,
          questionText: data.question_text,
          isFollowup: data.is_followup,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        // A 404 here means the interview's already done (e.g. resuming after it finished) —
        // the results screen is the right place to land, not a dead end on this page.
        if (err.message?.includes("complete") || err.message?.includes("No pending question")) {
          navigate(`/results/${sessionId}`, { replace: true });
        } else {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingQuestion(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Stop any in-flight speech when the question changes or the page is left, so a stale
  // question's audio never keeps playing over a new one.
  useEffect(() => {
    return () => window.speechSynthesis?.cancel();
  }, [question?.questionId]);

  function handleReadAloud() {
    if (!("speechSynthesis" in window)) {
      setError("Voice output isn't supported in this browser.");
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(question.questionText);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  async function handleStartRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType });
        const file = new File([blob], "answer.webm", { type: recorder.mimeType });

        setTranscribing(true);
        try {
          const { text } = await transcribeAudio({ file });
          // Appended, not replaced — lets someone record in a couple of takes without
          // losing what they'd already typed or said.
          setAnswer((prev) => (prev ? `${prev} ${text}` : text));
        } catch (err) {
          setError(err.message);
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Couldn't access the microphone — check your browser's permission settings.");
    }
  }

  function handleStopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await submitAnswer({
        sessionId,
        questionId: question.questionId,
        answerText: answer,
      });

      if (!result.has_next) {
        navigate(`/results/${sessionId}`, { replace: true });
        return;
      }

      setAnswer("");
      const next = await getNextQuestion({ sessionId });
      setQuestion({
        questionId: next.question_id,
        questionText: next.question_text,
        isFollowup: next.is_followup,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (loadingQuestion) {
    return <div className="page-center">Loading your question…</div>;
  }

  return (
    <div className="page">
      <header className="topbar">
        <h2>Interview</h2>
        <div className="nav-links">
          <Link to="/history">History</Link>
          <button className="link" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      {question && (
        <div className="chat">
          {question.isFollowup && <p className="muted">Follow-up:</p>}
          <div className="bubble interviewer">{question.questionText}</div>
          <button type="button" className="link" onClick={handleReadAloud}>
            {speaking ? "⏹ Stop" : "🔊 Read aloud"}
          </button>
        </div>
      )}

      <form className="card" onSubmit={handleSubmit}>
        <label>
          Your answer
          <textarea
            rows={6}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            required
            disabled={busy}
          />
        </label>

        <div className="voice-controls">
          {recording ? (
            <button type="button" onClick={handleStopRecording} className="recording">
              ⏹ Stop recording
            </button>
          ) : (
            <button type="button" onClick={handleStartRecording} disabled={busy || transcribing}>
              🎤 Record answer
            </button>
          )}
          {transcribing && <span className="muted">Transcribing…</span>}
        </div>

        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || recording || transcribing}>
          {busy ? "Submitting…" : "Submit answer"}
        </button>
      </form>
    </div>
  );
}
