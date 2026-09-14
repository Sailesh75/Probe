import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createSession } from "../api";
import { useAuth } from "../context/AuthContext";

export function NewSession() {
  const [role, setRole] = useState("");
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const { signOut } = useAuth();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await createSession({ role, jdText, resumeText });
      // Phase 1's API only hands back a question at session-creation time (no GET-question
      // endpoint yet), so it rides along as router state into the Interview page.
      navigate(`/interview/${data.session_id}`, {
        state: { questionId: data.question_id, questionText: data.question_text },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <h2>New interview</h2>
        <div className="nav-links">
          <Link to="/history">History</Link>
          <button className="link" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>
      <form className="card" onSubmit={handleSubmit}>
        <label>
          Role
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Senior Backend Engineer"
            required
          />
        </label>
        <label>
          Job description
          <textarea
            rows={8}
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here"
            required
          />
        </label>
        <label>
          Resume
          <textarea
            rows={8}
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder="Paste your resume here"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Analyzing your profile…" : "Start interview"}
        </button>
      </form>
    </div>
  );
}
