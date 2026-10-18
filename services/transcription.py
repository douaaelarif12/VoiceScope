"""One Whisper model in memory, serialized CPU inference."""
import threading

_lock = threading.RLock()
_model = None
_size = None


def transcribe(wav, size="base", language="fr", regions=None):
    global _model, _size
    with _lock:
        if _model is None or _size != size:
            from faster_whisper import WhisperModel
            _model = None
            _model = WhisperModel(size, device="cpu", compute_type="int8")
            _size = size
        requested = None if language == "auto" else language
        # Transcribing each VAD region separately prevents Whisper from carrying
        # silence/noise or a previous speaker into the next phrase. The offsets
        # are restored below so the API keeps its original timeline contract.
        clip_timestamps = None
        if regions:
            valid = [(max(0.0, float(a)), min(len(wav) / 16000.0, float(b)))
                     for a, b in regions if float(b) - float(a) >= 0.1]
            if valid:
                # faster-whisper accepts all VAD intervals in one call and
                # keeps timestamps on the original recording timeline.
                clip_timestamps = [value for pair in valid for value in pair]
        raw, info = _model.transcribe(
            wav,
            language=requested,
            vad_filter=not bool(clip_timestamps),
            clip_timestamps=clip_timestamps or "0",
            word_timestamps=True,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
        )
        return [{"debut":float(s.start), "fin":float(s.end), "texte":s.text.strip()}
                for s in raw if s.text.strip()], info.language
