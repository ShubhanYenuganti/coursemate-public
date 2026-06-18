import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { formatDateTime } from '../utils/dateUtils';
import { ChevronDownIcon, TrashIcon, PinIcon } from './icons';
import MessageBubble from './MessageBubble';

export function PinsPanel({ pins, courseName, userData, materials, onDeletePin }) {
  const [expandedPin, setExpandedPin] = useState(null);

  return (
    <TooltipProvider delayDuration={300}>
    <div className="flex-shrink-0 bg-background overflow-hidden border-b border-border" style={{ maxHeight: '220px' }}>
      {/* Header */}
      <div className="px-6 py-2 flex items-center gap-2 flex-shrink-0 border-b border-border">
        <span className="text-primary"><PinIcon filled /></span>
        <span className="text-xs font-semibold text-foreground">Saved Pins</span>
        {pins.length > 0 && (
          <span className="px-1.5 py-0.5 rounded-full bg-accent text-primary text-[10px] font-semibold">{pins.length}</span>
        )}
      </div>

      {/* List */}
      <div className="overflow-y-auto" style={{ maxHeight: '180px' }}>
        {pins.length === 0 && (
          <p className="px-6 py-2 text-xs text-muted-foreground italic">No saved pins yet.</p>
        )}
        {pins.map((pin) => {
          const isExpanded = expandedPin === pin.id;
          const pinDate = pin.pinned_at ? formatDateTime(pin.pinned_at) : '';
          return (
            <div key={pin.id}>
              {/* Row */}
              <div className="flex items-center group hover:bg-accent transition-colors">
              {/* Full-row expand toggle stays a raw button: a fixed-size icon Button
                  would break the flex-1 click target that spans the whole row. */}
              <button
                type="button"
                onClick={() => setExpandedPin(isExpanded ? null : pin.id)}
                className={`flex-1 flex gap-2 px-6 py-1.5 text-left min-w-0 ${
                  isExpanded ? 'items-start py-2' : 'items-center'
                }`}
              >
                {isExpanded ? (
                  <>
                    <span className="flex-1 min-w-0 text-[11px] font-medium text-foreground whitespace-normal break-words text-left">
                      {pin.chat_title || 'Chat'}
                    </span>
                    <span className="text-[10px] text-muted-foreground flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-muted-foreground transition-transform duration-200 rotate-180 mt-0.5">
                      <ChevronDownIcon />
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-[11px] font-medium text-foreground truncate max-w-[240px] flex-shrink-0">{pin.chat_title || 'Chat'}</span>
                    <span className="text-[10px] text-muted-foreground">·</span>
                    <span className="text-[10px] text-muted-foreground truncate max-w-[200px] flex-shrink-0">{pin.assistant_message?.ai_model || ''}</span>
                    <span className="text-[10px] text-muted-foreground">·</span>
                    <span className="text-[10px] text-muted-foreground flex-1 truncate">{pin.ai_summary}</span>
                    <span className="text-[10px] text-muted-foreground flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-muted-foreground transition-transform duration-200">
                      <ChevronDownIcon />
                    </span>
                  </>
                )}
              </button>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => onDeletePin && onDeletePin(pin)}
                      className="flex-shrink-0 mr-1.5 text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="Delete pin"
                    >
                      <TrashIcon />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">Delete pin</TooltipContent>
                </Tooltip>
              </div>

              {/* Expanded card */}
              {isExpanded && pin.user_message && pin.assistant_message && (
                <div className="px-4 pb-3 pt-1 space-y-3 bg-muted/50 border-t border-border">
                  <MessageBubble
                    msg={pin.user_message}
                    courseName={courseName}
                    userPicture={userData?.picture}
                    onCiteClick={null}
                    webSearchUrls={null}
                    isEditing={false}
                    editingContent=""
                    onEditStart={null}
                    onEditChange={null}
                    onEditSave={null}
                    onEditCancel={null}
                    canEdit={false}
                    replyHistory={null}
                    onRevert={null}
                    onRestore={null}
                    onRegenerate={null}
                    availableModels={[]}
                    materials={materials}
                    onPin={null}
                    isPinned={false}
                  />
                  <MessageBubble
                    msg={pin.assistant_message}
                    courseName={courseName}
                    userPicture={userData?.picture}
                    onCiteClick={null}
                    webSearchUrls={null}
                    isEditing={false}
                    editingContent=""
                    onEditStart={null}
                    onEditChange={null}
                    onEditSave={null}
                    onEditCancel={null}
                    canEdit={false}
                    replyHistory={null}
                    onRevert={null}
                    onRestore={null}
                    onRegenerate={null}
                    availableModels={[]}
                    materials={materials}
                    onPin={null}
                    isPinned={false}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
    </TooltipProvider>
  );
}
