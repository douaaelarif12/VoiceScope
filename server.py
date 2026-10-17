"""VoiceScope AI: local FastAPI service. Run one worker on loopback only."""
import importlib.util
import json
import logging
import os
import threading
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError
from schemas import AnalysisOptions, AnalysisResult, Profile
from services.acoustics import MAX_BYTES, read_wav
from services.speakers import ProfileStore, embed
from services.pipeline import analyse
from services.body_limit import BodyLimitMiddleware
from services.vad import speech_regions
import numpy as np

BASE = Path(__file__).resolve().parent
store = ProfileStore(Path(os.getenv("VOICESCOPE_DATA", str(BASE/"data")))/"voices.json")
results = OrderedDict()
result_lock = threading.RLock()
work_lock = threading.Lock()
log = logging.getLogger("voicescope")

@asynccontextmanager
async def lifespan(app):
    store.load()
    yield

app = FastAPI(title="VoiceScope AI",version="2.0.0",lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","testserver"])
app.add_middleware(BodyLimitMiddleware,max_bytes=MAX_BYTES+65536)

@app.middleware("http")
async def local_security(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ("http://localhost:8000","http://127.0.0.1:8000","http://localhost:5173","http://127.0.0.1:5173"):
        return Response("Origine non autorisée",status_code=403)
    try:
        length = int(request.headers.get("content-length","0"))
    except ValueError:
        return Response("Content-Length invalide",status_code=400)
    if length > MAX_BYTES+65536:
        return Response("Téléversement trop volumineux",status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

def read_upload(upload, limit=MAX_BYTES):
    raw = upload.file.read(limit+1)
    if len(raw)>limit:
        raise HTTPException(413,"Fichier trop volumineux.")
    return raw

def decode(upload):
    try:
        return read_wav(read_upload(upload))
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc

def analysis_options(stt: bool=Form(True),modele: str=Form("base"),langue: str=Form("fr"),
                     fenetre: float=Form(3),seuil: float=Form(.75),ecart: float=Form(.05),
                     classification: bool=Form(True),sound_threshold: float=Form(.3),
                     moderate_dbfs: float=Form(-35),high_dbfs: float=Form(-20),alert_seconds: float=Form(3)):
    try:
        return AnalysisOptions(**locals())
    except ValidationError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.get("/api/etat")
def etat():
    return {"pret":importlib.util.find_spec("resemblyzer") is not None,
            "stt_disponible":importlib.util.find_spec("faster_whisper") is not None,
            "classification_disponible":importlib.util.find_spec("tensorflow_hub") is not None,
            "voix":len(store.list()),"mode":"analyse d'enregistrement","model_status":"chargement à la demande"}

@app.get("/api/personnes",response_model=list[Profile])
def lister():
    return store.list()

@app.post("/api/personnes")
def ajouter(nom: str=Form(...),audio: UploadFile=File(...)):
    nom = nom.strip()
    if not nom or len(nom)>40:
        raise HTTPException(400,"Nom requis, 40 caractères maximum.")
    wav = decode(audio)
    try:
        regions, _ = speech_regions(wav)
        speech = np.concatenate([wav[int(a*16000):int(b*16000)] for a,b in regions]) if regions else np.array([],dtype=np.float32)
        if len(speech)<48000:
            raise ValueError("Au moins 3 secondes de parole requises ; enregistrez 10 à 15 secondes.")
        vector = embed(speech)
        store.merge({nom:{"echantillons":[vector.tolist()]}})
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except Exception as exc:
        log.exception("Enrollment failed")
        raise HTTPException(503,"Modèle vocal indisponible ; vérifier Resemblyzer, faster-whisper (VAD) et leurs dépendances.") from exc
    return {"nom":nom,"secondes":len(speech)/16000,"personnes":store.list()}

@app.delete("/api/personnes/{nom}",response_model=list[Profile])
def supprimer(nom: str):
    with store.lock:
        if nom not in store.voices:
            raise HTTPException(404,"Profil introuvable.")
        store.save({n:v for n,v in store.voices.items() if n!=nom})
    return store.list()

@app.get("/api/voix/export")
def exporter():
    with store.lock:
        return Response(json.dumps(store.voices,ensure_ascii=False),media_type="application/json",
                        headers={"Content-Disposition":'attachment; filename="voices.json"'})

@app.post("/api/voix/import",response_model=list[Profile])
def importer(fichier: UploadFile=File(...)):
    try:
        store.merge(json.loads(read_upload(fichier,2*1024*1024).decode("utf-8")))
    except (ValueError,TypeError,KeyError) as exc:
        raise HTTPException(400,"Fichier de profils invalide : "+str(exc)) from exc
    return store.list()

@app.post("/api/analyse",response_model=AnalysisResult)
def analyser(audio: UploadFile=File(...),options: AnalysisOptions=Depends(analysis_options)):
    if not work_lock.acquire(blocking=False):
        raise HTTPException(409,"Une analyse est déjà en cours.")
    try:
        wav = decode(audio)
        if len(wav)<8000:
            raise HTTPException(400,"Enregistrement trop court (0,5 seconde minimum).")
        result = analyse(wav,store,options)
        result["id"] = str(uuid.uuid4())
        validated = AnalysisResult(**result).model_dump()
        with result_lock:
            results[result["id"]] = validated
            while len(results)>10:
                results.popitem(last=False)
        return validated
    finally:
        work_lock.release()

@app.get("/api/sessions")
def sessions():
    with result_lock:
        return [{"id":r["id"],"date":r["date"],"duree":r["duree"]} for r in reversed(results.values())]

def get_result(key):
    with result_lock:
        if key not in results:
            raise HTTPException(404,"Séance expirée ou introuvable (historique en mémoire).")
        return results[key]

@app.get("/api/sessions/{key}",response_model=AnalysisResult)
def session(key: str):
    return get_result(key)

@app.delete("/api/sessions/{key}")
def delete_session(key: str):
    with result_lock:
        get_result(key)
        del results[key]
    return {"deleted":True}

@app.get("/api/sessions/{key}/export/{format}")
def export_result(key: str,format: Literal["json","csv","txt","pdf"]):
    from services.reports import export
    try:
        content, mime = export(get_result(key),format)
    except ImportError as exc:
        raise HTTPException(503,"Dépendances PDF manquantes.") from exc
    return Response(content,media_type=mime,headers={"Content-Disposition":f'attachment; filename="voicescope-{key}.{format}"'})

DIST = BASE/"frontend"/"dist"
if DIST.exists():
    app.mount("/",StaticFiles(directory=DIST,html=True),name="ui")
