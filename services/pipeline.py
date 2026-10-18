import math
import time
from datetime import datetime, timezone
from collections import defaultdict
from .acoustics import SR, analyse_frequency, alerts, dbfs
from . import speakers, transcription, vad, sound_classifier


def analyse(wav, store, options):
    started = time.perf_counter()
    acoustic = analyse_frequency(wav)
    duration = len(wav)/SR
    warnings, transcript, detected = [], [], None
    try:
        regions, vad_method = vad.speech_regions(wav)
    except Exception:
        regions, vad_method = [], "indisponible"
        warnings.append("VAD indisponible : aucun temps de parole estimé sans détection vocale.")
    if options.stt and acoustic["dbfs"] > -75:
        try:
            transcript, detected = transcription.transcribe(
                wav, options.modele, options.langue, regions=regions
            )
        except Exception:
            warnings.append("Transcription indisponible : vérifier faster-whisper et le téléchargement du modèle.")
    cents = store.centroids()
    rows = []
    for a,b in regions:
        for start in range(int(a*SR), int(b*SR), int(options.fenetre*SR)):
            end = min(start+int(options.fenetre*SR),int(b*SR))
            try:
                identity = speakers.identify(wav[start:end], cents, options.seuil, options.ecart)
            except Exception:
                identity = {"locuteur":"Indéterminé", "raison":"modèle vocal indisponible ou parole insuffisante", "scores":None}
                if "Reconnaissance vocale partiellement indisponible." not in warnings:
                    warnings.append("Reconnaissance vocale partiellement indisponible.")
            rows.append({"debut":start/SR,"fin":end/SR,"texte":"", "dbfs":dbfs(wav[start:end]), **identity})
    for item in transcript:
        item["debut"] = max(0.,min(duration,item["debut"]))
        item["fin"] = max(item["debut"],min(duration,item["fin"]))
        overlaps = [r for r in rows if r["fin"]>item["debut"] and r["debut"]<item["fin"]]
        names = {r["locuteur"] for r in overlaps}
        coverage = sum(max(0,min(r["fin"],item["fin"])-max(r["debut"],item["debut"])) for r in overlaps)
        stable = len(names)==1 and coverage >= .5*(item["fin"]-item["debut"])
        item["locuteur"] = next(iter(names)) if stable else "Indéterminé"
        item["raison"] = ("attribution estimée : chevauchement non vérifiable sur les segments courts" if any(r["raison"] for r in overlaps) else None) if stable and item["locuteur"] not in ("Inconnu","Indéterminé") else "attribution incertaine, parole mixte ou insuffisante"
        item["scores"] = overlaps[0]["scores"] if stable and len(overlaps)==1 else None
        item["dbfs"] = dbfs(wav[int(item["debut"]*SR):int(item["fin"]*SR)])
    statistics = defaultdict(lambda:{"secondes":0.,"prises":0,"energie":0.,"pic_dbfs":-120.})
    previous = None
    for r in rows:
        name = r["locuteur"]
        seconds = r["fin"]-r["debut"]
        statistics[name]["secondes"] += seconds
        # dBFS is logarithmic: compare linear power, then convert back to dBFS.
        statistics[name]["energie"] += seconds * (10 ** (r["dbfs"] / 10))
        statistics[name]["pic_dbfs"] = max(statistics[name]["pic_dbfs"], r["dbfs"])
        if previous is None or previous["locuteur"]!=name or r["debut"]-previous["fin"]>.3:
            statistics[name]["prises"] += 1
        previous = r
    total = sum(v["secondes"] for v in statistics.values())
    total_energy = sum(v["energie"] for v in statistics.values())
    stats = []
    for name, value in statistics.items():
        avg_dbfs = 10 * math.log10(max(value["energie"] / max(value["secondes"], 1e-9), 1e-12))
        stats.append({"nom":name,"secondes":value["secondes"],"prises":value["prises"],
                      "participation":100*value["secondes"]/total if total else 0,
                      "niveau_moyen_dbfs":avg_dbfs,
                      "pic_dbfs":value["pic_dbfs"],
                      "part_bruit":100*value["energie"]/total_energy if total_energy else 0})
    known_stats = [s for s in stats if s["nom"] not in ("Inconnu", "Indéterminé")]
    bruit_principal = max(known_stats, key=lambda s: s["part_bruit"])["nom"] if known_stats else None
    events, classifier = [], "désactivé"
    if options.classification:
        try:
            events = sound_classifier.classify(wav, options.sound_threshold)
            classifier = "YAMNet"
        except Exception:
            classifier = "indisponible"
            warnings.append("Classification indisponible : installer les dépendances YAMNet et rendre le modèle accessible.")
    return {"date":datetime.now(timezone.utc).isoformat(), "duree":duration,
            "langue":detected,"stt":detected is not None,"avertissement":" ".join(warnings) or None,
            "warnings":warnings,"segments":rows,"transcriptions":transcript,
            "niveaux":acoustic["niveaux"],"acoustics":acoustic,"statistics":stats,
            "events":events,"alerts":alerts(acoustic["niveaux"], options.moderate_dbfs, options.high_dbfs, options.alert_seconds),
            "locuteur_bruit_principal":bruit_principal,
            "options":options.model_dump(),"profiles":store.list(),"vad":vad_method,"classifier":classifier,
            "processing_seconds":time.perf_counter()-started,
            "limitations":["Similarités cosinus non calibrées.","dBFS numériques : aucune mesure dB SPL.",
                            "La voix la plus sonore est une estimation basée sur l'énergie des segments attribués ; un bruit non vocal reste classé séparément.",
                            "Temps de parole estimé par VAD, participation incluant les voix inconnues."]}
