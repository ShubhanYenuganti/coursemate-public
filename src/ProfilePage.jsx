import { useState } from "react";
import { useNavigate } from "react-router-dom";

function BackIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export default function ProfilePage({ userData, sessionToken, csrfToken, onSignOut, onUserUpdate }) {
  const navigate = useNavigate();

  const [usernameInput, setUsernameInput] = useState(userData?.username || userData?.name || "");
  const [usernameStatus, setUsernameStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
  const [usernameError, setUsernameError] = useState("");

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteStatus, setDeleteStatus] = useState(null); // null | 'deleting' | 'error'
  const [deleteError, setDeleteError] = useState("");

  async function handleSaveUsername(e) {
    e.preventDefault();
    const trimmed = usernameInput.trim();
    if (!trimmed) {
      setUsernameError("Username cannot be empty");
      return;
    }
    setUsernameStatus("saving");
    setUsernameError("");
    try {
      const res = await fetch("/api/update_profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ username: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || data.error || `HTTP ${res.status}`);
      }
      onUserUpdate({ ...userData, username: data.user.username });
      setUsernameStatus("saved");
      setTimeout(() => setUsernameStatus(null), 2500);
    } catch (err) {
      setUsernameError(err.message);
      setUsernameStatus("error");
    }
  }

  async function handleDeleteConfirm() {
    setDeleteStatus("deleting");
    setDeleteError("");
    try {
      const res = await fetch("/api/delete_account", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          "X-CSRF-Token": csrfToken,
        },
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || data.error || `HTTP ${res.status}`);
      }
      onSignOut();
    } catch (err) {
      setDeleteError(err.message);
      setDeleteStatus("error");
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Go back"
              aria-label="Go back"
            >
              <BackIcon />
            </button>
            <span className="text-xl font-bold text-gray-900">Profile</span>
          </div>
          <div className="flex items-center gap-3">
            {userData?.picture && (
              <img
                src={userData.picture}
                alt={userData.username || userData.name}
                className="w-8 h-8 rounded-full border-2 border-gray-200"
              />
            )}
            <button
              type="button"
              onClick={onSignOut}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Sign out"
              aria-label="Sign out"
            >
              <SignOutIcon />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex justify-center pt-12 px-4 pb-16">
        <div className="w-full max-w-md space-y-0 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

          {/* Avatar + identity */}
          <div className="flex flex-col items-center pt-8 pb-6 px-8">
            {userData?.picture ? (
              <img
                src={userData.picture}
                alt={userData.username || userData.name}
                className="w-20 h-20 rounded-full border-2 border-gray-200 shadow-sm mb-4"
              />
            ) : (
              <div className="w-20 h-20 rounded-full bg-gradient-to-r from-indigo-400 to-cyan-400 flex items-center justify-center mb-4 shadow-sm">
                <span className="text-2xl font-bold text-white">
                  {(userData?.username || userData?.name || "?")[0].toUpperCase()}
                </span>
              </div>
            )}
            <p className="text-lg font-semibold text-gray-900">{userData?.username || userData?.name}</p>
            <p className="text-sm text-gray-500">{userData?.email}</p>
          </div>

          <div className="border-t border-gray-100" />

          {/* Username section */}
          <div className="px-8 py-6">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Display Name</h2>
            <form onSubmit={handleSaveUsername} className="flex gap-2">
              <input
                type="text"
                value={usernameInput}
                onChange={(e) => { setUsernameInput(e.target.value); setUsernameStatus(null); setUsernameError(""); }}
                maxLength={255}
                placeholder="Your display name"
                className="flex-1 px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"
              />
              <button
                type="submit"
                disabled={usernameStatus === "saving"}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {usernameStatus === "saving" ? "Saving…" : "Save"}
              </button>
            </form>
            {usernameStatus === "saved" && (
              <p className="mt-2 text-sm text-green-600">Username updated.</p>
            )}
            {usernameError && (
              <p className="mt-2 text-sm text-red-600">{usernameError}</p>
            )}
          </div>

          <div className="border-t border-gray-100" />

          {/* Danger zone */}
          <div className="px-8 py-6">
            <h2 className="text-sm font-semibold text-red-600 uppercase tracking-wide mb-1">Danger Zone</h2>
            <p className="text-sm text-gray-500 mb-4">Permanently removes your account and all associated data. This cannot be undone.</p>

            {!deleteConfirm ? (
              <button
                type="button"
                onClick={() => setDeleteConfirm(true)}
                className="px-4 py-2 rounded-lg border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50 transition-colors"
              >
                Remove my account
              </button>
            ) : (
              <div className="space-y-3">
                <p className="text-sm font-medium text-red-700">Are you sure? This cannot be undone.</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => { setDeleteConfirm(false); setDeleteError(""); }}
                    disabled={deleteStatus === "deleting"}
                    className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleDeleteConfirm}
                    disabled={deleteStatus === "deleting"}
                    className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    {deleteStatus === "deleting" ? "Deleting…" : "Yes, delete my account"}
                  </button>
                </div>
                {deleteError && (
                  <p className="text-sm text-red-600">{deleteError}</p>
                )}
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}
