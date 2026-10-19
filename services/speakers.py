"""Resemblyzer profiles and closest-match cosine decisions."""
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

def embed_samples(wav):
    if len(wav) < 48000:
        raise ValueError("Au moins 3 secondes de parole requises ; enregistrez 10 à 15 secondes.")
    window = 3 * 16000
    return [embed(wav[start:start + window]) for start in range(0, len(wav) - window + 1, window)]


def decision(scores, threshold=.75, margin=.05):
    ranked = sorted((scores or {}).items(), key=lambda x: x[1], reverse=True)
    if not ranked:
        return "Inconnu", "similarité insuffisante"
    if ranked[0][1] < threshold:
        return ranked[0][0], "similarité faible : personne la plus proche retenue"
    if len(ranked)>1 and ranked[0][1]-ranked[1][1] < margin:
        return ranked[0][0], "scores proches : personne au score le plus élevé retenue"
    return ranked[0][0], None


def _profile_scores(vector, profiles):
    scores = {}
    for name, profile in profiles.items():
        samples = np.asarray(profile, dtype=float)
        if samples.ndim == 1:
            samples = samples.reshape(1, -1)
        samples = samples / np.maximum(np.linalg.norm(samples, axis=1, keepdims=True), 1e-9)
        similarities = samples @ vector
        nearest = float(np.max(similarities))
        centroid = samples.mean(axis=0)
        centroid /= max(np.linalg.norm(centroid), 1e-9)
        scores[name] = float(.7 * nearest + .3 * np.dot(centroid, vector))
    return scores


def identify(wav, profiles, threshold, margin):
    if not profiles:
        return {"locuteur": "Inconnu", "raison": "aucun profil", "scores": None}
    # Resemblyzer needs at least half a second; never invent a match below that.
    if len(wav) < 8000:
        return {"locuteur": "Inconnu", "raison": "parole insuffisante pour comparer les profils", "scores": None}
    vectors = [embed(wav)]
    # Need two complete, independent 1.5s windows before checking consistency.
    # Short padded tails yield unreliable embeddings and must not veto a whole clip.
    if len(wav) >= 48000:
        vectors += [embed(part) for part in np.array_split(wav, len(wav)//24000)]
    all_scores = [_profile_scores(v, profiles) for v in vectors]
    effective_threshold = max(.62, threshold - .10)
    mean_scores = {name: float(np.mean([scores[name] for scores in all_scores])) for name in profiles}
    who, reason = decision(mean_scores, effective_threshold, margin)
    local = [decision(s, effective_threshold, margin)[0] for s in all_scores[1:]]
    if local:
        agreement = sum(n == who for n in local) / len(local)
        if agreement < 1 and reason is None:
            reason = "voix variables : personne au score moyen le plus élevé retenue"
    elif reason is None:
        reason = "segment court : chevauchement non vérifiable"
    return {"locuteur": who, "raison": reason, "scores": mean_scores}


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

    def templates(self):
        with self.lock:
            result = {}
            for name, value in self.voices.items():
                samples = np.asarray(value["echantillons"], dtype=float)
                result[name] = samples / np.maximum(np.linalg.norm(samples, axis=1, keepdims=True), 1e-9)
            return result
