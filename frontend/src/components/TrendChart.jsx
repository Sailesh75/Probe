import { useId, useState } from "react";

// Single-series line chart: overall_score per completed session, oldest to newest.
// One series -> no legend needed (the section title above it already names it).
const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 32 };
const Y_MIN = 1;
const Y_MAX = 5;

function xFor(i, count) {
  const innerWidth = WIDTH - PAD.left - PAD.right;
  if (count <= 1) return PAD.left + innerWidth / 2;
  return PAD.left + (innerWidth * i) / (count - 1);
}

function yFor(score) {
  const innerHeight = HEIGHT - PAD.top - PAD.bottom;
  const clamped = Math.min(Y_MAX, Math.max(Y_MIN, score));
  return PAD.top + innerHeight * (1 - (clamped - Y_MIN) / (Y_MAX - Y_MIN));
}

export function TrendChart({ sessions }) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const gradientId = useId();

  if (sessions.length === 0) {
    return <p className="muted">No completed interviews yet — finish one to start a trend.</p>;
  }

  const points = sessions.map((s, i) => ({
    x: xFor(i, sessions.length),
    y: yFor(s.overall_score),
    session: s,
  }));

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const gridScores = [1, 2, 3, 4, 5];
  const hovered = hoverIndex !== null ? points[hoverIndex] : null;

  return (
    <div className="trend-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Overall score by session over time"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-line)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--chart-line)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridScores.map((score) => (
          <g key={score}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={yFor(score)}
              y2={yFor(score)}
              className="trend-gridline"
            />
            <text x={PAD.left - 8} y={yFor(score)} className="trend-axis-label" textAnchor="end" dy="0.32em">
              {score}
            </text>
          </g>
        ))}

        {points.length > 1 && (
          <path
            d={`${linePath} L ${points[points.length - 1].x} ${yFor(Y_MIN)} L ${points[0].x} ${yFor(Y_MIN)} Z`}
            fill={`url(#${gradientId})`}
            stroke="none"
          />
        )}
        {points.length > 1 && (
          <path d={linePath} fill="none" stroke="var(--chart-line)" strokeWidth="2" strokeLinecap="round" />
        )}

        {points.map((p, i) => (
          <g key={p.session.session_id}>
            {/* Larger invisible hit target than the visible marker, per interaction guidance. */}
            <circle
              cx={p.x}
              cy={p.y}
              r={12}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(i)}
              onMouseLeave={() => setHoverIndex(null)}
            />
            <circle
              cx={p.x}
              cy={p.y}
              r={hoverIndex === i ? 6 : 4}
              fill="var(--chart-line)"
              stroke="var(--card-bg)"
              strokeWidth="2"
            />
          </g>
        ))}
      </svg>

      {hovered && (
        <div className="trend-tooltip">
          <strong>{hovered.session.role}</strong>
          <span>{new Date(hovered.session.created_at).toLocaleDateString()}</span>
          <span>Score: {hovered.session.overall_score.toFixed(1)} / 5</span>
        </div>
      )}
    </div>
  );
}
