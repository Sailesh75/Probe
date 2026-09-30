import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true" />
      Probe
    </span>
  );
}

// links: [{ to, label }] — shown before "Sign out".
export function TopBar({ links = [] }) {
  const { signOut } = useAuth();
  return (
    <header className="topbar">
      <Link to="/" className="brand-link">
        <Brand />
      </Link>
      <nav className="nav-links">
        {links.map(({ to, label }) => (
          <Link key={to} to={to}>
            {label}
          </Link>
        ))}
        <button className="link" onClick={signOut}>
          Sign out
        </button>
      </nav>
    </header>
  );
}
