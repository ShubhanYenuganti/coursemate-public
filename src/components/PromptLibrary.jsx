import React, { useEffect, useState } from 'react';

export default function PromptLibrary({ onInsert, onClose }) {
  const [prompts, setPrompts] = useState([]);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');

  const load = () =>
    fetch('/api/prompts', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { prompts: [] }))
      .then((data) => setPrompts(data.prompts ?? []))
      .catch(() => {});
  useEffect(() => { load(); }, []);

  async function create() {
    if (!title.trim() || !body.trim()) return;
    await fetch('/api/prompts', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body }),
    });
    setTitle(''); setBody(''); load();
  }

  async function remove(id) {
    await fetch(`/api/prompts?id=${id}`, { method: 'DELETE', credentials: 'include' });
    load();
  }

  return (
    <div className="absolute bottom-14 left-0 w-80 max-h-96 overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg p-3 z-30">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Saved Prompts</span>
        <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
      </div>
      {prompts.length === 0 && (
        <p className="text-xs text-gray-400 px-2 py-1">No saved prompts yet.</p>
      )}
      {prompts.map((p) => (
        <div key={p.id} className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-indigo-50">
          <button
            type="button"
            className="flex-1 text-left"
            onClick={() => { onInsert(p.body); onClose(); }}
          >
            <div className="text-sm text-gray-800">{p.title}</div>
            <div className="text-[11px] text-gray-400 truncate">{p.body}</div>
          </button>
          <button
            type="button"
            onClick={() => remove(p.id)}
            className="text-gray-300 hover:text-rose-500 text-lg leading-none"
          >×</button>
        </div>
      ))}
      <div className="mt-2 border-t border-gray-100 pt-2 space-y-1">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          className="w-full text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none"
        />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Prompt text"
          className="w-full text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none"
          rows={2}
        />
        <button
          type="button"
          onClick={create}
          className="w-full text-sm bg-indigo-600 text-white rounded py-1 hover:bg-indigo-700"
        >Save prompt</button>
      </div>
    </div>
  );
}
