async function lire(r) {
  if (!r.ok) {
    let msg = `Erreur HTTP ${r.status}`;
    try {
      msg = (await r.json()).detail || msg;
    } catch {}
    throw new Error(typeof msg === "string" ? msg : "Requête invalide");
  }
  return r.json();
}
const upload = (url, fields) => {
  const body = new FormData();
  Object.entries(fields).forEach(([key, value]) => body.append(key, value));
  return fetch(url, { method: "POST", body }).then(lire);
};
export const api = {
  etat: () => fetch("/api/etat").then(lire),
  personnes: () => fetch("/api/personnes").then(lire),
  ajouter: (nom, audio) => upload("/api/personnes", { nom, audio }),
  supprimer: (nom) =>
    fetch(`/api/personnes/${encodeURIComponent(nom)}`, {
      method: "DELETE",
    }).then(lire),
  importer: (fichier) => upload("/api/voix/import", { fichier }),
  analyser: (audio, options) => upload("/api/analyse", { audio, ...options }),
  sessions: () => fetch("/api/sessions").then(lire),
  session: (id) => fetch(`/api/sessions/${id}`).then(lire),
  deleteSession: (id) =>
    fetch(`/api/sessions/${id}`, { method: "DELETE" }).then(lire),
  download: async (id, format) => {
    const r = await fetch(`/api/sessions/${id}/export/${format}`);
    if (!r.ok) return lire(r);
    const url = URL.createObjectURL(await r.blob()),
      a = document.createElement("a");
    a.href = url;
    a.download = `voicescope-${id}.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
