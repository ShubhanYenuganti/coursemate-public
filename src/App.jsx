import { useEffect, useState } from "react";
import "./App.css";

export default function App() {
  const [userData, setUserData] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [csrfToken, setCsrfToken] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showJson, setShowJson] = useState(false);

  // Initialize Google Sign-In
  useEffect(() => {
    const initializeGoogleSignIn = () => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
          callback: handleCredentialResponse,
        });

        const buttonDiv = document.getElementById("googleSignInButton");
        if (buttonDiv && !userData) {
          buttonDiv.innerHTML = '';
          window.google.accounts.id.renderButton(
            buttonDiv,
            {
              theme: "outline",
              size: "large",
              text: "signin_with",
              shape: "rectangular",
              width: 280,
            }
          );
        }
      } else {
        setTimeout(initializeGoogleSignIn, 100);
      }
    };

    if (!userData) {
      initializeGoogleSignIn();
    }
  }, [userData]);

  const handleCredentialResponse = async (response) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/oauth", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          credential: response.credential,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.message || `HTTP ${res.status}`);
      }

      const data = await res.json();

      // Store session tokens in memory (not localStorage — prevents XSS exfiltration)
      if (data.session_token) {
        setSessionToken(data.session_token);
      }
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }

      setUserData(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    // Server-side session revocation
    if (sessionToken) {
      try {
        await fetch("/api/logout", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${sessionToken}`,
          },
        });
      } catch (e) {
        console.error("Logout API error:", e);
      }
    }

    setUserData(null);
    setSessionToken(null);
    setCsrfToken(null);
    setError(null);
    setShowJson(false);
    window.google.accounts.id.disableAutoSelect();
  };

  // Filter sensitive tokens from JSON viewer display
  const getSafeDisplayData = () => {
    if (!userData) return null;
    const { session_token, csrf_token, ...safe } = userData;
    return safe;
  };

  if (userData) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="profile-container">
            <div className="profile-header">
              {userData.user?.picture && (
                <img
                  src={userData.user.picture}
                  alt={userData.user.name}
                  className="profile-avatar"
                />
              )}
              <h1 className="profile-name">{userData.user?.name || "User"}</h1>
              <p className="profile-email">{userData.user?.email}</p>
            </div>

            <div className="profile-info">
              <div className="info-row">
                <span className="info-label">Status</span>
                <span className="badge badge-success">
                  Authenticated
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">Email Verified</span>
                <span className={`badge ${userData.user?.email_verified ? 'badge-success' : 'badge-error'}`}>
                  {userData.user?.email_verified ? 'Verified' : 'Not Verified'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">User ID</span>
                <span className="info-value" style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {userData.user?.id?.substring(0, 20)}...
                </span>
              </div>
              {userData.user?.locale && (
                <div className="info-row">
                  <span className="info-label">Locale</span>
                  <span className="info-value">{userData.user.locale.toUpperCase()}</span>
                </div>
              )}
            </div>

            <button
              className="button button-secondary"
              onClick={() => setShowJson(!showJson)}
            >
              {showJson ? 'Show Profile View' : '{ } Show Raw JSON'}
            </button>

            {showJson && (
              <>
                <div className="section-title">API Response from /api/oauth</div>
                <div className="json-viewer">
                  {JSON.stringify(getSafeDisplayData(), null, 2)}
                </div>
              </>
            )}

            <button
              className="button button-primary"
              onClick={handleSignOut}
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🎓</div>
          <h1 className="auth-title">CourseMate</h1>
          <p className="auth-subtitle">
            Sign in with your Google account to access your personalized learning experience
          </p>
        </div>

        <div className="signin-section">
          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p className="loading-text">Verifying your credentials...</p>
            </div>
          ) : (
            <>
              <div className="google-button-wrapper" id="googleSignInButton"></div>
            </>
          )}

          {error && (
            <div className="error-message">
              <strong>Authentication Failed</strong>
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
