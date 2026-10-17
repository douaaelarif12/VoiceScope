"""Exports use the server's immutable analysis snapshot."""
import csv
import io
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape


def csv_safe(value):
    text = str(value if value is not None else "")
    return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text


def export(result, format):
    if format == "json":
        return json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2).encode(), "application/json"
    if format == "txt":
        lines = ["VoiceScope AI - Transcription", result["date"], *result["warnings"], ""]
        lines += [f'{s["locuteur"]} [{s["debut"]:.2f} - {s["fin"]:.2f} s]'+
                  (f' ({s["raison"]})' if s["raison"] else '')+f'\n{s["texte"]}\n' for s in result["transcriptions"]]
        return "\n".join(lines).encode("utf-8"), "text/plain; charset=utf-8"
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream,delimiter=";")
        writer.writerow(["type","debut_s","fin_s","locuteur_ou_categorie","texte","dbfs","scores","observation"])
        for kind, rows in (("parole",result["segments"]),("transcription",result["transcriptions"]),("son",result["events"]),("alerte",result["alerts"])):
            for s in rows:
                writer.writerow([kind,s["debut"],s["fin"],csv_safe(s.get("locuteur",s.get("categorie",""))),
                                 csv_safe(s.get("texte","")),s.get("dbfs",s.get("seuil_dbfs","")),
                                 csv_safe(json.dumps(s.get("scores",s.get("score","")),ensure_ascii=False)),csv_safe(s.get("raison",""))])
        return ("\ufeff"+stream.getvalue()).encode("utf-8"), "text/csv; charset=utf-8"
    if format != "pdf":
        raise ValueError("Format inconnu")
    return pdf(result), "application/pdf"


