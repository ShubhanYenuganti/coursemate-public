import { useState } from 'react';
import { formatDateTime } from '../utils/dateUtils';
import { ChevronDownIcon, TrashIcon, PinIcon } from './icons';
import MessageBubble from './MessageBubble';

export function PinsPanel({ pins, courseName, userData, materials, onDeletePin }) {
  const [expandedPin, setExpandedPin] = useState(null);

  return (
    <div className="flex-shrink-0 bg-white overflow-hidden" style={{ maxHeight: '220px' }}>
      {/* Header */}
      <div className="px-6 py-2 flex items-center gap-2 flex-shrink-0 border-b border-gray-100">
        <span className="text-indigo-500"><PinIcon filled /></span>
        <span className="text-xs font-semibold text-gray-700">Saved Pins</span>
        {pins.length > 0 && (
          <span className="px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-600 text-[10px] font-semibold">{pins.length}</span>
        )}
      </div>

      {/* List */}
      <div className="overflow-y-auto" style={{ maxHeight: '180px' }}>
        {pins.length === 0 && (
          <p className="px-6 py-2 text-xs text-gray-400 italic">No saved pins yet.</p>
        )}
        {pins.map((pin) => {
          const isExpanded = expandedPin === pin.id;
          const pinDate = pin.pinned_at ? formatDateTime(pin.pinned_at) : '';
          return (
            <div key={pin.id}>
              {/* Row */}
              <div className="flex items-center group hover:bg-gray-50 transition-colors">
              <button
                type="button"
                onClick={() => setExpandedPin(isExpanded ? null : pin.id)}
                className={`flex-1 flex gap-2 px-6 py-1.5 text-left min-w-0 ${
                  isExpanded ? 'items-start py-2' : 'items-center'
                }`}
              >
                {isExpanded ? (
                  <>
                    <span className="flex-1 min-w-0 text-[11px] font-medium text-gray-700 whitespace-normal break-words text-left">
                      {pin.chat_title || 'Chat'}
                    </span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-gray-400 transition-transform duration-200 rotate-180 mt-0.5">
                      <ChevronDownIcon />
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-[11px] font-medium text-gray-700 truncate max-w-[240px] flex-shrink-0">{pin.chat_title || 'Chat'}</span>
                    <span className="text-[10px] text-gray-300">·</span>
                    <span className="text-[10px] text-gray-500 truncate max-w-[200px] flex-shrink-0">{pin.assistant_message?.ai_model || ''}</span>
                    <span className="text-[10px] text-gray-300">·</span>
                    <span className="text-[10px] text-gray-600 flex-1 truncate">{pin.ai_summary}</span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-gray-400 transition-transform duration-200">
                      <ChevronDownIcon />
                    </span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => onDeletePin && onDeletePin(pin)}
                className="flex-shrink-0 pl-1 pr-2.5 py-1.5 text-gray-400 hover:text-red-500 transition-colors"
                aria-label="Delete pin"
              >
                <TrashIcon />
              </button>
              </div>

              {/* Expanded card */}
              {isExpanded && pin.user_message && pin.assistant_message && (
                <div className="px-4 pb-3 pt-1 space-y-3 bg-gray-50 border-t border-gray-100">
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
  );
}
