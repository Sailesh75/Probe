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
