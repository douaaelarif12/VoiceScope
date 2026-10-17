"""One Whisper model in memory, serialized CPU inference."""
import threading

_lock = threading.RLock()
_model = None
_size = None


def transcribe(wav, size="base", language="fr"):
    global _model, _size
    with _lock:
        if _model is None or _size != size:
            from faster_whisper import WhisperModel
            _model = None
            _model = WhisperModel(size, device="cpu", compute_type="int8")
            _size = size
        raw, info = _model.transcribe(wav, language=None if language=="auto" else language,
                                      vad_filter=True, word_timestamps=True, beam_size=3,
                                      condition_on_previous_text=False)
        return [{"debut":float(s.start), "fin":float(s.end), "texte":s.text.strip()}
                for s in raw if s.text.strip()], info.language
