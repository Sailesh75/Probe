import { supabase } from "./supabaseClient";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function authedFetch(path, options = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Like authedFetch, but for multipart file uploads — no Content-Type header (the browser sets
// the multipart boundary itself), and the body is FormData rather than a JSON string.
async function authedUpload(path, file) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Extracts plain text from an uploaded PDF/DOCX resume. Callers should treat the result as a
// starting point to review/edit, not submit silently — parsing can mangle odd layouts.
export function parseResume({ file }) {
  return authedUpload("/resume/parse", file);
}

// Speech-to-text for a recorded answer (Gemini's native audio input, no separate Whisper key).
// Same "review before submit" rule as parseResume — transcription can be wrong.
export function transcribeAudio({ file }) {
  return authedUpload("/voice/transcribe", file);
}

// user_id is never sent here — the backend derives it from the auth token itself.
export function createSession({ role, jdText, resumeText }) {
  return authedFetch("/sessions", {
    method: "POST",
    body: JSON.stringify({ role, jd_text: jdText, resume_text: resumeText }),
  });
}

// Deliberately returns only {recorded, has_next} — the backend never sends back
// score/feedback here, by design (see the plan's "no live grading" contract), and never the
// next question's text either — fetch that separately via getNextQuestion.
export function submitAnswer({ sessionId, questionId, answerText }) {
  return authedFetch(`/sessions/${sessionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
  });
}

// The current pending (unanswered) question for a session — used both to advance to the next
// question after has_next=true, and to resume a session after a page refresh, since the
// pending question now lives in Supabase rather than only in frontend router state.
export function getNextQuestion({ sessionId }) {
  return authedFetch(`/sessions/${sessionId}/next-question`);
}

// The results screen's data. Only available once the interview has actually ended — this is
// the first point anywhere in the app that a score or feedback is ever shown.
export function getSummary({ sessionId }) {
  return authedFetch(`/sessions/${sessionId}/summary`);
}

// Past sessions for the history screen — no score/feedback, just enough to list and link
// into each one's results once completed.
export function listSessions() {
  return authedFetch("/sessions");
}

// Score trend across the user's completed sessions.
export function getTrends() {
  return authedFetch("/stats/trends");
}
