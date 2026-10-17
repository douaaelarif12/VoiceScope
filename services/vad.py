"""Use faster-whisper's bundled Silero ONNX VAD, never label energy as speech."""
import numpy as np
from .acoustics import SR, dbfs


def speech_regions(wav):
    if dbfs(wav) <= -75:
        return [], "silence"
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    parts = get_speech_timestamps(np.asarray(wav,dtype=np.float32),
                                 VadOptions(min_speech_duration_ms=250, min_silence_duration_ms=300, speech_pad_ms=50),
                                 sampling_rate=SR)
    return [(p["start"]/SR,p["end"]/SR) for p in parts], "silero"
