import io
import numpy as np
import pytest
import soundfile as sf
from services.acoustics import read_wav, analyse_frequency, dbfs, alerts
from services.speakers import decision, identify, ProfileStore

def wav_bytes(data, sr=16000):
    stream=io.BytesIO()
    sf.write(stream,data,sr,format="WAV",subtype="FLOAT")
    return stream.getvalue()

@pytest.mark.parametrize("raw",[b"",b"not audio",wav_bytes(np.zeros(0))])
def test_invalid_audio(raw):
    with pytest.raises(ValueError): read_wav(raw)

def test_stereo_resampling():
    t=np.arange(48000)/48000
    x=np.column_stack([.5*np.sin(2*np.pi*440*t)]*2)
    y=read_wav(wav_bytes(x,48000))
    assert y.shape==(16000,)
    assert analyse_frequency(y)["dominant_hz"]==pytest.approx(440,abs=1)

@pytest.mark.parametrize("x",[np.array([np.nan]),np.array([np.inf]),np.array([2.])])
def test_bad_samples(x):
    with pytest.raises(ValueError): read_wav(wav_bytes(x))

def test_fft_stft_and_dbfs():
    x=.5*np.sin(2*np.pi*1000*np.arange(16000)/16000)
    r=analyse_frequency(x.astype(np.float32))
    assert r["dominant_hz"]==pytest.approx(1000,abs=1)
    assert r["centroid_hz"]==pytest.approx(1000,abs=2)
    assert r["dbfs"]==pytest.approx(-9.0309,abs=.001)
    heat=np.asarray(r["spectrogram"]["db"])
    assert r["spectrogram"]["frequencies"][heat[:,10].argmax()]==1000
    assert len(r["waveform"])<=800
    assert len(r["spectrogram"]["times"])<=240

def test_silence():
    r=analyse_frequency(np.zeros(16000,dtype=np.float32))
    assert dbfs([])==-120
    assert r["dbfs"]==-120
    assert r["dominant_hz"] is None
    assert r["centroid_hz"] is None
    assert np.isfinite(r["spectrogram"]["db"]).all()

def test_alerts_consecutive_and_final_partial():
    levels=[{"t":i*.25,"fin":(i+1)*.25,"dbfs":-10 if i!=6 else -50} for i in range(20)]
    assert alerts(levels,high=-20,sustain=3)==[{"debut":1.75,"fin":5.,"seuil_dbfs":-20}]
    assert alerts(levels,high=-20,sustain=4)==[]

def test_unknown_ambiguous():
    assert decision({"A":.4})[0]=="Inconnu"
    assert decision({"A":.8,"B":.79})[0]=="Indéterminé"
    assert decision({"A":.9,"B":.7})[0]=="A"
    assert decision({})[0]=="Inconnu"

def test_mixed_voice(monkeypatch):
    from services import speakers
    vectors=iter([np.array([1.,0.]),np.array([1.,0.]),np.array([0.,1.]),np.array([0.,1.])])
    monkeypatch.setattr(speakers,"embed",lambda wav:next(vectors))
    r=identify(np.ones(48000),{"A":np.array([1.,0.]),"B":np.array([0.,1.])},.75,.05)
    assert r["locuteur"]=="Indéterminé"

def test_consistency_uses_complete_windows(monkeypatch):
    from services import speakers
    lengths=[]
    def encode(wav):
        lengths.append(len(wav))
        return np.array([1.,0.])
    monkeypatch.setattr(speakers,"embed",encode)
    r=identify(np.ones(56000),{"A":np.array([1.,0.])},.75,.05)
    assert r["locuteur"]=='A'
    assert min(lengths)>=24000
    short=identify(np.ones(32000),{"A":np.array([1.,0.])},.75,.05)
    assert short["locuteur"]=='A'
    assert 'chevauchement' in short['raison']

def test_profiles_atomic_validation(tmp_path):
    store=ProfileStore(tmp_path/"voices.json")
    profile={"echantillons":[[1.]+[0.]*255]}
    store.merge({"A":profile,"B":profile,"C":profile})
    before=store.path.read_bytes()
    with pytest.raises(ValueError):store.merge({"D":profile})
    assert store.path.read_bytes()==before
    with pytest.raises(ValueError):store.merge({"A":{"echantillons":[[float('nan')]*256]}})
    store.load()
    assert len(store.list())==3

def test_duration_limit():
    with pytest.raises(ValueError):read_wav(wav_bytes(np.zeros(16000*301)))
