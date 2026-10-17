"""Evaluate labelled, held-out clips. Never infer ground truth from predictions.

Manifest JSON: [{"audio":"path.wav", "speaker":"Alice", "text":"bonjour",
                "sound":"Speech"}]. Optional labels independently enable metrics.
Clips must have one speaker and one dominant sound for clip-level metrics.
"""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.acoustics import read_wav
from services.pipeline import analyse
from services.speakers import ProfileStore
from schemas import AnalysisOptions

def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):
            nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]

def macro_f1(pairs):
    labels=sorted({v for pair in pairs for v in pair})
    scores={}
    for label in labels:
        tp=sum(a==b==label for a,b in pairs)
        fp=sum(a!=label and b==label for a,b in pairs)
        fn=sum(a==label and b!=label for a,b in pairs)
        scores[label]=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0
    return {"macro":sum(scores.values())/len(scores) if scores else None,"per_class":scores}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest",type=Path)
    parser.add_argument("--profiles",type=Path,default=Path("data/voices.json"))
    parser.add_argument("--model",choices=["tiny","base","small"],default="base")
    parser.add_argument("--language",default="auto",choices=["fr","en","ar","auto"])
    parser.add_argument("--output",type=Path,default=Path("evaluation.json"))
    args=parser.parse_args()
    store=ProfileStore(args.profiles);store.load()
    clips=json.loads(args.manifest.read_text(encoding="utf-8"))
    speakers,sounds,distances,reference_words,timings,rows=[],[],0,0,[],[]
    failures=[]
    for clip in clips:
        path=(args.manifest.parent/clip["audio"]).resolve()
        try:
            wav=read_wav(path.read_bytes())
            options=AnalysisOptions(stt="text" in clip,classification="sound" in clip,modele=args.model,langue=args.language)
            start=time.perf_counter();r=analyse(wav,store,options);elapsed=time.perf_counter()-start
            timings.append(elapsed)
            predicted=max(r["statistics"],key=lambda x:x["secondes"],default={"nom":"Inconnu"})["nom"]
            text=" ".join(s["texte"] for s in r["transcriptions"])
            counts={}
            for event in r["events"]:counts[event["categorie"]]=counts.get(event["categorie"],0)+event["fin"]-event["debut"]
            sound=max(counts,key=counts.get) if counts else None
            if "speaker" in clip:
                if r["vad"]=="indisponible" or any("Reconnaissance" in w for w in r["warnings"]):
                    failures.append({"audio":clip["audio"],"metric":"speaker","error":"modèle indisponible"})
                else:speakers.append((clip["speaker"],predicted))
            if "text" in clip:
                if r["warnings"] and any("Transcription" in w for w in r["warnings"]):
                    failures.append({"audio":clip["audio"],"metric":"WER","error":"transcription indisponible"})
                else:
                    reference=clip["text"].casefold().split();hypothesis=text.casefold().split()
                    distances+=edit_distance(reference,hypothesis);reference_words+=len(reference)
            if "sound" in clip:
                if sound is None:failures.append({"audio":clip["audio"],"metric":"F1","error":"classification indisponible"})
                else:sounds.append((clip["sound"],sound))
            rows.append({"audio":clip["audio"],"speaker":predicted,"text":text,"sound":sound,"seconds":elapsed,"warnings":r["warnings"]})
        except Exception as exc:failures.append({"audio":clip["audio"],"error":str(exc)})
    report={"speaker_accuracy":sum(a==b for a,b in speakers)/len(speakers) if speakers else None,
            "speaker_clips":len(speakers),"wer":distances/reference_words if reference_words else None,
            "reference_words":reference_words,"sound_f1":macro_f1(sounds),"sound_clips":len(sounds),
            "mean_processing_seconds":sum(timings)/len(timings) if timings else None,
            "failures":failures,"clips":rows,"normalization":"casefold + whitespace; punctuation retained"}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!='clips'},ensure_ascii=True,indent=2))
    if failures:sys.exit(2)

if __name__=="__main__":main()
