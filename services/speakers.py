"""Resemblyzer profiles and conservative cosine decisions."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .privacy import protect, unprotect

MODEL_LOCK = threading.RLock()
_encoder = None


def get_encoder():
    global _encoder
    with MODEL_LOCK:
        if _encoder is None:
            from resemblyzer import VoiceEncoder
            _encoder = VoiceEncoder("cpu", verbose=False)
        return _encoder


def prep(wav):
    from resemblyzer import preprocess_wav
    return preprocess_wav(wav, source_sr=16000)


def embed(wav):
    with MODEL_LOCK:
        speech = prep(wav)
        if len(speech) < 8000:
            raise ValueError("Parole insuffisante pour une empreinte.")
        v = get_encoder().embed_utterance(speech)
        return v / max(np.linalg.norm(v), 1e-9)


def decision(scores, threshold=.75, margin=.05):
    ranked = sorted((scores or {}).items(), key=lambda x: x[1], reverse=True)
    if not ranked or ranked[0][1] < threshold:
        return "Inconnu", "similarité insuffisante"
    if len(ranked)>1 and ranked[0][1]-ranked[1][1] < margin:
        return "Indéterminé", "profils trop proches"
    return ranked[0][0], None


def identify(wav, cents, threshold, margin):
    if not cents:
        return {"locuteur": "Inconnu", "raison": "aucun profil", "scores": None}
    # Never expand a clip into neighbouring speech. Compare subwindows as well.
    if len(wav) < 16000:
        return {"locuteur": "Indéterminé", "raison": "segment inférieur à 1 seconde", "scores": None}
    vectors = [embed(wav)]
    # Need two complete, independent 1.5s windows before checking consistency.
    # Short padded tails yield unreliable embeddings and must not veto a whole clip.
    if len(wav) >= 48000:
        vectors += [embed(part) for part in np.array_split(wav, len(wav)//24000)]
    all_scores = [{n: float(np.clip(np.dot(v,c), -1,1)) for n,c in cents.items()} for v in vectors]
    who, reason = decision(all_scores[0], threshold, margin)
    local = [decision(s, threshold, margin)[0] for s in all_scores[1:]]
    if local and any(n != who for n in local):
        who, reason = "Indéterminé", "attribution instable ou plusieurs voix possibles"
    elif not local and reason is None:
        reason = "segment court : chevauchement non vérifiable"
    return {"locuteur": who, "raison": reason, "scores": all_scores[0]}


class ProfileStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.voices = {}

    @staticmethod
    def validate(data):
        if not isinstance(data, dict) or len(data)>3:
            raise ValueError("Trois profils maximum.")
        names = set()
        for name, value in data.items():
            if not isinstance(name,str) or not name.strip() or name != name.strip() or len(name)>40 or name.casefold() in names:
                raise ValueError("Noms invalides ou dupliqués.")
            names.add(name.casefold())
            if not isinstance(value,dict):
                raise ValueError("Profil invalide.")
            arr = np.asarray(value.get("echantillons", []), dtype=float)
            if arr.ndim!=2 or arr.shape[1]!=256 or not 1<=len(arr)<=30 or not np.isfinite(arr).all():
                raise ValueError("Empreintes invalides (1 à 30 vecteurs de 256 valeurs).")
            norms = np.linalg.norm(arr,axis=1)
            if not np.isfinite(norms).all() or np.any(norms<1e-6):
                raise ValueError("Empreinte nulle.")
            if value.get("ajoute") is not None and not isinstance(value["ajoute"],str):
                raise ValueError("Date invalide.")
        return data

    def load(self):
        if self.path.exists():
            self.voices = self.validate(json.loads(unprotect(self.path.read_bytes()).decode("utf-8")))

    def save(self, data):
        self.validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(protect(json.dumps(data, ensure_ascii=False).encode("utf-8")))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        self.voices = data

    def merge(self, incoming):
        self.validate(incoming)
        with self.lock:
            updated = json.loads(json.dumps(self.voices))
            for name, value in incoming.items():
                key = next((n for n in updated if n.casefold()==name.casefold()),name)
                entry = updated.setdefault(key,{"echantillons":[],"ajoute":datetime.now(timezone.utc).isoformat()})
                entry["echantillons"].extend(value["echantillons"])
            self.save(updated)

    def list(self):
        with self.lock:
            return [{"nom":n,"echantillons":len(v["echantillons"]),"ajoute":v.get("ajoute")} for n,v in sorted(self.voices.items())]

    def centroids(self):
        with self.lock:
            result = {}
            for n,v in self.voices.items():
                a = np.asarray(v["echantillons"],dtype=float)
                a /= np.linalg.norm(a,axis=1,keepdims=True)
                mean = a.mean(axis=0)
                result[n] = mean / max(np.linalg.norm(mean),1e-9)
            return result
