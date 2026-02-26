import { useState } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import SignInPage from "./SignInPage.jsx";
import Dashboard from "./Dashboard.jsx";
import CoursePage from "./CoursePage.jsx";
import "./App.css";

function CourseRoute({ userData, onSignOut }) {
  const { state } = useLocation();
  return <CoursePage course={state?.course} userData={userData} onSignOut={onSignOut} />;
}

export default function App() {
  const [userData, setUserData] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [, setCsrfToken] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleCredentialResponse = async (response) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/oauth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.message || `HTTP ${res.status}`);
      }

      const data = await res.json();

      if (data.session_token) setSessionToken(data.session_token);
      if (data.csrf_token) setCsrfToken(data.csrf_token);
      setUserData(data);
      navigate("/dashboard");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    if (sessionToken) {
      try {
        await fetch("/api/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${sessionToken}` },
        });
      } catch (e) {
        console.error("Logout API error:", e);
      }
    }

    setUserData(null);
    setSessionToken(null);
    setCsrfToken(null);
    setError(null);
    window.google?.accounts?.id?.disableAutoSelect();
    navigate("/");
  };

  return (
    <Routes>
      <Route
        path="/"
        element={
          userData ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <SignInPage
              loading={loading}
              error={error}
              onGoogleSignIn={handleCredentialResponse}
            />
          )
        }
      />
      <Route
        path="/dashboard"
        element={
          userData ? (
            <Dashboard userData={userData} sessionToken={sessionToken} onSignOut={handleSignOut} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id"
        element={
          userData ? (
            <CourseRoute userData={userData} onSignOut={handleSignOut} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
