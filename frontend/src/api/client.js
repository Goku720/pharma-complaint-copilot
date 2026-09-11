const BASE = "/api";

function getSessionId() {
  let id = sessionStorage.getItem("qms_session_id");
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem("qms_session_id", id);
  }
  return id;
}

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  sessionId: getSessionId(),

  sendMessage: (message) =>
    fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId(), message }),
    }).then(handle),

  uploadDocument: (file) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/upload/${getSessionId()}`, {
      method: "POST",
      body: form,
    }).then(handle);
  },

  getState: () => fetch(`${BASE}/state/${getSessionId()}`).then(handle),

  reset: () => fetch(`${BASE}/reset/${getSessionId()}`, { method: "POST" }).then(handle),
};