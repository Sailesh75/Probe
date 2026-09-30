import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTrends, listSessions } from "../api";
import { TopBar } from "../components/TopBar";
import { TrendChart } from "../components/TrendChart";

const TREND_LABEL = {
  improving: "Improving 📈",
  flat_or_declining: "Flat or declining",
  not_enough_data: "Not enough data yet",
};

export function History() {
  const [sessions, setSessions] = useState([]);
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-value">{trend.avg_score !== null ? trend.avg_score.toFixed(1) : "—"}</div>
              <div className="stat-label">Average score</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value" style={{ fontSize: "1.1rem" }}>
                {TREND_LABEL[trend.trend]}
              </div>
              <div className="stat-label">{trend.sessions.length} completed</div>
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
                <div>
                  <span className={`status-badge ${s.status}`}>{s.status.replace("_", " ")}</span>
                  {s.status === "completed" && (
                    <>
                      {" "}
                      <Link to={`/results/${s.session_id}`}>View results</Link>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
