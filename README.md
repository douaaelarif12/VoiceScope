# VoiceScope AI

Plateforme locale d’analyse d’enregistrements de classe, construite à partir du projet FastAPI + React/Vite fourni. Aucun résultat de démonstration n’est injecté dans l’application. Les mesures, graphiques et exports proviennent du même résultat serveur.

## Installation Windows

Utiliser **Python 3.12 64 bits** (3.11 possible, non vérifié ici) et Node.js **22.12+**. Python 3.14 n’est pas la cible de cette configuration ML. PowerShell, depuis `VoiceScope-main` :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
.\.venv\Scripts\python.exe -m pip install resemblyzer==0.1.4 --no-deps
.\.venv\Scripts\python.exe -m pip install -r requirements-yamnet.txt
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Ouvrir http://localhost:8000. `lancer.bat` utilise l’environnement virtuel du projet ou celui du dossier parent. Dans l’espace livré ici, les dépendances sont dans `..\.venv` (Python 3.12).

**Pourquoi deux étapes pour Resemblyzer ?** Sa dépendance historique `webrtcvad` tente de compiler du C++ sous Windows. `requirements-ai.txt` installe explicitement ses dépendances et la distribution compatible `webrtcvad-wheels`, puis `--no-deps` évite de réinstaller l’ancienne distribution. Ne pas exécuter simplement `pip install resemblyzer` sur une machine sans compilateur.

Pour un fonctionnement acoustique sans modèles IA : `pip install -r requirements.txt`. Désactiver transcription et classification dans Settings ; l’absence de VAD ou de modèle vocal sera indiquée sans inventer de résultat. La présence d’un module dans Settings signifie « installé », pas « poids chargés ».

Les poids Whisper et YAMNet sont téléchargés à la première utilisation. Préparer une analyse en ligne avant la soutenance ; le cache permet ensuite le fonctionnement hors ligne. Resemblyzer inclut ses poids. Les téléchargements nécessitent du réseau et plusieurs Go libres pour les dépendances. CPU natif Windows, aucun GPU requis.

`constraints-tested.txt` enregistre les versions effectivement utilisées lors des vérifications. Pour les reproduire, ajouter `-c constraints-tested.txt` aux commandes `pip install -r ...`. TensorFlow Hub 0.16 utilise encore `pkg_resources` : `requirements-yamnet.txt` impose donc `setuptools<81`. Les avertissements de dépréciation TensorFlow Hub n'empêchent pas l'inférence testée.

### Développement

Terminal backend :

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

Second terminal, dans `frontend` :

```powershell
npm run dev
```

Vite écoute sur http://localhost:5173 et transmet `/api` à FastAPI. Pour utiliser l’interface servie directement par Python, refaire `npm run build` après chaque modification React.

## Parcours de démonstration

1. **Voice Profiles** : enregistrer les trois personnes, idéalement 3 échantillons distincts de 10–15 secondes par personne. Le minimum est 3 secondes de parole détectée par Silero par ajout (faster-whisper requis pour le VAD). Limite de 30 échantillons par profil. Même nom = nouvel échantillon ; noms comparés sans tenir compte de la casse.
2. **Settings** : langue `fr`, `en`, `ar`, `es` ou `auto`, Whisper `tiny`, `base` ou `small`, similarité/marge, score YAMNet et seuils numériques. Ces paramètres persistants dans le navigateur ne changent pas rétroactivement les analyses.
3. **Audio Analysis** : importer ou enregistrer (maximum 5 minutes et 32 Mio). Le navigateur convertit les formats qu’il sait décoder en WAV mono 16 kHz. L’API décode les formats pris en charge par libsndfile et refuse les fichiers invalides.
4. Lancer l’analyse après l’enregistrement. Les modèles ne sont pas utilisés en temps réel. Le vumètre pendant la capture est uniquement un indicateur de signal micro.
5. **Overview** : mesures, graphiques, sélection temporelle et feu tricolore. Un dépassement durable est compté lorsque plusieurs fenêtres de 250 ms dépassent consécutivement le seuil rouge pendant la durée configurée.
6. **Transcription / Analytics** : phrases horodatées, attribution, similarités, temps de parole, prises, événements sonores et historique.
7. **Reports** : télécharger TXT, CSV, JSON ou PDF. Exporter avant d’arrêter le serveur : l’historique conserve uniquement les dix dernières analyses en mémoire. Les profils restent sur disque.

## Architecture et compatibilité

