import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getNextQuestion, submitAnswer } from "../api";
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
  const [complete, setComplete] = useState(false);

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
        // A 404 here means the interview's already done (e.g. resuming after it finished).
        if (err.message?.includes("complete") || err.message?.includes("No pending question")) {
          setComplete(true);
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
      setAnswer("");

      if (!result.has_next) {
        setComplete(true);
        return;
      }

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
        <button className="link" onClick={signOut}>
          Sign out
        </button>
      </header>

      {question && (
        <div className="chat">
          {question.isFollowup && <p className="muted">Follow-up:</p>}
          <div className="bubble interviewer">{question.questionText}</div>
        </div>
      )}

      {complete ? (
        <div className="card">
          <p>
            Interview complete. Every answer was scored internally, but nothing is shown here by
            design — a results screen with the full breakdown lands in Phase 4.
          </p>
          <button onClick={() => navigate("/")}>Start another interview</button>
        </div>
      ) : (
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
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? "Submitting…" : "Submit answer"}
          </button>
        </form>
      )}
    </div>
  );
}
