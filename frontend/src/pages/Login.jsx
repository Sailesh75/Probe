import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../supabaseClient";
import { Brand } from "../components/TopBar";
import { GitHubIcon, GoogleIcon } from "../components/icons";

export function Login() {
  const [mode, setMode] = useState("sign-in"); // "sign-in" | "sign-up"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      if (mode === "sign-in") {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (signInError) throw signInError;
        navigate("/");
      } else {
        const { error: signUpError } = await supabase.auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        setInfo("Account created. Check your email to confirm it, then sign in.");
        setMode("sign-in");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleOAuth(provider) {
    setError("");
    setInfo("");
    setBusy(true);
    // Redirects away to the provider; on success Supabase sends the browser back to the site
    // root with the session in the URL, which supabase-js picks up on load.
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: window.location.origin },
    });
    if (oauthError) {
      setError(oauthError.message);
      setBusy(false);
    }
  }

  const isSignIn = mode === "sign-in";

  return (
    <div className="auth-layout">
      <section className="auth-showcase" aria-hidden="true">
        <Brand />
        <div>
          <h1 className="display">
            Interviews that <em>dig deeper.</em>
          </h1>
          <p className="muted showcase-sub">
            Paste a job description and your resume. Probe finds the gaps between them and
            interviews you on exactly those — following up when an answer falls short.
          </p>
        </div>
        <div className="transcript">
          <div className="t-line t-q">
            <span className="t-tag">Interviewer</span>
            How would you scale the ingestion pipeline to 10× traffic?
          </div>
          <div className="t-line t-a">
            <span className="t-tag">You</span>
            We'd add more workers and a queue in front…
          </div>
          <div className="t-line t-q t-follow">
            <span className="t-tag">
              Follow-up <span className="t-probe">probing: Kafka</span>
            </span>
            What happens to message ordering when you add partitions?
          </div>
        </div>
        <p className="showcase-foot">Scores stay hidden until the interview ends.</p>
      </section>

      <section className="auth-panel">
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-mobile-brand">
            <Brand />
          </div>
          <div>
            <h2>{isSignIn ? "Welcome back" : "Create your account"}</h2>
            <p className="muted">
              {isSignIn ? "Sign in to start a mock interview." : "It takes less than a minute."}
            </p>
          </div>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              autoComplete={isSignIn ? "current-password" : "new-password"}
              required
              minLength={6}
            />
          </label>
          {error && <p className="error">{error}</p>}
          {info && <p className="info">{info}</p>}
          <div className="auth-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={() => handleOAuth("google")}
              disabled={busy}
              aria-label="Continue with Google"
              title="Continue with Google"
            >
              <GoogleIcon />
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={() => handleOAuth("github")}
              disabled={busy}
              aria-label="Continue with GitHub"
              title="Continue with GitHub"
            >
              <GitHubIcon />
            </button>
            <button type="submit" className="primary grow" disabled={busy}>
              {busy ? "Please wait…" : isSignIn ? "Sign in" : "Sign up"}
            </button>
          </div>
          <p className="auth-switch muted">
            {isSignIn ? "New here?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="link"
              onClick={() => setMode(isSignIn ? "sign-up" : "sign-in")}
            >
              {isSignIn ? "Create an account" : "Sign in"}
            </button>
          </p>
        </form>
      </section>
    </div>
  );
}