- `server.py` : mêmes routes historiques pour profils/import/export/analyse, validation, gestion locale et historique borné.
- `schemas.py` : modèles Pydantic, paramètres et réponse d’analyse détaillée ; documentation interactive `/docs` et OpenAPI `/openapi.json`.
- `services/acoustics.py` : décodage borné, conversion mono, rééchantillonnage polyphase, FFT, centroïde, RMS, dBFS, Welch, STFT, waveform, alertes.
- `services/speakers.py` : Resemblyzer, plusieurs empreintes par profil, score combinant les meilleurs échantillons et leur centroïde, contrôle des sous-fenêtres, persistance atomique.
- `services/transcription.py` : faster-whisper CPU int8 avec VAD et horodatages ; un seul modèle Whisper en cache.
- `services/vad.py` : Silero ONNX livré avec faster-whisper, sans deuxième framework VAD.
- `services/sound_classifier.py` : YAMNet et libellés AudioSet réels, seuil pour `Inconnu`.
- `services/pipeline.py` : orchestration, statistiques à partir d’intervalles VAD disjoints, attribution prudente des phrases.
- `services/reports.py` : exports et PDF Unicode avec graphiques, limites et avertissements.
- `frontend/src/App.jsx` : sept sections ; `AudioInput.jsx` capture le microphone en PCM avant de créer un WAV mono 16 kHz, sans dépendre du codec MediaRecorder ; `audio.js` convertit aussi les fichiers importés ; `visuals.jsx` apporte Recharts et spectrogramme interactif ; `api.js` centralise les appels.
- `frontend/src/charts.jsx` : anciens composants SVG conservés, non utilisés par le nouveau dashboard.
- `scripts/evaluate.py` : évaluation sur corpus annoté ; `scripts/smoke_models.py` : essais explicites des modèles sur fichiers réels dans `tmp/audio`.

Les champs `duree`, `langue`, `stt`, `avertissement`, `segments`, `niveaux` restent présents. `segments` décrit maintenant la timeline vocale VAD ; les phrases sont dans `transcriptions`. Les clients qui lisaient les phrases dans `segments[].texte` doivent migrer.

### API

| Route | Usage |
|---|---|
| GET `/api/etat` | Présence des dépendances |
| GET/POST `/api/personnes` | Profils ; ajout multipart `nom`, `audio` |
| DELETE `/api/personnes/{nom}` | Suppression d’un profil |
| GET `/api/voix/export` | Sauvegarde des empreintes JSON |
| POST `/api/voix/import` | Fusion validée, multipart `fichier` |
| POST `/api/analyse` | Audio + options multipart, résultat structuré |
| GET `/api/sessions` | Historique en mémoire |
| GET/DELETE `/api/sessions/{id}` | Lecture / suppression |
| GET `/api/sessions/{id}/export/{format}` | `txt`, `csv`, `json`, `pdf` |

Les réponses 400/413 signalent un audio invalide/trop gros ; 422 des paramètres incorrects ; 409 une analyse déjà en cours ; 503 un modèle d’enrôlement ou l’export PDF indisponible. L’analyse peut retourner 200 avec `warnings` lorsque seules certaines capacités IA échouent : les mesures acoustiques restent disponibles.

## Interprétation scientifique

- **dBFS** = `20 log10(RMS)`, avec plancher d’affichage à -120. Un sinus d’amplitude 0,5 vaut environ -9,03 dBFS. Ce n’est pas le dB SPL et aucune exposition acoustique réelle n’est déduite.
- FFT Hann sur l’ensemble du signal, maximum spectral et centroïde pondéré en amplitude. Fréquence dominante et centroïde valent `null` sur le silence. Les fréquences sont celles du signal ramené à 16 kHz, donc limitées à 8 kHz.
- Distribution affichée : densité spectrale de puissance Welch, en dB/Hz. STFT Hann de 512 échantillons, pas 256. Affichage borné à 240 colonnes en conservant les pics de chaque groupe ; enveloppe waveform limitée à 800 points.
- La similarité cosinus n’est **pas une probabilité calibrée**. Le score combine la meilleure correspondance parmi les empreintes du profil et son centroïde ; chaque capture de profil fournit une empreinte par fenêtre complète de trois secondes. Quand des profils sont disponibles, l’application attribue toujours le profil au score le plus élevé, même si le score est faible ou si plusieurs scores sont proches ; les seuils configurables servent à signaler les cas moins fiables, pas à bloquer l’attribution. Sans profil, ou lorsque le modèle ne peut pas calculer de similarité, aucun nom ne peut être déterminé.
- Les extraits vocaux ne sont jamais étendus dans les phrases voisines. Les sous-fenêtres servent à repérer des scores variables seulement lorsqu'au moins deux fenêtres complètes de 1,5 seconde sont disponibles. Les phrases qui traversent plusieurs segments sont attribuées au profil dont le score moyen pondéré par la durée est le plus élevé. Ce choix fournit un nom, pas une certitude.
- Pas de séparation de sources ni de détecteur spécialisé de chevauchement : un mélange peut recevoir le nom du profil le plus proche sans qu’il s’agisse forcément de l’unique personne qui parle. L’application ne garantit donc pas une diarisation parfaite en conversations simultanées.
- Temps de parole = estimation VAD ; les prises successives du même locuteur sans pause supérieure à 300 ms sont regroupées. Participation calculée parmi les régions vocales, y compris inconnues/indéterminées, sans compter deux fois les phrases.
- YAMNet : catégories du CSV embarqué dans le modèle, sans traduction inventée ni attribution causale à un meuble. `Knock`/`Thump`/`Scrape` ne prouvent pas un coup sur table ou une chaise. Scores non calibrés, catégorie `Inconnu` sous le seuil. Le modèle observe environ 0,96 s par fenêtre espacée de 0,48 s ; les intervalles de décision affichés ne se recouvrent pas. La dernière décision est prolongée jusqu’à la fin du fichier.
- Whisper peut produire des erreurs/hallucinations et sa qualité varie selon la langue et l’acoustique. Silero et l’exclusion des silences réduisent ces risques sans les supprimer.

