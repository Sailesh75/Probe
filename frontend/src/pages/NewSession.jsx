import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, isServiceUnavailable, parseResume } from "../api";
import { ServiceNotice } from "../components/ServiceNotice";
import { TopBar } from "../components/TopBar";
import { ArrowIcon, UploadIcon } from "../components/icons";

export function NewSession() {
  const [role, setRole] = useState("");
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [companyStyleText, setCompanyStyleText] = useState("");
  const [error, setError] = useState(null); // the raw Error, so isServiceUnavailable can inspect it
  const [busy, setBusy] = useState(false);
  const [parsingResume, setParsingResume] = useState(false);
  const [parseNotice, setParseNotice] = useState("");
  const navigate = useNavigate();

  async function handleResumeFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    setError(null);
    setParseNotice("");
    setParsingResume(true);
    try {
      const { text } = await parseResume({ file });
      setResumeText(text);
      setParseNotice(
        `Extracted text from ${file.name} — review it before starting.`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setParsingResume(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const data = await createSession({
        role,
        jdText,
        resumeText,
        companyStyleText,
      });
      // Phase 1's API only hands back a question at session-creation time (no GET-question
      // endpoint yet), so it rides along as router state into the Interview page.
      navigate(`/interview/${data.session_id}`, {
        state: {
          questionId: data.question_id,
          questionText: data.question_text,
        },
      });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page page-wide">
      <TopBar links={[{ to: "/history", label: "History" }]} />

      <section className="hero">
        <p className="eyebrow">New interview</p>
        <h1 className="display">
          Practice the questions <em>your resume invites.</em>
        </h1>
        <ol className="steps" aria-label="How it works">
          <li>Find the gaps</li>
          <li>Interview with follow-ups</li>
          <li>Reveal scores at the end</li>
        </ol>
      </section>

      <form className="card session-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="role" className="field-head">
            <span className="step-num">01</span> Role
          </label>
          <input
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Senior Backend Engineer"
            required
          />
        </div>

        <div className="field-grid">
          <div className="field">
            <label htmlFor="jd" className="field-head">
              <span className="step-num">02</span> Job description
            </label>
            <textarea
              id="jd"
              rows={10}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste the job description"
              required
            />
          </div>
          <div className="field">
            <div className="field-head">
              <label htmlFor="resume">
                <span className="step-num">03</span> Resume
              </label>
              <label className={`upload-btn${parsingResume ? " is-busy" : ""}`}>
                <UploadIcon />
                {parsingResume ? "Extracting…" : "Upload PDF/DOCX"}
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleResumeFile}
                  disabled={parsingResume}
                  hidden
                />
              </label>
            </div>
            <textarea
              id="resume"
              rows={10}
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste your resume, or upload a file"
              required
            />
          </div>
        </div>
        {parseNotice && <p className="info">{parseNotice}</p>}

        <details>
          <summary>Company-style mode (optional)</summary>
          <div className="details-body">
            <label htmlFor="company-style">
              Paste real questions from this company (e.g. from Glassdoor)
            </label>
            <textarea
              id="company-style"
              rows={5}
              value={companyStyleText}
              onChange={(e) => setCompanyStyleText(e.target.value)}
              placeholder={
                "One per line, e.g.:\nTell me about a time you disagreed with a decision.\nDesign a system that handles 1M requests/sec."
              }
            />
            <p className="muted small">
              The interviewer will match this company's tone and emphasis — it
              still targets your resume/JD gaps, it just asks about them the way
              this company tends to.
            </p>
          </div>
        </details>

        {error &&
          (isServiceUnavailable(error) ? (
            <ServiceNotice message={error.message} />
          ) : (
            <p className="error">{error.message}</p>
          ))}
        <div className="form-footer">
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Analyzing your profile…" : "Start interview"}
            {!busy && <ArrowIcon />}
          </button>
        </div>
      </form>
    </div>
  );
}
