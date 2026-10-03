import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getNextQuestion, isServiceUnavailable, submitAnswer, transcribeAudio } from "../api";
import { TopBar } from "../components/TopBar";
import { ServiceNotice } from "../components/ServiceNotice";

export function Interview() {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Seeded from router state when arriving fresh from NewSession; re-fetched from the backend
  // on mount otherwise (page refresh, or arriving via a bookmarked/shared URL) — the pending
  // question lives in Supabase now, not just in this router state.
  const [question, setQuestion] = useState(
    location.state?.questionId
      ? {
          questionId: location.state.questionId,
          questionText: location.state.questionText,
          isFollowup: false,
          questionNumber: location.state.questionNumber,
          totalQuestions: location.state.totalQuestions,
        }
      : null,
  );
  const [loadingQuestion, setLoadingQuestion] = useState(!location.state?.questionId);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState(null); // the raw Error, so isServiceUnavailable can inspect it
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
          questionNumber: data.question_number,
          totalQuestions: data.total_questions,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        // A 404 here means the interview's already done (e.g. resuming after it finished) —
        // the results screen is the right place to land, not a dead end on this page.
        if (err.message?.includes("complete") || err.message?.includes("No pending question")) {
          navigate(`/results/${sessionId}`, { replace: true });
        } else {
          setError(err);
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

  function speak(text) {
    if (!("speechSynthesis" in window)) {
      setError(new Error("Voice output isn't supported in this browser."));
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  // Reads each question aloud automatically the moment it's ready — like an interviewer
  // actually asking it, not text you have to remember to play. Also cancels any in-flight
  // speech when the question changes or the page is left, so a stale question's audio never
  // keeps playing over a new one.
  useEffect(() => {
    if (question) speak(question.questionText);
    return () => window.speechSynthesis?.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.questionId]);

  function handleReadAloud() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    speak(question.questionText);
  }

  async function handleStartRecording() {
    setError(null);
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
          // Appended, not replaced — lets someone answer across a couple of takes (natural
          // pauses) without losing what they'd already said. There's no typing here to fix a
          // bad take with, so a full restart is what "Clear" below is for.
          setAnswer((prev) => (prev ? `${prev} ${text}` : text));
        } catch (err) {
          setError(err);
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError(new Error("Couldn't access the microphone — check your browser's permission settings."));
    }
  }

  function handleStopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
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
        questionNumber: next.question_number,
        totalQuestions: next.total_questions,
      });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (loadingQuestion) {
    return <div className="page-center">Loading your question…</div>;
  }

  return (
    <div className="page">
      <TopBar links={[{ to: "/history", label: "History" }]} />
      <h1 className="page-title">Interview</h1>

      {question?.totalQuestions > 0 && (
        <div className="interview-progress">
          <div className="interview-progress-label muted">
            Question {question.questionNumber} of {question.totalQuestions}
            {question.isFollowup && " · follow-up"}
          </div>
          <div
            className="interview-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={question.totalQuestions}
            aria-valuenow={question.questionNumber}
          >
            <div
              className="interview-progress-fill"
              style={{ width: `${(question.questionNumber / question.totalQuestions) * 100}%` }}
            />
          </div>
        </div>
      )}

      {question && (
        <div className="chat">
          {question.isFollowup && <p className="muted">Follow-up:</p>}
          <div className="bubble interviewer">{question.questionText}</div>
          <button type="button" className="link" onClick={handleReadAloud}>
            {speaking ? "⏹ Stop" : "🔊 Replay question"}
          </button>

          {answer && <div className="bubble candidate">{answer}</div>}
        </div>
      )}

      <form className="card" onSubmit={handleSubmit}>
        <div className="voice-controls">
          {recording ? (
            <button type="button" onClick={handleStopRecording} className="recording">
              ⏹ Stop recording
            </button>
          ) : (
            <button type="button" onClick={handleStartRecording} disabled={busy || transcribing}>
              🎤 {answer ? "Record more" : "Record answer"}
            </button>
          )}
          {answer && !recording && (
            <button
              type="button"
              className="link"
              onClick={() => setAnswer("")}
              disabled={busy || transcribing}
            >
              🗑 Clear
            </button>
          )}
          {transcribing && <span className="muted">Transcribing…</span>}
        </div>

        {error &&
          (isServiceUnavailable(error) ? (
            <ServiceNotice message={error.message} />
          ) : (
            <p className="error">{error.message}</p>
          ))}
        <button type="submit" disabled={busy || recording || transcribing || !answer}>
          {busy ? "Submitting…" : "Submit answer"}
        </button>
      </form>
    </div>
  );
}
