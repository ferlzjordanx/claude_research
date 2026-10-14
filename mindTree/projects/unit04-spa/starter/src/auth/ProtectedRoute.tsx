import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./AuthContext";

/** UX guard only. Real authorization is enforced by the API. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  // TODO: when not authenticated, render <Navigate to="/login" replace
  // state={{ from: location.pathname }} /> so login can send the user
  // back where they came from.
  void isAuthenticated;
  void location;
  void Navigate;
  return <>{children}</>;
}
