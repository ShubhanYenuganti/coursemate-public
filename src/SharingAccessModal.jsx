import { useState } from "react";

const SHARE_URL = "https://coursemate.app/share/9bd6807c-dc4b";

const MEMBERS = [
  { id: 1, name: "Mara Okonkwo",  email: "mara@designco.io",    status: "accepted", role: "editor" },
  { id: 2, name: "Julian Reyes",  email: "j.reyes@studio.com",  status: "pending",  role: "viewer" },
  { id: 3, name: "Soo-Yeon Park", email: "soo@parkcreative.kr", status: "accepted", role: "viewer" },
  { id: 4, name: "Dmitri Volkov", email: "d.volkov@vk.co",      status: "denied",   role: "admin"  },
];

const ROLE_META = {
  admin:  { icon: "⭐", label: "Admin",  pill: "bg-amber-50 text-amber-700 border-amber-200"   },
  editor: { icon: "✏️", label: "Editor", pill: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  viewer: { icon: "👁️", label: "Viewer", pill: "bg-gray-50 text-gray-600 border-gray-200"       },
};

const STATUS_META = {
  accepted: { dot: "bg-green-500", label: "Accepted", text: "text-green-700", bg: "bg-green-50",  border: "border-green-200"  },
  pending:  { dot: "bg-amber-400", label: "Pending",  text: "text-amber-700", bg: "bg-amber-50",  border: "border-amber-200"  },
  denied:   { dot: "bg-red-400",   label: "Denied",   text: "text-red-700",   bg: "bg-red-50",    border: "border-red-200"    },
};

const AVATAR_COLORS = [
  "bg-indigo-400", "bg-cyan-500", "bg-violet-400",
  "bg-teal-500",   "bg-sky-500",  "bg-rose-400",
];

function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function initials(name) {
  return name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function Avatar({ name }) {
  return (
    <div className={`w-9 h-9 rounded-full ${avatarColor(name)} flex items-center justify-center flex-shrink-0`}>
      <span className="text-xs font-bold text-white tracking-wide">{initials(name)}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  const m = STATUS_META[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${m.text} ${m.bg} ${m.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${m.dot}`} />
      {m.label}
    </span>
  );
}

function RolePill({ role }) {
  const m = ROLE_META[role];
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${m.pill}`}>
      <span>{m.icon}</span>
      {m.label}
    </span>
  );
}

function RemoveButton() {
  return (
    <button
      type="button"
      className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors"
      aria-label="Remove"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>
  );
}

function MemberRow({ member }) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
      <Avatar name={member.name} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">{member.name}</p>
        <p className="text-xs text-gray-400 truncate">{member.email}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <StatusBadge status={member.status} />
        <RolePill role={member.role} />
        <RemoveButton />
      </div>
    </div>
  );
}

function LinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-gray-400">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

export default function SharingAccessModal() {
  const [filter, setFilter]   = useState("all");
  const [copied, setCopied]   = useState(false);

  const counts = {
    pending:  MEMBERS.filter((m) => m.status === "pending").length,
    accepted: MEMBERS.filter((m) => m.status === "accepted").length,
    denied:   MEMBERS.filter((m) => m.status === "denied").length,
  };

  const filtered = filter === "all" ? MEMBERS : MEMBERS.filter((m) => m.status === filter);

  const handleCopy = () => {
    navigator.clipboard.writeText(SHARE_URL).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filterTabs = [
    { key: "all",      label: "All" },
    { key: "pending",  label: `Pending · ${counts.pending}` },
    { key: "accepted", label: `Accepted · ${counts.accepted}` },
    { key: "denied",   label: `Denied · ${counts.denied}` },
  ];

  return (
    <div className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-sm p-6 space-y-6">

      {/* ── Shareable link ── */}
      <div>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
            Shareable Link
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-600 font-medium border border-gray-200">
              Anyone with link
            </span>
            <span className="text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-600 font-medium border border-gray-200">
              👁️ Viewer
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 flex items-center gap-2 px-3 py-2.5 rounded-xl border border-gray-200 bg-gray-50 min-w-0">
            <LinkIcon />
            <span className="text-sm text-gray-500 truncate">{SHARE_URL}</span>
          </div>
          <button
            type="button"
            onClick={handleCopy}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors flex-shrink-0 border ${
              copied
                ? "bg-green-50 text-green-700 border-green-200"
                : "bg-indigo-50 text-indigo-600 border-indigo-200 hover:bg-indigo-100"
            }`}
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>

      {/* ── Invite ── */}
      <div className="flex gap-2 flex-wrap sm:flex-nowrap">
        <input
          type="email"
          placeholder="Invite by email address…"
          className="flex-1 min-w-0 px-4 py-2.5 rounded-xl border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm text-gray-900 placeholder-gray-400"
        />
        <select className="px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-400 flex-shrink-0">
          <option value="viewer">👁️ Viewer</option>
          <option value="editor">✏️ Editor</option>
          <option value="admin">⭐ Admin</option>
        </select>
        <button
          type="button"
          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors flex-shrink-0"
        >
          + Invite
        </button>
      </div>

      {/* ── With access ── */}
      <div>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
            {MEMBERS.length} With Access
          </span>
          <div className="flex items-center gap-1.5 flex-wrap">
            {filterTabs.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                  filter === f.key
                    ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                    : "bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-200"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          {filtered.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-4">No members in this category.</p>
          ) : (
            filtered.map((m) => <MemberRow key={m.id} member={m} />)
          )}
        </div>
      </div>

    </div>
  );
}