def pdf(result):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.graphics.shapes import Drawing, PolyLine, Line, String, Rect
    candidates = [os.getenv("VOICESCOPE_PDF_FONT",""),"C:/Windows/Fonts/arial.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    font = next((p for p in candidates if p and Path(p).is_file()),None)
    if not font:
        raise ImportError("Police Unicode manquante : définir VOICESCOPE_PDF_FONT.")
    # Registration is idempotent. No personal content is written to temporary files.
    pdfmetrics.registerFont(TTFont("VoiceScope",font))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="VS",fontName="VoiceScope",fontSize=9,leading=14,textColor=colors.HexColor("#172238"),spaceAfter=7))
    styles.add(ParagraphStyle(name="VSH",parent=styles["VS"],fontSize=16,leading=22,spaceBefore=15,spaceAfter=12,keepWithNext=True))
    def text(value):
        value = str(value)
        if any("\u0600"<=c<="\u06ff" for c in value):
            import arabic_reshaper
            from bidi.algorithm import get_display
            value = get_display(arabic_reshaper.reshape(value))
        return escape(value).replace("\n","<br/>")
    def p(value,heading=False):
        return Paragraph(text(value),styles["VSH" if heading else "VS"])
    def chart(data,x,y,title):
        drawing = Drawing(480,170)
        drawing.add(Rect(0,0,480,170,fillColor=colors.HexColor("#f0f4fb"),strokeColor=None))
        drawing.add(String(14,153,title,fontName="VoiceScope",fontSize=9))
        if data:
            lo=min(float(v[y]) for v in data); hi=max(float(v[y]) for v in data)
            xmin=min(v[x] for v in data); xmax=max(v[x] for v in data)
            points=[]
            for v in data:
                points.extend([42+(v[x]-xmin)/max(xmax-xmin,1e-9)*420,30+(v[y]-lo)/max(hi-lo,1e-9)*105])
            if len(points)>=4:
                drawing.add(PolyLine(points,strokeColor=colors.HexColor("#6366f1"),strokeWidth=.8))
            drawing.add(String(8,32,f"{lo:.1f}",fontName="VoiceScope",fontSize=7))
            drawing.add(String(8,130,f"{hi:.1f}",fontName="VoiceScope",fontSize=7))
            drawing.add(String(42,12,f"{xmin:.1f}",fontName="VoiceScope",fontSize=7))
            drawing.add(String(425,12,f"{xmax:.1f}",fontName="VoiceScope",fontSize=7))
        return drawing
    story=[p("VoiceScope AI",True),p("Rapport d'analyse d'enregistrement"),p(f'Date UTC : {result["date"]} | Durée : {result["duree"]:.2f} s'),
           p(f'VAD : {result["vad"]} | Classification : {result["classifier"]} | Traitement : {result["processing_seconds"]:.2f} s'),
           p("Mesures acoustiques",True)]
    a=result["acoustics"]
    def frequency(value):
        return f"{value:.2f} Hz" if value is not None else "non définie (silence)"
    story += [p(f'Niveau global : {a["dbfs"]:.2f} dBFS | RMS : {a["rms"]:.5f}'),
              p(f'Fréquence dominante : {frequency(a["dominant_hz"])} | Centroïde : {frequency(a["centroid_hz"])}'),
              chart(result["niveaux"],"t","dbfs","Niveau numérique (dBFS) / temps (s)"),Spacer(1,12),
              chart(a["spectrum"],"hz","power_db","Densité spectrale Welch (dB/Hz) / fréquence (Hz)"),
              p("Signal et spectrogramme",True),
              chart(a["waveform"],"t","max","Enveloppe supérieure du signal / temps (s)")]
    import numpy as np
    from PIL import Image as PILImage
    heat=np.asarray(a["spectrogram"]["db"])
    intensity=np.clip((heat[::-1]+100)/100,0,1)
    rgb=np.stack([20+95*intensity,20+195*intensity,45+190*intensity],axis=-1).astype(np.uint8)
    buffer=io.BytesIO()
    PILImage.fromarray(rgb).save(buffer,format="PNG");buffer.seek(0)
    story += [Spacer(1,12),Image(buffer,width=480,height=180),
              p(f'STFT : fréquence verticale de 8 kHz (haut) à 0 Hz (bas) ; temps horizontal de 0 à {result["duree"]:.2f} s. Couleurs : -100 dB (sombre) à 0 dB (clair).'),
              p("Profils et participation",True)]
    story += [p(f'{v["nom"]} : {v["echantillons"]} échantillon(s)') for v in result["profiles"]]
    table=[[p("Locuteur"),p("Secondes"),p("Participation"),p("Prises")]]
    table += [[p(s["nom"]),p(f'{s["secondes"]:.2f}'),p(f'{s["participation"]:.1f} %'),p(s["prises"])] for s in result["statistics"]]
    t=Table(table,colWidths=[200,80,100,100],repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e0e7ff")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),.3,colors.lightgrey)]))
    story += [t,p("Transcriptions",True)]
    if not result["transcriptions"]:
        story.append(p("Aucune transcription disponible."))
    for s in result["transcriptions"]:
        story += [p(f'{s["debut"]:.2f} - {s["fin"]:.2f} s | {s["locuteur"]}'),p(s["texte"])]
        if s["raison"]:
            story.append(p(s["raison"]))
    story.append(p("Timeline et similarités",True))
    for s in result["segments"]:
        story.append(p(f'{s["debut"]:.2f} - {s["fin"]:.2f} s | {s["locuteur"]} | '+str(s["scores"] or s["raison"])))
    story.append(p("Classification sonore",True))
    if not result["events"]:
        story.append(p("Aucune classification disponible."))
    for e in result["events"]:
        story.append(p(f'{e["debut"]:.2f} - {e["fin"]:.2f} s | {e["categorie"]} | score {e["score"]:.3f}'))
    story.append(p("Alertes acoustiques",True))
    story.append(p(f'Seuil orange : {result["options"]["moderate_dbfs"]} dBFS ; rouge : {result["options"]["high_dbfs"]} dBFS ; durée consécutive : {result["options"]["alert_seconds"]} s.'))
    for e in result["alerts"]:
        story.append(p(f'Dépassement : {e["debut"]:.2f} - {e["fin"]:.2f} s'))
    if not result["alerts"]:
        story.append(p("Aucun dépassement durable du seuil configuré."))
    story.append(p("Limites et avertissements",True))
    story += [p(w) for w in result["warnings"]+result["limitations"]]
    def footer(canvas,doc):
        canvas.setFont("VoiceScope",8)
        canvas.drawString(42,25,"VoiceScope AI - Données locales - dBFS, pas dB SPL")
        canvas.drawRightString(550,25,str(doc.page))
    output=io.BytesIO()
    SimpleDocTemplate(output,rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=45,title="VoiceScope AI - Rapport").build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
