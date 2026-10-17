"""Optional YAMNet. Labels are read from the model's actual AudioSet class map."""
import csv
import os
import threading
import numpy as np

_lock = threading.Lock()
_model = None
_labels = None


def classify(wav, threshold=.3):
    global _model, _labels
    with _lock:
        if _model is None:
            import tensorflow_hub as hub
            model = hub.load(os.getenv("YAMNET_MODEL", "https://tfhub.dev/google/yamnet/1"))
            path = model.class_map_path().numpy().decode("utf-8")
            with open(path, encoding="utf-8") as stream:
                labels = [r["display_name"] for r in csv.DictReader(stream)]
            _model, _labels = model, labels
        scores, _, _ = _model(np.asarray(wav, dtype=np.float32))
        scores = scores.numpy()
    events = []
    duration = len(wav)/16000
    for i, row in enumerate(scores):
        start = i*.48
        if start>=duration:
            break
        best = int(np.argmax(row))
        # Non-overlapping decision bins. Model receptive field is 0.96s.
        events.append({"debut":start,"fin":duration if i==len(scores)-1 else min(start+.48,duration),
                       "categorie":_labels[best] if row[best]>=threshold else "Inconnu",
                       "score":float(row[best]),"modele":"YAMNet"})
    return events
