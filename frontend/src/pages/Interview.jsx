import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { submitAnswer } from "../api";
import { useAuth } from "../context/AuthContext";

export function Interview() {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);

  const questionId = location.state?.questionId;
  const questionText = location.state?.questionText;

  // Phase 1 has no "resume this session" endpoint, so a hard refresh loses the in-flight
  // question. That's a known Phase 1 limitation, not a bug — surfaced honestly instead of
  // silently breaking.
  if (!questionId || !questionText) {
    return (
      <div className="page-center">
        <div className="card">
          <p>
            No active question found for this session — this happens after a page refresh,
            since Phase 1's backend doesn't support resuming an in-progress session yet.
          </p>
          <button onClick={() => navigate("/")}>Start a new interview</button>
        </div>
      </div>
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await submitAnswer({ sessionId, questionId, answerText: answer });
      setComplete(!result.has_next);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <h2>Interview</h2>
        <button className="link" onClick={signOut}>
          Sign out
        </button>
      </header>

      <div className="chat">
        <div className="bubble interviewer">{questionText}</div>
      </div>

      {complete ? (
        <div className="card">
          <p>
            Answer recorded. That's the end of this interview for now — it was scored
            internally, but nothing is shown here by design. Follow-up questions, multi-question
            flow, and a results screen land in later phases.
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
