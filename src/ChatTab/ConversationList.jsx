// ─── ConversationList ─────────────────────────────────────────────────────────

import { UnarchiveIcon, ArchiveIcon, ChatBubbleIcon, TrashIcon } from './icons';

export function ConvItem({ conv, active, onClick, onDoubleClick, onArchive }) {
  return (
    <div className={`group w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs transition-colors ${
      active
        ? 'bg-accent text-accent-foreground font-medium'
        : 'text-muted-foreground hover:bg-accent hover:text-foreground'
    }`}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onArchive(conv.id, !conv.is_archived); }}
        title={conv.is_archived ? 'Unarchive' : 'Archive'}
        className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-all text-muted-foreground hover:text-primary hover:bg-accent"
      >
        {conv.is_archived ? <UnarchiveIcon /> : <ArchiveIcon />}
      </button>
      <button
        type="button"
        onClick={onClick}
        onDoubleClick={onDoubleClick}
        className="flex-1 flex items-center gap-2 min-w-0 text-left"
      >
        <span className={`flex-shrink-0 ${active ? 'text-primary' : 'text-muted-foreground'}`}>
          <ChatBubbleIcon />
        </span>
        <span className="truncate">{conv.title}</span>
      </button>
    </div>
  );
}

export function ArchivedConvItem({ conv, onDelete, onUnarchive }) {
  return (
    <div className="group w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors">
      <button
        type="button"
        onClick={() => onDelete(conv.id)}
        title="Delete permanently"
        className="flex-shrink-0 p-0.5 rounded transition-all text-muted-foreground hover:text-destructive hover:bg-destructive/10"
      >
        <TrashIcon />
      </button>
      <button
        type="button"
        onClick={() => onUnarchive(conv.id)}
        title="Unarchive"
        className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-all text-muted-foreground hover:text-primary hover:bg-accent"
      >
        <UnarchiveIcon />
      </button>
      <span className="flex-1 truncate min-w-0">{conv.title}</span>
    </div>
  );
}
