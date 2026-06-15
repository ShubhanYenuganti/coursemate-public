import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";

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

function PencilIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

const PROVIDER_LABELS = { gemini: "Gemini", openai: "OpenAI", claude: "Claude" };
const ALL_PROVIDERS = ["gemini", "openai", "claude"];

function ApiKeysSection() {
  const [keys, setKeys] = useState({ gemini: false, openai: false, claude: false });
  const [loading, setLoading] = useState(true);

  // Add key flow
  const [adding, setAdding] = useState(false);
  const [addProvider, setAddProvider] = useState("");
  const [addValue, setAddValue] = useState("");
  const [addStatus, setAddStatus] = useState(null); // null | 'saving' | 'error'
  const [addError, setAddError] = useState("");

  // Edit key flow
  const [editingProvider, setEditingProvider] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [editStatus, setEditStatus] = useState(null);
  const [editError, setEditError] = useState("");

  // Delete key
  const [deletingProvider, setDeletingProvider] = useState(null);

  async function fetchKeys() {
    try {
      const res = await fetch("/api/user?resource=api_keys", {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setKeys(data);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchKeys(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const savedProviders = ALL_PROVIDERS.filter((p) => keys[p]);
  const availableProviders = ALL_PROVIDERS.filter((p) => !keys[p]);
  const keyCount = savedProviders.length;

  function startAdding() {
    setAdding(true);
    setAddProvider(availableProviders[0] || "");
    setAddValue("");
    setAddStatus(null);
    setAddError("");
  }

  function cancelAdding() {
    setAdding(false);
    setAddProvider("");
    setAddValue("");
    setAddStatus(null);
    setAddError("");
  }

  async function handleSaveNew() {
    if (!addProvider) { setAddError("Select a provider."); return; }
    if (!addValue.trim()) { setAddError("API key cannot be empty."); return; }
    setAddStatus("saving");
    setAddError("");
    try {
      const res = await fetch("/api/user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ resource: "api_keys", provider: addProvider, api_key: addValue.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setKeys((prev) => ({ ...prev, [addProvider]: true }));
      cancelAdding();
    } catch (err) {
      setAddError(err.message);
      setAddStatus("error");
    }
  }

  function startEditing(provider) {
    setEditingProvider(provider);
    setEditValue("");
    setEditStatus(null);
    setEditError("");
  }

  function cancelEditing() {
    setEditingProvider(null);
    setEditValue("");
    setEditStatus(null);
    setEditError("");
  }

  async function handleSaveEdit() {
    if (!editValue.trim()) { setEditError("API key cannot be empty."); return; }
    setEditStatus("saving");
    setEditError("");
    try {
      const res = await fetch("/api/user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ resource: "api_keys", provider: editingProvider, api_key: editValue.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      cancelEditing();
    } catch (err) {
      setEditError(err.message);
      setEditStatus("error");
    }
  }

  async function handleDelete(provider) {
    setDeletingProvider(provider);
    try {
      const res = await fetch("/api/user?resource=api_keys", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ provider }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setKeys((prev) => ({ ...prev, [provider]: false }));
      if (editingProvider === provider) cancelEditing();
    } finally {
      setDeletingProvider(null);
    }
  }

  return (
    <Card className="rounded-none border-0 border-t border-border shadow-none">
      <CardHeader className="px-8 pt-6 pb-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm font-semibold text-foreground uppercase tracking-wide">API Keys</CardTitle>
            {!loading && (
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-muted text-muted-foreground text-xs font-semibold">
                {keyCount}
              </span>
            )}
          </div>
          {!adding && availableProviders.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={startAdding}
            >
              <span className="text-base leading-none">+</span> Add Key
            </Button>
          )}
        </div>
        <CardDescription className="text-xs text-muted-foreground">
          Your keys are encrypted at rest and never exposed in responses.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-8 pb-6">
        {/* Add key form */}
        {adding && (
          <div className="mb-4 rounded-xl border border-border bg-accent/50 p-4 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Select provider</p>
            <div className="flex gap-2 flex-wrap">
              {availableProviders.map((p) => (
                <Button
                  key={p}
                  type="button"
                  variant={addProvider === p ? "default" : "outline"}
                  size="sm"
                  onClick={() => setAddProvider(p)}
                >
                  {PROVIDER_LABELS[p]}
                </Button>
              ))}
            </div>
            <Input
              type="text"
              value={addValue}
              onChange={(e) => { setAddValue(e.target.value); setAddError(""); }}
              placeholder={`Paste your ${addProvider ? PROVIDER_LABELS[addProvider] : "API"} key…`}
              className="font-mono"
            />
            {addError && <p className="text-xs text-destructive">{addError}</p>}
            <div className="flex gap-2">
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={handleSaveNew}
                disabled={addStatus === "saving"}
              >
                {addStatus === "saving" ? "Saving…" : "Save"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={cancelAdding}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Key list */}
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : savedProviders.length === 0 ? (
          <p className="text-sm text-muted-foreground">No API keys saved yet.</p>
        ) : (
          <div className="divide-y divide-border border border-border rounded-xl overflow-hidden">
            {savedProviders.map((provider) => (
              <div key={provider} className="bg-background">
                {/* Normal row */}
                {editingProvider !== provider ? (
                  <div className="flex items-center gap-3 px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-foreground">{PROVIDER_LABELS[provider]}</p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">••••••••••••••••••••</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => startEditing(provider)}
                        title="Edit key"
                        className="text-muted-foreground hover:text-primary hover:bg-accent"
                      >
                        <PencilIcon />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(provider)}
                        disabled={deletingProvider === provider}
                        title="Delete key"
                        className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 disabled:opacity-40"
                      >
                        <TrashIcon />
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* Edit row */
                  <div className="px-4 py-3 space-y-2 bg-accent/40">
                    <p className="text-xs font-semibold text-muted-foreground">{PROVIDER_LABELS[provider]} — new key</p>
                    <Input
                      type="text"
                      autoFocus
                      value={editValue}
                      onChange={(e) => { setEditValue(e.target.value); setEditError(""); }}
                      placeholder="Paste replacement key…"
                      className="font-mono"
                    />
                    {editError && <p className="text-xs text-destructive">{editError}</p>}
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="default"
                        size="sm"
                        onClick={handleSaveEdit}
                        disabled={editStatus === "saving"}
                      >
                        {editStatus === "saving" ? "Saving…" : "Update"}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={cancelEditing}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NotionConnectionSection({ pending = false }) {
  const [status, setStatus] = useState(null); // null = loading, { connected, workspace_name, workspace_icon } = loaded
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    const endpoint = pending ? "finalize_connection" : "status";
    fetch(`/api/notion?action=${endpoint}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (data.connected) {
          localStorage.setItem("coursemate_notion_connected", "1");
        } else {
          localStorage.removeItem("coursemate_notion_connected");
        }
        setStatus(data);
      })
      .catch(() => setStatus({ connected: false }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDisconnect() {
    setRevoking(true);
    try {
      await fetch("/api/notion?action=revoke", { method: "DELETE", credentials: "include" });
      localStorage.removeItem("coursemate_notion_connected");
      setStatus({ connected: false });
    } finally {
      setRevoking(false);
    }
  }

  function handleConnect() {
    window.location.href = "/api/notion?action=auth";
  }

  if (status === null) {
    return (
      <Card className="rounded-none border-0 border-t border-border shadow-none">
        <CardHeader className="px-8 pt-6 pb-1">
          <CardTitle className="text-sm font-semibold text-foreground uppercase tracking-wide">Connected Apps</CardTitle>
        </CardHeader>
        <CardContent className="px-8 pb-6">
          <p className="text-sm text-muted-foreground">Loading…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-none border-0 border-t border-border shadow-none">
      <CardHeader className="px-8 pt-6 pb-1">
        <CardTitle className="text-sm font-semibold text-foreground uppercase tracking-wide">Connected Apps</CardTitle>
        <CardDescription className="text-xs text-muted-foreground">Connect third-party apps to import and export course content.</CardDescription>
      </CardHeader>
      <CardContent className="px-8 pb-6">
        <div className="border border-border rounded-xl overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-background">
            {/* Notion logo */}
            <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center shrink-0">
              <svg width="16" height="16" viewBox="0 0 100 100" fill="white" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 7.6C9.7 10.6 11 10.4 18.2 9.9L88.2 5.6C89.6 5.6 88.5 4.2 87.9 4L77.1 0.4C74.8 -0.3 72.1 0.1 69.7 0.4L2.4 5.7C0.3 6 0 7.3 1.1 8.2L6 7.6ZM8.5 18.1V91.6C8.5 95.4 10.5 96.7 14.9 96.4L91.5 92C95.9 91.7 96.4 89.3 96.4 86.3V13.1C96.4 10 95 8.4 92 8.7L12.1 13C9 13.3 8.5 14.9 8.5 18.1ZM84.5 21.4C85 23.9 84.5 26.4 82 26.7L77.5 27.4V87.5L82 87.2C84.5 87 85 84.5 85 82V21.4ZM22.3 29.3C22.3 26.8 20.7 25.9 18.5 26.1L14.5 26.4V86.2C14.5 88.7 16.5 90.1 18.8 89.9L22.3 89.6V29.3ZM67 22.7L35.5 24.4C33.5 24.5 33 25.5 33 27.2V88.1C33 89.8 33.8 90.8 35.5 90.7L67.5 88.9C69.3 88.8 70 87.8 70 86.1V25.2C70 23.5 69 22.6 67 22.7Z" />
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground">Notion</p>
              {status.connected ? (
                <p className="text-xs text-muted-foreground truncate">
                  {status.workspace_icon && (
                    <span className="mr-1">{status.workspace_icon}</span>
                  )}
                  {status.workspace_name || "Connected"}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Not connected</p>
              )}
            </div>

            {status.connected ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                disabled={revoking}
                className="shrink-0 disabled:opacity-40"
              >
                {revoking ? "Disconnecting…" : "Disconnect"}
              </Button>
            ) : (
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={handleConnect}
                className="shrink-0"
              >
                Connect
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function GDriveConnectionSection({ pending = false }) {
  const [status, setStatus] = useState(null); // null = loading, { connected, email } = loaded
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    const endpoint = pending ? "finalize_connection" : "status";
    fetch(`/api/gdrive?action=${endpoint}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (data.connected) {
          localStorage.setItem("coursemate_gdrive_connected", "1");
        } else {
          localStorage.removeItem("coursemate_gdrive_connected");
        }
        setStatus(data);
      })
      .catch(() => setStatus({ connected: false }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDisconnect() {
    if (!window.confirm("Disconnect Google Drive? This will remove your stored access token.")) return;
    setRevoking(true);
    try {
      await fetch("/api/gdrive?action=revoke", { method: "DELETE", credentials: "include" });
      localStorage.removeItem("coursemate_gdrive_connected");
      setStatus({ connected: false });
    } finally {
      setRevoking(false);
    }
  }

  function handleConnect() {
    window.location.href = "/api/gdrive?action=auth";
  }

  if (status === null) {
    return (
      <div className="px-8 pb-6">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="px-8 pb-6">
      <div className="border border-border rounded-xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 bg-background">
          {/* Google Drive logo */}
          <div className="w-8 h-8 rounded-lg bg-background border border-border flex items-center justify-center shrink-0">
            <svg width="18" height="16" viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg">
              <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
              <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>
              <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/>
              <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
              <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
              <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
            </svg>
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground">Google Drive</p>
            {status.connected ? (
              <p className="text-xs text-muted-foreground truncate">{status.email || "Connected"}</p>
            ) : (
              <p className="text-xs text-muted-foreground">Not connected</p>
            )}
          </div>

          {status.connected ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleDisconnect}
              disabled={revoking}
              className="shrink-0 disabled:opacity-40"
            >
              {revoking ? "Disconnecting…" : "Disconnect"}
            </Button>
          ) : (
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleConnect}
              className="shrink-0"
            >
              Connect
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage({ userData, csrfToken, onSignOut, onUserUpdate }) {
  const navigate = useNavigate();
  const location = useLocation();

  const notionPending = new URLSearchParams(location.search).get("notion_pending") === "1";
  const gdrivePending = new URLSearchParams(location.search).get("gdrive_pending") === "1";

  const [notionToast, setNotionToast] = useState(() => {
    const params = new URLSearchParams(location.search);
    return params.get("notion_connected") === "1" || params.get("notion_pending") === "1";
  });

  useEffect(() => {
    if (notionToast) {
      const t = setTimeout(() => setNotionToast(false), 4000);
      return () => clearTimeout(t);
    }
  }, [notionToast]);

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
      const res = await fetch("/api/user", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        credentials: "include",
        body: JSON.stringify({ resource: "profile", username: trimmed }),
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
      const res = await fetch("/api/user?resource=profile", {
        method: "DELETE",
        headers: {
          "X-CSRF-Token": csrfToken,
        },
        credentials: "include",
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
    <div className="min-h-screen bg-background">
      {/* Notion connected toast — decorative overlay, structure kept, retinted */}
      {notionToast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-3 rounded-xl bg-foreground text-background text-sm shadow-lg">
          <span>Notion connected successfully.</span>
          <Button type="button" variant="ghost" size="icon" onClick={() => setNotionToast(false)} className="ml-2 text-background/60 hover:text-background hover:bg-transparent h-auto w-auto p-0">✕</Button>
        </div>
      )}

      {/* Header */}
      <header className="bg-background/80 backdrop-blur-sm border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => navigate('/dashboard')}
              title="Go back"
              aria-label="Go back"
            >
              <BackIcon />
            </Button>
            <span className="text-xl font-bold text-foreground">Profile</span>
          </div>
          <div className="flex items-center gap-3">
            {userData?.picture && (
              <img
                src={userData.picture}
                alt={userData.username || userData.name}
                className="w-8 h-8 rounded-full border-2 border-border"
              />
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onSignOut}
              title="Sign out"
              aria-label="Sign out"
            >
              <SignOutIcon />
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex justify-center pt-12 px-4 pb-16">
        <div className="w-full max-w-md space-y-0 bg-background/80 backdrop-blur-sm border border-border rounded-2xl shadow-sm overflow-hidden">

          {/* Avatar + identity */}
          <div className="flex flex-col items-center pt-8 pb-6 px-8">
            {userData?.picture ? (
              <img
                src={userData.picture}
                alt={userData.username || userData.name}
                className="w-20 h-20 rounded-full border-2 border-border shadow-sm mb-4"
              />
            ) : (
              /* Brand avatar gradient — intentional brand asset, kept */
              <div className="w-20 h-20 rounded-full bg-gradient-to-r from-indigo-400 to-cyan-400 flex items-center justify-center mb-4 shadow-sm">
                <span className="text-2xl font-bold text-white">
                  {(userData?.username || userData?.name || "?")[0].toUpperCase()}
                </span>
              </div>
            )}
            <p className="text-lg font-semibold text-foreground">{userData?.username || userData?.name}</p>
            <p className="text-sm text-muted-foreground">{userData?.email}</p>
          </div>

          <div className="border-t border-border" />

          {/* Username section */}
          <Card className="rounded-none border-0 shadow-none">
            <CardHeader className="px-8 pt-6 pb-2">
              <CardTitle className="text-sm font-semibold text-foreground uppercase tracking-wide">Display Name</CardTitle>
            </CardHeader>
            <CardContent className="px-8 pb-6">
              <form onSubmit={handleSaveUsername} className="flex gap-2">
                <Label htmlFor="username-input" className="sr-only">Display name</Label>
                <Input
                  id="username-input"
                  type="text"
                  value={usernameInput}
                  onChange={(e) => { setUsernameInput(e.target.value); setUsernameStatus(null); setUsernameError(""); }}
                  maxLength={255}
                  placeholder="Your display name"
                  className="flex-1"
                />
                <Button
                  type="submit"
                  variant="default"
                  disabled={usernameStatus === "saving"}
                >
                  {usernameStatus === "saving" ? "Saving…" : "Save"}
                </Button>
              </form>
              {usernameStatus === "saved" && (
                <p className="mt-2 text-sm text-green-600">Username updated.</p>
              )}
              {usernameError && (
                <p className="mt-2 text-sm text-destructive">{usernameError}</p>
              )}
            </CardContent>
          </Card>

          {/* API Keys section */}
          <ApiKeysSection />

          {/* Connected apps section */}
          <NotionConnectionSection pending={notionPending} />
          <GDriveConnectionSection pending={gdrivePending} />

          {/* Danger zone */}
          <Card className="rounded-none border-0 border-t border-border shadow-none">
            <CardHeader className="px-8 pt-6 pb-1">
              <CardTitle className="text-sm font-semibold text-destructive uppercase tracking-wide">Danger Zone</CardTitle>
              <CardDescription className="text-sm text-muted-foreground">Permanently removes your account and all associated data. This cannot be undone.</CardDescription>
            </CardHeader>
            <CardContent className="px-8 pb-6">
              {!deleteConfirm ? (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => setDeleteConfirm(true)}
                  className="border border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10"
                >
                  Remove my account
                </Button>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-destructive">Are you sure? This cannot be undone.</p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => { setDeleteConfirm(false); setDeleteError(""); }}
                      disabled={deleteStatus === "deleting"}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={handleDeleteConfirm}
                      disabled={deleteStatus === "deleting"}
                    >
                      {deleteStatus === "deleting" ? "Deleting…" : "Yes, delete my account"}
                    </Button>
                  </div>
                  {deleteError && (
                    <p className="text-sm text-destructive">{deleteError}</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

        </div>
      </main>
    </div>
  );
}
