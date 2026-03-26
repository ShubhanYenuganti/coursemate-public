// Ensures a bare ISO string (no timezone designator) is treated as UTC.
function parseUTC(str) {
  if (!str) return null;
  const s = String(str);
  // Already has timezone info (Z, +HH:MM, -HH:MM)
  if (/Z|[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  // Bare string — append Z so JS treats it as UTC
  return new Date(s + 'Z');
}

// "Mar 25, 2026, 3:42 PM" — date + time in user's local tz
export function formatDateTime(str) {
  const d = parseUTC(str);
  if (!d || isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  });
}

// "Mar 25, 2026" — date only
export function formatDate(str) {
  const d = parseUTC(str);
  if (!d || isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export { parseUTC };
