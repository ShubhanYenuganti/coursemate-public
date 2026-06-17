const ownerPills = [
  { id: "all", label: "All materials" },
  { id: "mine", label: "My materials" },
];
const typePills = [
  { id: "all", label: "All types", prefix: null },
  { id: "uploaded", label: "Uploaded", prefix: "↑" },
  { id: "generated", label: "Generated", prefix: "✦" },
];

export default function FilterBar({ ownerFilter, setOwnerFilter, typeFilter, setTypeFilter }) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-full bg-background border border-border shadow-sm w-fit flex-wrap">
      {/* Owner group */}
      <div className="flex items-center gap-0.5">
        {ownerPills.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setOwnerFilter(p.id)}
            className={`px-3.5 py-1 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              ownerFilter === p.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-border" />

      {/* Type group label */}
      <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest select-none pl-1">
        Show
      </span>

      {/* Type group */}
      <div className="flex items-center gap-0.5">
        {typePills.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setTypeFilter(p.id)}
            className={`flex items-center gap-1 px-3.5 py-1 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              typeFilter === p.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.prefix && <span className="text-xs">{p.prefix}</span>}
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}
