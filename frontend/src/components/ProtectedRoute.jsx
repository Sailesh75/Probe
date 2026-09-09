import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children }) {
  const { session, loading } = useAuth();

  if (loading) return <div className="page-center">Loading…</div>;
  if (!session) return <Navigate to="/login" replace />;
  return children;
}
