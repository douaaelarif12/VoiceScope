import numpy as np
import pytest
from services import sound_classifier
from scripts.evaluate import edit_distance, macro_f1

def test_classifier_labels_unknown_and_timestamps(monkeypatch):
    class Scores:
        def numpy(self):return np.array([[.1,.9],[.2,.1]])
    monkeypatch.setattr(sound_classifier,"_model",lambda x:(Scores(),None,None))
    monkeypatch.setattr(sound_classifier,"_labels",["Speech","Clapping"])
    events=sound_classifier.classify(np.zeros(16000),.3)
    assert [e["categorie"] for e in events]==["Clapping","Inconnu"]
    assert events[0]["fin"]==events[1]["debut"]==.48
    assert events[-1]["fin"]==1
    assert events[0]["score"]==.9

def test_evaluation_math():
    assert edit_distance("un deux trois".split(),"un quatre trois cinq".split())==2
    assert edit_distance([],['a'])==1
    assert macro_f1([('A','A'),('B','A')])['macro']==pytest.approx(1/3)
    assert macro_f1([])['macro'] is None
