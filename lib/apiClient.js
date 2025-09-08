'use client';

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function getJSON(path, opts = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'GET',
    credentials: 'include',
    ...opts,
    headers: {
      'Accept': 'application/json',
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`GET ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function postJSON(path, body, opts = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(opts.headers || {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`POST ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

/**
 * POST and consume a text/event-stream-like response.
 * Returns an async iterator over parsed events:
 * - { type: 'delta', text: string }
 * - { type: 'final', ... }
 * - { type: 'error', message: string }
 */
export async function* postStream(path, body, opts = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...(opts.headers || {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(`POST(stream) ${path} failed: ${res.status} ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Parse by SSE lines (data: {...})\n\n
    let idx;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      // Extract data: lines
      const lines = chunk.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;
          try {
            const evt = JSON.parse(jsonStr);
            yield evt;
          } catch {
            // ignore non-JSON data lines
          }
        }
      }
    }
  }
}
