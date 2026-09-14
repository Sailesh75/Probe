import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSummary } from "../api";
import { useAuth } from "../context/AuthContext";

export function Results() {
  const { sessionId } = useParams();
  const { signOut } = useAuth();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSummary({ sessionId })
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <div className="page">
      <header className="topbar">
        <h2>Results</h2>
        <div className="nav-links">
          <Link to="/history">History</Link>
          <Link to="/">New interview</Link>
          <button className="link" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      {loading && <p className="muted">Loading results…</p>}
      {error && <p className="error">{error}</p>}

      {summary && (
        <>
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-value">{summary.overall_score.toFixed(1)} / 5</div>
              <div className="stat-label">Overall score</div>
            </div>
            <div className="stat-tile" style={{ flex: 2 }}>
              <p style={{ margin: 0 }}>{summary.overall_feedback}</p>
            </div>
          </div>

          {summary.patterns.length > 0 && (
            <div className="card" style={{ marginTop: "1.5rem" }}>
              <h3 style={{ margin: 0 }}>Recurring patterns</h3>
              <ul className="pattern-list">
                {summary.patterns.map((p) => (
                  <li key={p.issue}>
                    {p.issue} <span className="muted">— {p.count} answers</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card" style={{ marginTop: "1.5rem" }}>
            <h3 style={{ margin: 0 }}>Per-question breakdown</h3>
            {summary.questions.map((q, i) => (
              <div className="question-breakdown" key={i}>
                <p style={{ margin: "0 0 0.4rem" }}>
                  <strong>
                    Q{i + 1}
                    {q.is_followup ? " (follow-up)" : ""}:
                  </strong>{" "}
                  {q.question_text}
                  <span className="score-badge">{q.score}/5</span>
                </p>
                <p className="muted" style={{ margin: "0 0 0.4rem" }}>
                  Your answer: {q.answer_text}
                </p>
                <p style={{ margin: 0 }}>{q.feedback}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
