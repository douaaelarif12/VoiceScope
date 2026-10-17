"""Real model smoke test against isolated profiles, never a biometric benchmark.

Input: public openai/whisper tests/jfk.flac, downloaded manually to tmp/audio.
Enrollment and analysis overlap intentionally: validates plumbing, not accuracy.
"""
import io
import json
import sys
import tempfile
from pathlib import Path
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from services.acoustics import read_wav
from services.speakers import ProfileStore
import server

def encode(wav):
    buffer=io.BytesIO()
    sf.write(buffer,wav,16000,format="WAV")
    return buffer.getvalue()

wav=read_wav(Path("tmp/audio/jfk.flac").read_bytes())
with tempfile.TemporaryDirectory(prefix="e2e-",dir="tmp") as directory:
    server.store=ProfileStore(Path(directory)/"voices.json")
    with TestClient(server.app) as client:
        enrolled=client.post("/api/personnes",data={"nom":"Extrait public JFK"},
                             files={"audio":("enroll.wav",encode(wav[:96000]))})
        print("enrollment",enrolled.status_code,enrolled.text,flush=True)
        enrolled.raise_for_status()
        server.store.load()
        response=client.post("/api/analyse",data={"modele":"tiny","langue":"en","classification":"true"},
                             files={"audio":("jfk.wav",encode(wav))})
        response.raise_for_status()
        result=response.json()
        Path("tmp/e2e-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        exports={}
        for kind in ("json","csv","txt","pdf"):
            exported=client.get(f'/api/sessions/{result["id"]}/export/{kind}')
            exported.raise_for_status()
            exports[kind]=len(exported.content)
            if kind=="pdf":
                Path("output/pdf").mkdir(parents=True,exist_ok=True)
                Path("output/pdf/validation-public-audio.pdf").write_bytes(exported.content)
        summary={"enrollment":enrolled.status_code,"seconds":result["duree"],"processing_seconds":result["processing_seconds"],
                 "warnings":result["warnings"],"statistics":result["statistics"],"transcriptions":result["transcriptions"],
                 "sound_categories":sorted({e["categorie"] for e in result["events"]}),"export_bytes":exports,
                 "note":"Smoke test only: enrollment overlaps analysis; no accuracy claim."}
        Path("tmp/e2e-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(summary,ensure_ascii=True),flush=True)