## Confidentialité et limites de déploiement

Application **locale mono-utilisateur**, à démarrer uniquement sur `127.0.0.1`, un seul worker. Aucun service cloud ne reçoit les enregistrements. Les modèles peuvent télécharger leurs poids officiels. Pas d’authentification pour un usage réseau : ne pas exposer le port à Internet ni utiliser `0.0.0.0` sans ajouter authentification, HTTPS et protection des uploads au niveau du proxy.

Les fichiers audio ne sont pas archivés. FastAPI peut utiliser ses fichiers temporaires de téléversement, fermés à la fin de la requête. Les profils sont chiffrés au repos sous Windows avec **DPAPI, lié au compte Windows courant**, puis sauvegardés atomiquement. Le fichier `data/voices.json` conserve son nom historique mais contient une enveloppe chiffrée. Les anciens JSON restent lisibles et sont chiffrés à la prochaine sauvegarde. Un autre compte ne pourra pas les déchiffrer : utiliser l'export explicite pour les transférer. Sous POSIX, le stockage JSON reste non chiffré avec permissions privées. Conserver le dossier dans un emplacement privé, jamais partagé. Obtenir le consentement des participants et supprimer les profils après le projet. L'export JSON de profils est non chiffré et contient les empreintes, mais les rapports d'analyse n'en contiennent pas. JSON/CSV/PDF/TXT peuvent contenir les paroles : les conserver avec les mêmes précautions.

Noms d’hôtes et origines sont restreints à localhost ; tailles, durées, valeurs finies, modèles et imports sont validés. CSV protège les champs texte contre les formules. Les modifications de profils sont verrouillées et sauvegardées atomiquement. Une seule analyse est exécutée à la fois ; les inférences vocales et Whisper sont verrouillées.

`.env.example` documente les variables facultatives, **sans chargement automatique de `.env`**. Dans PowerShell, utiliser par exemple `$env:VOICESCOPE_DATA = "C:\MonDossierPrive\VoiceScope"`. `VOICESCOPE_PDF_FONT` peut pointer vers une police Unicode TTF (Arial détectée sous Windows ; DejaVu Sans sous Linux). L’arabe PDF utilise arabic-reshaper + python-bidi ; la mise en page de longs paragraphes arabes mérite une relecture humaine.

## Tests et évaluation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm ci
npm run build
npm audit
```

Tests : WAV/stéréo/rééchantillonnage, formats invalides/vides/non finis, durée, FFT/STFT/centroïde/RMS/dBFS, silence, alertes consécutives, inconnus/marge/mélange, import atomique de trois profils, paramètres API, historique, erreurs de modèles simulées, exports JSON/TXT/CSV/PDF et protection CSV. Les mocks ne démontrent pas la précision réelle des modèles. Voir `VALIDATION.md` pour les vérifications effectivement effectuées.

Pour mesurer la précision, préparer un corpus **indépendant des enregistrements d’enrôlement**, avec trois locuteurs connus et plusieurs inconnus, silences/bruits/chevauchements, langues et conditions de salle. Au moins plusieurs dizaines de clips par classe pour un premier bilan ; conserver un jeu distinct pour régler les seuils.

Créer un manifeste JSON (les chemins audio sont relatifs au manifeste) :

```json
[
  {"audio":"alice_test.wav", "speaker":"Alice", "text":"Bonjour à tous", "sound":"Speech"},
  {"audio":"applause.wav", "sound":"Clapping"}
]
```

Ces lignes sont un **exemple de format**, pas des mesures ni des fichiers livrés. Le nom de catégorie doit correspondre à la table réelle du modèle. Le script évalue les clips monolocuteurs et à catégorie dominante unique :

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py corpus/manifest.json --profiles data/voices.json --model base --language fr --output evaluation.json
```

Mesures : accuracy par clip, WER micro (casse normalisée, ponctuation conservée), macro-F1 et F1 par classe, temps moyen incluant le premier chargement. Les échecs sont consignés et les métriques sans données valent `null`, jamais un score fictif. Ne pas utiliser ce protocole monolabel pour prétendre mesurer la diarisation ou la détection temporelle multi-événements : annoter les intervalles et ajouter un protocole adapté dans ce cas.

## Sources des modèles

- Resemblyzer : https://github.com/resemble-ai/Resemblyzer
- faster-whisper / Silero intégré : https://github.com/SYSTRAN/faster-whisper
- YAMNet : https://www.tensorflow.org/hub/tutorials/yamnet
- Fenêtres YAMNet : https://www.tensorflow.org/tutorials/audio/transfer_learning_audio

Aucune accuracy, WER ou F1 sur les trois participants n’est annoncée sans corpus annoté. Docker n’est pas ajouté : le lancement Windows local est la cible de cette livraison.
