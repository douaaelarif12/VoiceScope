import io
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
import server
from services.speakers import ProfileStore
from services import pipeline
from test_audio import wav_bytes

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"store",ProfileStore(tmp_path/"voices.json"))
    server.results.clear()
    with TestClient(server.app) as c: yield c

def analyze(client,**options):
    return client.post('/api/analyse',files={'audio':('test.wav',wav_bytes(np.zeros(16000)))},data={'stt':'false','classification':'false',**options})

def test_silence_api_and_exports(client):
    r=analyze(client)
    assert r.status_code==200,r.text
    data=r.json()
    assert data['segments']==[] and data['statistics']==[]
    assert data['acoustics']['dbfs']==-120
    assert data['vad']=='silence'
    for kind,mime in [('json','application/json'),('csv','text/csv'),('txt','text/plain'),('pdf','application/pdf')]:
        export=client.get(f'/api/sessions/{data["id"]}/export/{kind}')
        assert export.status_code==200,export.text[:500]
        assert export.headers['content-type'].startswith(mime)
        if kind=='pdf': assert export.content.startswith(b'%PDF')
        if kind=='json':assert export.json()==data
    assert len(client.get('/api/sessions').json())==1
    assert client.delete(f'/api/sessions/{data["id"]}').status_code==200
    assert client.get(f'/api/sessions/{data["id"]}').status_code==404

@pytest.mark.parametrize('options',[{'fenetre':0},{'modele':'../../arbitrary'},{'langue':'xx'},{'seuil':2},{'moderate_dbfs':-10,'high_dbfs':-30},{'seuil':'NaN'}])
def test_invalid_options(client,options):
    assert analyze(client,**options).status_code==422

@pytest.mark.parametrize('raw',[b'',b'bad file',wav_bytes(np.zeros(100))])
def test_invalid_upload(client,raw):
    assert client.post('/api/analyse',files={'audio':('x.wav',raw)}).status_code==400

def test_security_and_schema(client):
    assert client.get('/api/etat',headers={'origin':'https://evil.example'}).status_code==403
    assert client.get('/api/etat',headers={'host':'evil.example'}).status_code==400
    assert client.post('/api/analyse',headers={'content-length':str(40*1024*1024)}).status_code==413
    schema=client.get('/openapi.json').json()
    assert 'AnalysisResult' in schema['components']['schemas']

def test_profiles_import_delete(client):
    profile={'A':{'echantillons':[[1.]+[0.]*255]}}
    r=client.post('/api/voix/import',files={'fichier':('voices.json',json.dumps(profile))})
    assert r.status_code==200
    assert client.get('/api/voix/export').json()['A']['echantillons']==profile['A']['echantillons']
    assert client.delete('/api/personnes/A').status_code==200
    assert client.delete('/api/personnes/A').status_code==404

def test_pipeline_mixed_transcript_and_statistics(client,monkeypatch):
    monkeypatch.setattr(pipeline.vad,'speech_regions',lambda w:([(0.,2.),(2.,4.)],'mock'))
    monkeypatch.setattr(pipeline.transcription,'transcribe',lambda *a:([{'debut':0.,'fin':4.,'texte':'Bonjour à tous'}],'fr'))
    names=iter(['A','B'])
    monkeypatch.setattr(pipeline.speakers,'identify',lambda *a:{'locuteur':next(names),'raison':None,'scores':{'A':.8,'B':.5}})
    r=client.post('/api/analyse',files={'audio':('x.wav',wav_bytes(np.ones(64000)*.1))},data={'classification':'false'})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['transcriptions'][0]['locuteur']=='Indéterminé'
    assert sum(s['secondes'] for s in data['statistics'])==4
    assert sum(s['participation'] for s in data['statistics'])==100

def test_missing_models_degrade_explicitly(client,monkeypatch):
    def fail(*a):raise ImportError('missing')
    monkeypatch.setattr(pipeline.vad,'speech_regions',fail)
    monkeypatch.setattr(pipeline.transcription,'transcribe',fail)
    monkeypatch.setattr(pipeline.sound_classifier,'classify',fail)
    r=client.post('/api/analyse',files={'audio':('x.wav',wav_bytes(np.ones(16000)*.1))})
    assert r.status_code==200
    assert len(r.json()['warnings'])==3
    assert r.json()['segments']==[]

def test_csv_injection():
    from services.reports import csv_safe
    assert csv_safe('=HYPERLINK("evil")').startswith("'")
    assert csv_safe('  +formula').startswith("'")

def test_history_bounded(client):
    ids=[analyze(client).json()['id'] for _ in range(11)]
    assert len(client.get('/api/sessions').json())==10
    assert client.get('/api/sessions/'+ids[0]).status_code==404

def test_enrollment_rejects_non_speech(client,monkeypatch):
    monkeypatch.setattr(server,'speech_regions',lambda wav:([],'silero'))
    r=client.post('/api/personnes',data={'nom':'A'},files={'audio':('noise.wav',wav_bytes(np.ones(64000)*.1))})
    assert r.status_code==400
    assert client.get('/api/personnes').json()==[]
