import asyncio
import os
import json
from services.privacy import protect,unprotect,PREFIX
from services.speakers import ProfileStore
from services.body_limit import BodyLimitMiddleware

def test_roundtrip_and_legacy():
    raw=b'{"private":"voice"}'
    value=protect(raw)
    assert unprotect(value)==raw
    assert unprotect(raw)==raw
    if os.name=='nt':
        assert value.startswith(PREFIX)
        assert b'private' not in value

def test_legacy_profiles_migrate(tmp_path):
    path=tmp_path/'voices.json'
    data={'A':{'echantillons':[[1.]+[0.]*255]}}
    path.write_text(json.dumps(data),encoding='utf-8')
    store=ProfileStore(path);store.load();store.save(store.voices)
    store.load()
    assert store.list()[0]['nom']=='A'
    if os.name=='nt':assert path.read_bytes().startswith(PREFIX)

def test_chunked_size_limit():
    messages=iter([{'type':'http.request','body':b'123','more_body':True},{'type':'http.request','body':b'456','more_body':False}])
    sent=[]
    async def receive():return next(messages)
    async def send(message):sent.append(message)
    async def app(*args):raise AssertionError('oversized body must never reach parser')
    asyncio.run(BodyLimitMiddleware(app,4)({'type':'http','method':'POST'},receive,send))
    assert sent[0]['status']==413
