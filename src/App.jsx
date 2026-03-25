import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation, useParams } from "react-router-dom";
import SignInPage from "./SignInPage.jsx";
import Dashboard from "./Dashboard.jsx";
import CoursePage from "./CoursePage.jsx";
import ProfilePage from "./ProfilePage.jsx";
import QuizViewerRoute from "./QuizViewerRoute.jsx";
import "./App.css";

function CourseRoute({ userData, sessionToken, csrfToken, onSignOut, onUserUpdate }) {
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
    if (!sessionToken) return;
    if (state?.course) {
      setCourse(state.course);
      setLoadingCourse(false);
      return;
    }
    if (!id) return;

    let cancelled = false;
    setLoadingCourse(true);
    fetch("/api/course", {
      headers: { Authorization: `Bearer ${sessionToken}` },
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
  }, [id, sessionToken, state, navigate]);

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
      sessionToken={sessionToken}
      csrfToken={csrfToken}
      onSignOut={onSignOut}
      onUserUpdate={onUserUpdate}
      onCourseUpdate={handleCourseUpdate}
    />
  );
}

export default function App() {
  const [userData, setUserData] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [csrfToken, setCsrfToken] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const stored = localStorage.getItem("cm_session");
    if (!stored) {
      setRestoring(false);
      return;
    }
    fetch("/api/validate_session", {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("invalid");
        return res.json();
      })
      .then((data) => {
        if (data.session_token) setSessionToken(data.session_token);
        if (data.csrf_token) setCsrfToken(data.csrf_token);
        setUserData(data.user);
      })
      .catch(() => {
        localStorage.removeItem("cm_session");
      })
      .finally(() => {
        setRestoring(false);
      });
  }, []);

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

      if (data.session_token) {
        setSessionToken(data.session_token);
        localStorage.setItem("cm_session", data.session_token);
      }
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

    localStorage.removeItem("cm_session");
    setUserData(null);
    setSessionToken(null);
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
            <Dashboard userData={userData} sessionToken={sessionToken} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id/quiz/:generationId"
        element={
          userData ? (
            <QuizViewerRoute sessionToken={sessionToken} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/course/:id"
        element={
          userData ? (
            <CourseRoute userData={userData} sessionToken={sessionToken} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/profile"
        element={
          userData ? (
            <ProfilePage userData={userData} sessionToken={sessionToken} csrfToken={csrfToken} onSignOut={handleSignOut} onUserUpdate={setUserData} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
