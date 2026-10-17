"""Digital signal measurements. No acoustic SPL calibration is implied."""
import io
import math
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, stft, welch

SR = 16000
MAX_BYTES = 32 * 1024 * 1024
MAX_SECONDS = 300


def read_wav(raw):
    if not raw:
        raise ValueError("Fichier audio vide.")
    if len(raw) > MAX_BYTES:
        raise ValueError("Fichier trop volumineux (32 Mio maximum).")
    try:
        with sf.SoundFile(io.BytesIO(raw)) as audio:
            if audio.frames == 0 or audio.samplerate <= 0:
                raise ValueError("Audio vide.")
            if audio.frames / audio.samplerate > MAX_SECONDS or audio.channels > 8:
                raise ValueError("Audio limité à 5 minutes et 8 canaux.")
            if audio.samplerate > 192000:
                raise ValueError("Fréquence d'échantillonnage trop élevée.")
            data = audio.read(dtype="float32", always_2d=True).mean(axis=1)
            rate = audio.samplerate
    except (RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError("Format audio illisible ou incompatible.") from exc
    if not np.isfinite(data).all() or np.max(np.abs(data)) > 1.001:
        raise ValueError("Échantillons invalides : valeurs finies dans [-1, 1] requises.")
    if rate != SR:
        gcd = math.gcd(rate, SR)
        data = resample_poly(data, SR // gcd, rate // gcd)
    return data.astype(np.float32)


def dbfs(x):
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.
    return max(-120., 20 * math.log10(max(rms, 1e-6)))


def analyse_frequency(wav):
    # FFT on the whole recording; Welch is the bounded distribution for display.
    spectrum = np.abs(np.fft.rfft(wav * np.hanning(len(wav))))
    frequencies = np.fft.rfftfreq(len(wav), 1 / SR)
    energy = float(spectrum.sum())
    dominant = float(frequencies[np.argmax(spectrum)]) if energy > 1e-9 else None
    centroid = float(np.dot(frequencies, spectrum) / energy) if energy > 1e-9 else None
    f, power = welch(wav, SR, nperseg=min(2048, len(wav)))
    sfreq, times, z = stft(wav, SR, nperseg=min(512, len(wav)), noverlap=min(256, len(wav)//2))
    stride = max(1, math.ceil(len(times) / 240))
    # Peak per time bucket preserves short transients in the displayed spectrogram.
    mag = np.abs(z)
    columns = [np.max(mag[:, i:i+stride], axis=1) for i in range(0, mag.shape[1], stride)]
    heat = np.maximum(-120., 20*np.log10(np.maximum(np.stack(columns, axis=1), 1e-6)))
    hop = SR // 4
    levels = [{"t": i/SR, "fin": min(i+hop, len(wav))/SR, "dbfs": dbfs(wav[i:i+hop])}
              for i in range(0, len(wav), hop)]
    step = max(1, math.ceil(len(wav)/800))
    waveform = [{"t": i/SR, "min": float(wav[i:i+step].min()), "max": float(wav[i:i+step].max())}
                for i in range(0, len(wav), step)]
    return {"dominant_hz": dominant, "centroid_hz": centroid,
            "rms": float(np.sqrt(np.mean(wav.astype(float)**2))), "dbfs": dbfs(wav),
            "waveform": waveform, "spectrum": [{"hz": float(a), "power_db": float(10*np.log10(max(b, 1e-12)))} for a,b in zip(f,power)],
            "spectrogram": {"frequencies": sfreq.tolist(), "times": times[::stride].tolist(), "db": heat.round(2).tolist()},
            "niveaux": levels, "sample_rate": SR, "floor_dbfs": -120}


def alerts(levels, moderate=-35., high=-20., sustain=3.):
    events, start, end = [], None, None
    for frame in levels:
        if frame["dbfs"] >= high:
            start = frame["t"] if start is None else start
            end = frame["fin"]
        elif start is not None:
            if end-start >= sustain:
                events.append({"debut": start, "fin": end, "seuil_dbfs": high})
            start = None
    if start is not None and end-start >= sustain:
        events.append({"debut": start, "fin": end, "seuil_dbfs": high})
    return events
