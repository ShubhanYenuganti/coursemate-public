import { useState, useEffect } from "react";

const AVATAR_COLORS = [
  "bg-indigo-400", "bg-cyan-500", "bg-violet-400",
  "bg-teal-500", "bg-sky-500", "bg-rose-400",
];

function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function initials(name) {
  return name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function Avatar({ name, picture }) {
  if (picture) {
    return (
      <img
        src={picture}
        alt={name}
        className="w-9 h-9 rounded-full border border-gray-200 flex-shrink-0 object-cover"
      />
    );
  }
  return (
    <div className={`w-9 h-9 rounded-full ${avatarColor(name)} flex items-center justify-center flex-shrink-0`}>
      <span className="text-xs font-bold text-white tracking-wide">{initials(name)}</span>
    </div>
  );
}

function MemberRow({ member, isOwner, onRemove, removing }) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
      <Avatar name={member.name} picture={member.picture} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">{member.name}</p>
        <p className="text-xs text-gray-400 truncate">{member.email}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border bg-indigo-50 text-indigo-700 border-indigo-200">
          Collaborator
        </span>
        {isOwner && (
          <button
            type="button"
            disabled={removing}
            onClick={() => onRemove(member.id)}
            className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors disabled:opacity-40"
            aria-label="Remove collaborator"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export default function SharingAccessModal({ courseId, csrfToken, isOwner }) {
  const [members, setMembers] = useState([]);
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [removingId, setRemovingId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!courseId) return;
    setLoadingMembers(true);
    fetch(`/api/sharing?course_id=${courseId}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setMembers(data.members || []))
      .catch(() => {})
      .finally(() => setLoadingMembers(false));
  }, [courseId]);

  async function handleInvite(e) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setInviting(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch("/api/sharing", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
        body: JSON.stringify({ course_id: courseId, email: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
      setMembers(data.members || []);
      setEmail("");
      setSuccess(`${trimmed} added as a collaborator.`);
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setInviting(false);
    }
  }

  async function handleRemove(userId) {
    setRemovingId(userId);
    setError("");
    try {
      const res = await fetch("/api/sharing", {
        method: "DELETE",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
        body: JSON.stringify({ course_id: courseId, user_id: userId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
      setMembers(data.members || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 space-y-5">
      {/* Header */}
      <div>
        <p className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-1">Sharing</p>
        <p className="text-xs text-gray-500">
          {isOwner
            ? "Invite collaborators by email. They'll see this course on their dashboard and can access public materials, chat, and generate."
            : "People with access to this course."}
        </p>
      </div>

      {/* Invite row — owner only */}
      {isOwner && (
        <form onSubmit={handleInvite} className="flex gap-2 flex-wrap sm:flex-nowrap">
          <input
            type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setError(""); }}
            placeholder="Invite by email address…"
            className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm text-gray-900 placeholder-gray-400"
          />
          <button
            type="submit"
            disabled={inviting || !email.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors flex-shrink-0 disabled:opacity-50"
          >
            {inviting ? "Adding…" : "Invite"}
          </button>
        </form>
      )}

      {/* Feedback */}
      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
      )}
      {success && (
        <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">{success}</p>
      )}

      {/* Members list */}
      <div>
        <p className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-3">
          {members.length} {members.length === 1 ? "Collaborator" : "Collaborators"}
        </p>
        {loadingMembers ? (
          <div className="flex justify-center py-6">
            <div className="w-6 h-6 border-2 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
          </div>
        ) : members.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-4">No collaborators yet.</p>
        ) : (
          <div>
            {members.map((m) => (
              <MemberRow
                key={m.id}
                member={m}
                isOwner={isOwner}
                onRemove={handleRemove}
                removing={removingId === m.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
