import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteSession, getTrends, listSessions } from "../api";
import { TopBar } from "../components/TopBar";
import { TrendChart } from "../components/TrendChart";

const TREND_LABEL = {
  improving: "Improving 📈",
  flat_or_declining: "Flat or declining",
  not_enough_data: "Not enough data yet",
};

// The trend compares your latest completed interview against your first, so it needs two.
const TREND_HINT = {
  improving: "Latest score is above your first",
  flat_or_declining: "Latest score isn't above your first",
  not_enough_data: "Complete 2+ interviews to see a trend",
};

export function History() {
  const [sessions, setSessions] = useState([]);
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  async function handleDelete(session) {
    const ok = window.confirm(
      `Delete this ${session.role} session from ${new Date(session.created_at).toLocaleDateString()}? ` +
        "Its questions, answers and results will be removed permanently.",
    );
    if (!ok) return;

    setError("");
    setDeletingId(session.session_id);
    try {
      await deleteSession({ sessionId: session.session_id });
      setSessions((prev) => prev.filter((s) => s.session_id !== session.session_id));
      // A deleted completed session drops out of the average/trend too.
      if (session.status === "completed") setTrend(await getTrends());
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([listSessions(), getTrends()])
      .then(([sessionsData, trendData]) => {
        if (cancelled) return;
        setSessions(sessionsData);
        setTrend(trendData);
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
  }, []);

  return (
    <div className="page">
      <TopBar links={[{ to: "/", label: "New interview" }]} />
      <h1 className="page-title">History</h1>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}

      {trend && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ margin: 0 }}>Score over time</h3>
          <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
            Based on your {trend.sessions.length} completed{" "}
            {trend.sessions.length === 1 ? "interview" : "interviews"}. Each interview's score is
            the average of its per-answer scores (1–5).
          </p>
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-value">{trend.avg_score !== null ? trend.avg_score.toFixed(1) : "—"}</div>
              <div className="stat-label">Average score (out of 5)</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value" style={{ fontSize: "1.1rem" }}>
                {TREND_LABEL[trend.trend]}
              </div>
              <div className="stat-label">{TREND_HINT[trend.trend]}</div>
            </div>
          </div>
          <TrendChart sessions={trend.sessions} />
        </div>
      )}

      <div className="card">
        <h3 style={{ margin: 0 }}>Past sessions</h3>
        {sessions.length === 0 ? (
          <p className="muted">No sessions yet.</p>
        ) : (
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.session_id}>
                <div>
                  <strong>{s.role}</strong>{" "}
                  <span className="muted">{new Date(s.created_at).toLocaleDateString()}</span>
                </div>
                <div className="session-actions">
                  <span className={`status-badge ${s.status}`}>{s.status.replace("_", " ")}</span>
                  {s.status === "completed" ? (
                    <Link to={`/results/${s.session_id}`}>View results</Link>
                  ) : (
                    <Link to={`/interview/${s.session_id}`}>Resume</Link>
                  )}
                  <button
                    type="button"
                    className="link danger"
                    onClick={() => handleDelete(s)}
                    disabled={deletingId === s.session_id}
                  >
                    {deletingId === s.session_id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
