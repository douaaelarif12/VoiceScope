from typing import Literal
from pydantic import BaseModel, Field, model_validator

class AnalysisOptions(BaseModel):
    stt: bool = True
    modele: Literal["tiny","base","small"] = "base"
    langue: Literal["fr","en","ar","es","auto"] = "fr"
    fenetre: float = Field(3., ge=1, le=10)
    seuil: float = Field(.75,ge=0,le=1)
    ecart: float = Field(.05,ge=0,le=1)
    classification: bool = True
    sound_threshold: float = Field(.3,ge=0,le=1)
    moderate_dbfs: float = Field(-35,ge=-120,le=0)
    high_dbfs: float = Field(-20,ge=-120,le=0)
    alert_seconds: float = Field(3,ge=.25,le=60)

    @model_validator(mode="after")
    def thresholds(self):
        if self.moderate_dbfs >= self.high_dbfs:
            raise ValueError("Le seuil modéré doit être inférieur au seuil rouge.")
        return self

class Profile(BaseModel):
    nom: str
    echantillons: int
    ajoute: str | None = None

class Segment(BaseModel):
    debut: float
    fin: float
    texte: str
    dbfs: float
    locuteur: str
    raison: str | None
    scores: dict[str,float] | None

class Level(BaseModel):
    t: float
    fin: float
    dbfs: float

class AcousticData(BaseModel):
    dominant_hz: float | None
    centroid_hz: float | None
    rms: float
    dbfs: float
    waveform: list[dict[str,float]]
    spectrum: list[dict[str,float]]
    spectrogram: dict[str,list]
    niveaux: list[Level]
    sample_rate: int
    floor_dbfs: int

class Statistic(BaseModel):
    nom: str
    secondes: float
    prises: int
    participation: float

class SoundEvent(BaseModel):
    debut: float
    fin: float
    categorie: str
    score: float
    modele: str

class Alert(BaseModel):
    debut: float
    fin: float
    seuil_dbfs: float

class AnalysisResult(BaseModel):
    id: str
    date: str
    duree: float
    langue: str | None
    stt: bool
    avertissement: str | None
    warnings: list[str]
    segments: list[Segment]
    transcriptions: list[Segment]
    niveaux: list[Level]
    acoustics: AcousticData
    statistics: list[Statistic]
    events: list[SoundEvent]
    alerts: list[Alert]
    options: AnalysisOptions
    profiles: list[Profile]
    vad: str
    classifier: str
    processing_seconds: float
    limitations: list[str]
