# Vérifications effectuées — 17 octobre 2026

## Résultat vérifiable

- **37 tests Python réussis**, dernière exécution : 8,85 s, Python 3.12 sous Windows. Commande : `python -m pytest -q -p no:cacheprovider --tb=short`.
- **Compilation Vite réussie**, sans avertissement de taille après séparation des graphiques : bundle principal 172,71 ko et graphiques différés 376,56 ko (tailles avant gzip).
- **Audit npm : 0 vulnérabilité signalée** lors de la dernière installation des dépendances.
- Interface réellement ouverte dans le navigateur, import d'un fichier WAV public, conversion navigateur, appel API, mesures, timeline, statistiques et historique vérifiés. Console navigateur : aucune erreur ni alerte React relevée lors de ce parcours.
- Affichage inspecté sur desktop et à 390 × 844 pour la page Settings. La capture `output/interface-finale.jpg` montre l'application prête à recevoir les profils. `output/dashboard.jpg` montre l'analyse acoustique réelle du fichier public de parole/sifflement.
- PDF rendus avec Poppler puis inspectés visuellement : graphiques, tableaux, pagination, français et court texte arabe de test. Rapport réel de validation disponible sous `output/pdf/validation-public-audio.pdf`.

## Tests automatisés

Les tests portent sur décodage WAV, stéréo/rééchantillonnage, fichiers vides/incompatibles/non finis/hors durée, sinus 1 kHz, FFT/STFT, centroïde, RMS/dBFS, silence, alertes consécutives, rejet d'inconnus et de profils ambigus, voix différentes simulées, fenêtres vocales suffisamment longues, imports atomiques, limite de trois profils, validation API, historique borné, erreurs de dépendances simulées, schémas OpenAPI, quatre exports, protection CSV, catégories YAMNet simulées et timestamps, calcul des métriques, migration des profils historiques, chiffrement DPAPI, limite des requêtes sans Content-Length et rejet d'un enrôlement non vocal.

Les tests utilisant des modèles simulés contrôlent la logique. Ils ne mesurent aucune précision IA.

## Modèles réellement exécutés

Fichiers publics du [tutoriel officiel YAMNet](https://www.tensorflow.org/hub/tutorials/yamnet) :

- `miaow_16k.wav` : Silero ne détecte aucune parole ; Whisper tiny renvoie un texte vide. YAMNet produit notamment `Cat`, `Animal`, `Caterwaul` et `Inconnu`.
- `speech_whistling2.wav` : Silero détecte de la parole ; Resemblyzer produit un vecteur de 256 dimensions ; Whisper tiny renvoie une transcription ; YAMNet produit `Speech`, `Whistle`, `Whistling` et ponctuellement `Bird`.

Le résultat `Bird` illustre une confusion réelle : ces essais ne prouvent pas la fiabilité sur des bruits de classe. Les scores ne sont pas calibrés. Les détails des essais sont conservés localement dans `tmp/model-smoke.json` et le script reproductible est `scripts/smoke_models.py`.

## Essai complet de l'API avec modèles réels

Entrée : [extrait public `jfk.flac` du dépôt Whisper](https://github.com/openai/whisper/blob/main/tests/jfk.flac), durée 11 s.

Le script `scripts/smoke_e2e.py` utilise un dossier de profils temporaire indépendant. Il ne crée aucun profil dans votre application courante.

1. Enrôlement sur les six premières secondes, avec 3,754 s de parole retenues par Silero : HTTP 200.
2. Sauvegarde chiffrée DPAPI et rechargement du profil : réussis.
3. Analyse complète avec Resemblyzer, Silero, Whisper tiny anglais et YAMNet : aucune capacité indisponible dans `warnings`.
4. 6,668 s estimées attribuées au profil de test ; 1,124 s restent inconnues. La phrase complète reste indéterminée puisqu'elle traverse ces attributions différentes.
5. Transcription obtenue : « And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country. »
6. Classification : `Speech` et `Inconnu`.
7. Exports JSON, CSV, TXT et PDF : HTTP 200, contenus non vides ; PDF d'environ 156 ko.
8. Temps d'analyse observé sur ce seul passage : **37,12 s**, incluant les chargements de modèles dans ce processus. Ce n'est ni une moyenne de performance ni une garantie de latence.

**Cet essai n'est pas un benchmark** : l'enrôlement recouvre une partie de l'audio analysé. Aucun taux d'accuracy, WER ou F1 n'en est déduit. Les résultats détaillés sont dans `tmp/e2e-summary.json` et `tmp/e2e-result.json`.

## Ce qui reste à vérifier avec les participants

- Précision sur les trois locuteurs réels, inconnus distincts et conditions acoustiques de la salle.
- Qualité de transcription française et arabe : les options sont implémentées, mais les essais vocaux réels effectués ici sont en anglais, avec Whisper tiny. Les modèles base/small ne sont pas validés ici.
- Reconnaissance des applaudissements, rires, frottements et coups avec un corpus réel de classe. Ne pas interpréter automatiquement une catégorie sonore comme une chaise ou une table.
- Microphone physique et autorisations navigateur : la capture existante a été conservée et sécurisée, mais aucun enregistrement du microphone utilisateur n'a été effectué.
- Chevauchement de voix : absence de séparation de sources. Les sous-fenêtres détectent certaines instabilités, pas tous les mélanges.
- Seuils de similarité et d'alerte à régler sur des enregistrements de validation distincts.
- Les mesures restent numériques en dBFS ; aucun niveau dB SPL n'est testé ou annoncé.

Le protocole et le script de mesure sont décrits dans `README.md`. Les métriques absentes restent `null`.

## Incidents résolus

- Installation Windows de `webrtcvad` nécessitant C++ : remplacée par `webrtcvad-wheels`, installation Resemblyzer sans réinstaller ses anciennes dépendances.
- TensorFlow Hub et suppression de `pkg_resources` : borne `setuptools>=77,<81` ajoutée et testée.
- Dépendance pair `react-is` ajoutée pour Recharts ; Vite mis à jour après l'audit initial.
- Veto vocal excessif causé par des queues de fenêtres trop courtes : comparaison uniquement de fenêtres complètes d'au moins 1,5 s, avertissement explicite sur les segments plus courts.
- Restrictions du bac à sable sur les dossiers temporaires, sockets et DPAPI : vérifications finales réalisées sous le compte Windows via les outils autorisés.
- Un contrôle automatique d'approbation a temporairement échoué sur une limite d'utilisation ; l'étape a ensuite été autorisée et exécutée. Aucun blocage d'installation restant.
