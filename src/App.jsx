import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation, useParams } from "react-router-dom";
import SignInPage from "./SignInPage.jsx";
import Dashboard from "./Dashboard.jsx";
import CoursePage from "./CoursePage.jsx";
import ProfilePage from "./ProfilePage.jsx";
import QuizViewerRoute from "./QuizViewerRoute.jsx";
import FlashcardViewerRoute from "./FlashcardViewerRoute.jsx";
import ReportViewerRoute from "./ReportViewerRoute.jsx";
import "./App.css";

function CourseRoute({ userData, csrfToken, onSignOut, onUserUpdate }) {
  const { state } = useLocation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [course, setCourse] = useState(state?.course || null);
  const [loadingCourse, setLoadingCourse] = useState(!state?.course);

  function handleCourseUpdate(updated) {
    setCourse(updated);
    navigate(".", { replace: true, state: { ...state, course: updated } });
  }

  useEffect(() => {
    if (!userData) return;
    if (state?.course) {
      setCourse(state.course);
      setLoadingCourse(false);
      return;
    }
    if (!id) return;

    let cancelled = false;
    setLoadingCourse(true);
    fetch("/api/course", {
      credentials: 'include',
    })
      .then((res) => res.json().catch(() => ({})))
      .then((data) => {
        const found = (data.courses || []).find((c) => String(c.id) === String(id));
        if (!found) throw new Error("Course not found");
        if (!cancelled) setCourse(found);
      })
      .catch(() => {
        if (!cancelled) navigate("/dashboard", { replace: true });
      })
      .finally(() => {
        if (!cancelled) setLoadingCourse(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, userData, state, navigate]);

  if (loadingCourse || !course) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <CoursePage
      course={course}
      userData={userData}
      csrfToken={csrfToken}
      onSignOut={onSignOut}
      onUserUpdate={onUserUpdate}
      onCourseUpdate={handleCourseUpdate}
    />
  );
}

export default function App() {
  const [userData, setUserData] = useState(null);
  const [csrfToken, setCsrfToken] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Legacy cleanup: older builds may have stored session tokens in Web Storage.
    // Current auth uses HttpOnly cookies, so this prevents stale values from sticking around in DevTools.
    try {
      localStorage.removeItem("cm_session");
      sessionStorage.removeItem("cm_session");
    } catch {}

    fetch("/api/auth", { credentials: 'include' })
      .then((res) => {
        if (!res.ok) throw new Error("invalid");
        return res.json();
      })
      .then((data) => {
        if (data.csrf_token) setCsrfToken(data.csrf_token);
        setUserData(data.user);
      })
      .catch(() => {
        // Cookie is invalid or absent — nothing to clean up
      })
      .finally(() => {
        setRestoring(false);
      });
  }, []);

  const handleCredentialResponse = async (response) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: 'include',
        body: JSON.stringify({ credential: response.credential }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.message || `HTTP ${res.status}`);
      }

      const data = await res.json();

      if (data.csrf_token) setCsrfToken(data.csrf_token);
      setUserData(data.user ?? data);
      navigate("/dashboard");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await fetch("/api/auth", {
        method: "DELETE",
        credentials: 'include',
      });
    } catch (e) {
      console.error("Logout API error:", e);
    }

    // Legacy cleanup for older token storage.
    try {
      localStorage.removeItem("cm_session");
      sessionStorage.removeItem("cm_session");
    } catch {}

    setUserData(null);
    setCsrfToken(null);
    setError(null);
    window.google?.accounts?.id?.disableAutoSelect();
    navigate("/");
  };

  if (restoring) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <div style={{ width: 40, height: 40, border: "4px solid #ccc", borderTopColor: "#6c63ff", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

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
            <Dashboard userData={userData} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id/quiz/:generationId"
        element={
          userData ? (
            <QuizViewerRoute />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id/flashcards/:generationId"
        element={
          userData ? (
            <FlashcardViewerRoute />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id/reports/:generationId"
        element={
          userData ? (
            <ReportViewerRoute />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id"
        element={
          userData ? (
            <CourseRoute userData={userData} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/profile"
        element={
          userData ? (
            <ProfilePage userData={userData} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
