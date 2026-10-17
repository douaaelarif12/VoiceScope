"""Run real downloaded audio through each installed model; record failures honestly."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.acoustics import read_wav
from services import speakers, transcription, vad, sound_classifier

out=[]
for file in Path("tmp/audio").glob("*.wav"):
    wav=read_wav(file.read_bytes())
    for name,call in [("silero",lambda:vad.speech_regions(wav)),
                      ("resemblyzer",lambda:{"embedding_dim":len(speakers.embed(wav))}),
                      ("whisper_tiny",lambda:transcription.transcribe(wav,"tiny","en")),
                      ("yamnet",lambda:sound_classifier.classify(wav))]:
        start=time.perf_counter()
        try:
            value=call()
            row={"file":file.name,"model":name,"ok":True,"result":value}
        except Exception as exc:
            row={"file":file.name,"model":name,"ok":False,"error":str(exc)}
        row["seconds"]=time.perf_counter()-start
        out.append(row)
        print(json.dumps(row,ensure_ascii=True),flush=True)
Path("tmp/model-smoke.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
