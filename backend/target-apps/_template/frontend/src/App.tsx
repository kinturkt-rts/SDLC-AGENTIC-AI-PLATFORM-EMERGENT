// This is a placeholder. The frontend agent replaces this file with real
// screens generated from the product brief and the backend OpenAPI spec.
//
// Expected shape (see the system prompt for the full rules):
//   - Mount-time auth check via isSessionValid() from ./api, gating
//     login-screen-vs-authenticated-shell — this MUST stay in App.tsx.
//   - Authenticated shell renders <Shell> (src/Shell.tsx, fixed) with
//     navItems (each with a lucide-react icon) + onNavigate={navigate} (from
//     useNavigate()) + onLogout, wrapping a <Routes> tree with one <Route>
//     per screen.
//   - A Dashboard screen is ALWAYS the first navItems entry and ALWAYS owns
//     path "/" — every generated app lands on the Dashboard after login,
//     never on a raw entity list. A trailing catch-all route redirects any
//     unrecognized path back to "/".
import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { LayoutDashboard } from "lucide-react";
import { isSessionValid } from "./api";
import { Shell } from "./Shell";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Preview: show Shell without a backend token (remove for real auth gate).
    setIsAuthenticated(true);
    setLoading(false);
  }, []);

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;
  if (!isAuthenticated) {
    return <div className="p-8 text-muted-foreground">Login screen goes here.</div>;
  }

  return (
    <Shell
      brandName="App"
      navItems={[{ label: "Dashboard", to: "/", icon: <LayoutDashboard className="size-4" /> }]}
      onNavigate={navigate}
      onLogout={() => setIsAuthenticated(false)}
    >
      <Routes>
        <Route path="/" element={<div>Generated Dashboard will render here.</div>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
