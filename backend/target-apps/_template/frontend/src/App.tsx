// This is a placeholder. The frontend agent replaces this file with real
// screens generated from the product brief and the backend OpenAPI spec.
//
// Expected shape (see the system prompt for the full rules):
//   - Mount-time auth check via isSessionValid() from ./api, gating
//     login-screen-vs-authenticated-shell — this MUST stay in App.tsx.
//   - Authenticated shell renders <Shell> (src/Shell.tsx, fixed) with
//     navItems + onNavigate={navigate} (from useNavigate()) + onLogout,
//     wrapping a <Routes> tree with one <Route> per screen.
import { useState, useEffect } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";
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
      navItems={[{ label: "Home", to: "/" }]}
      onNavigate={navigate}
      onLogout={() => setIsAuthenticated(false)}
    >
      <Routes>
        <Route path="/" element={<div>Generated screens will render here.</div>} />
      </Routes>
    </Shell>
  );
}
