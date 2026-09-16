import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createSession, parseResume } from "../api";
import { useAuth } from "../context/AuthContext";

export function NewSession() {
  const [role, setRole] = useState("");
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [companyStyleText, setCompanyStyleText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [parsingResume, setParsingResume] = useState(false);
  const [parseNotice, setParseNotice] = useState("");
  const navigate = useNavigate();
  const { signOut } = useAuth();

  async function handleResumeFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    setError("");
    setParseNotice("");
    setParsingResume(true);
    try {
      const { text } = await parseResume({ file });
      setResumeText(text);
      setParseNotice(`Extracted text from ${file.name} — review it below before starting.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setParsingResume(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await createSession({ role, jdText, resumeText, companyStyleText });
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
            placeholder="Paste your resume here, or upload a file below"
            required
          />
        </label>
        <label>
          Or upload a resume (PDF/DOCX)
          <input type="file" accept=".pdf,.docx" onChange={handleResumeFile} disabled={parsingResume} />
        </label>
        {parsingResume && <p className="muted">Extracting text…</p>}
        {parseNotice && <p className="info">{parseNotice}</p>}

        <details>
          <summary>Company-style mode (optional)</summary>
          <label style={{ marginTop: "0.75rem" }}>
            Paste real questions from this company (e.g. from Glassdoor)
            <textarea
              rows={5}
              value={companyStyleText}
              onChange={(e) => setCompanyStyleText(e.target.value)}
              placeholder={"One per line, e.g.:\nTell me about a time you disagreed with a decision.\nDesign a system that handles 1M requests/sec."}
            />
          </label>
          <p className="muted" style={{ margin: "0.4rem 0 0" }}>
            The interviewer will match this company's tone and emphasis — it still targets your
            resume/JD gaps, it just asks about them the way this company tends to.
          </p>
        </details>

        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Analyzing your profile…" : "Start interview"}
        </button>
      </form>
    </div>
  );
}
