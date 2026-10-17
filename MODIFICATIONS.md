# Fichiers et fonctionnalités livrés

Le projet a été extrait de l'archive fournie dans `VoiceScope-main`. L'archive originale n'a pas été modifiée. FastAPI, React/Vite, Resemblyzer, faster-whisper, les routes historiques de profils et l'enregistrement navigateur ont été conservés et réorganisés.

## Fichiers existants modifiés

| Fichier | Modification |
|---|---|
| `server.py` | Services séparés, validation, réponses typées d'analyse, profils, historique mémoire, exports, limites d'upload et protection locale |
| `requirements.txt` | Dépendances du socle acoustique/API/PDF |
| `lancer.bat` | Environnement virtuel prioritaire et écoute loopback explicite |
| `.gitignore` | Exclusion des profils, environnements, caches, dépendances et sorties de tests |
| `LISEZMOI.md` | Orientation vers le guide complet et le bilan de validation |
| `frontend/package.json`, `frontend/package-lock.json` | Lucide, Recharts, react-is, Vite actualisé et Prettier |
| `frontend/index.html` | Titre VoiceScope AI |
| `frontend/vite.config.js` | Configuration existante conservée, formatage |
| `frontend/src/App.jsx` | Sept sections, gestion des profils, analyse, statistiques, alertes, exports, paramètres persistants, états d'interface |
| `frontend/src/api.js` | Services API, historique et téléchargement des quatre formats |
| `frontend/src/AudioInput.jsx` | Capture existante, arrêt automatique, libération des ressources, nettoyage au changement de page |
| `frontend/src/audio.js` | Conversion existante, limites de taille et durée avant rééchantillonnage |
| `frontend/src/styles.css` | Identité dark, sidebar, responsive, clavier, graphiques et conversations |
| `frontend/src/charts.jsx` | Composants historiques conservés, formatage ; remplacés visuellement par `visuals.jsx` |
| `frontend/dist/` | Interface compilée actualisée |

## Nouveaux fichiers

- `schemas.py` : contrats Pydantic et contraintes des options.
- `services/__init__.py`, `acoustics.py`, `speakers.py`, `transcription.py`, `vad.py`, `sound_classifier.py`, `pipeline.py`, `reports.py`, `privacy.py`, `body_limit.py` : traitements séparés, sécurité et exports.
- `frontend/src/visuals.jsx` : graphiques Recharts, spectrogramme canvas explorables à la souris et au clavier.
- `requirements-ai.txt`, `requirements-yamnet.txt`, `requirements-dev.txt`, `constraints-tested.txt`, `.env.example` : installation et configuration documentées.
- `tests/test_audio.py`, `test_api.py`, `test_models_contracts.py`, `test_privacy.py` : 37 cas automatisés.
- `scripts/evaluate.py`, `smoke_models.py`, `smoke_e2e.py` : évaluation sur corpus et vérifications réelles reproductibles.
- `README.md`, `VALIDATION.md`, `MODIFICATIONS.md` : installation, fonctionnement, protocole, preuves et limitations.
- `.gitignore` à la racine de l'espace de travail : exclusion de l'environnement virtuel utilisé ici.

Les dossiers `tmp/` et `output/` contiennent uniquement les fichiers de validation et les artefacts locaux ; ils ne sont pas injectés dans l'application. Aucun profil de test n'est conservé dans `data`.
