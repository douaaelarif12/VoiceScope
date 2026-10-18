import { useEffect, useState, lazy, Suspense } from "react";
import {
  Activity,
  LayoutDashboard,
  Users,
  AudioLines,
  MessageSquare,
  ChartNoAxesCombined,
  FileDown,
  Settings,
  CalendarDays,
  Play,
  Trash2,
  ShieldCheck,
  ArrowUpRight,
} from "lucide-react";
import AudioInput from "./AudioInput.jsx";
import { api } from "./api.js";

const visual = (name) => {
  const View = lazy(() =>
    import("./visuals.jsx").then((module) => ({ default: module[name] })),
  );
  return (props) => (
    <Suspense fallback={<p role="status">Chargement du graphique…</p>}>
      <View {...props} />
    </Suspense>
  );
};
const SignalChart = visual("SignalChart"),
  Spectrogram = visual("Spectrogram"),
  Participation = visual("Participation"),
  Categories = visual("Categories");

const navigation = [
  ["Overview", LayoutDashboard],
  ["Voice Profiles", Users],
  ["Audio Analysis", AudioLines],
  ["Transcription", MessageSquare],
  ["Analytics", ChartNoAxesCombined],
  ["Reports", FileDown],
  ["Schedule", CalendarDays],
  ["Settings", Settings],
];
const defaults = {
  stt: true,
  modele: "base",
  langue: "fr",
  fenetre: 3,
  seuil: 0.68,
  ecart: 0.05,
  classification: true,
  sound_threshold: 0.3,
  moderate_dbfs: -35,
  high_dbfs: -20,
  alert_seconds: 3,
};
const clock = (v) =>
  `${String(Math.floor(v / 60)).padStart(2, "0")}:${(v % 60).toFixed(1).padStart(4, "0")}`;
const number = (v, unit = "", digits = 1) =>
  v == null ? "—" : `${v.toFixed(digits)}${unit}`;
const colors = ["#818cf8", "#22d3ee", "#34d399"];

export default function App() {
  const [page, setPage] = useState("Overview"),
    [status, setStatus] = useState(null),
    [people, setPeople] = useState([]);
  const [name, setName] = useState(""),
    [voice, setVoice] = useState(null),
    [audio, setAudio] = useState(null),
    [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(null),
    [history, setHistory] = useState([]),
    [selected, setSelected] = useState(0);
  const [schedule, setSchedule] = useState(() => {
    try { return JSON.parse(localStorage.getItem("voicescope-schedule") || "[]"); }
    catch { return []; }
  });
  const [selectedSchedule, setSelectedSchedule] = useState("");
  const [scheduleDraft, setScheduleDraft] = useState({
    professeur: "", classe: "", matiere: "", salle: "", semestre: "Semestre 1", semaine: "Toutes", jour: "Lundi", debut: "08:00", fin: "09:00",
  });
  const [options, setOptions] = useState(() => {
    try {
      return {
        ...defaults,
        ...JSON.parse(localStorage.getItem("voicescope-settings") || "{}"),
      };
    } catch {
      return defaults;
    }
  });
  const refresh = async () => {
    try {
      const [s, p, h] = await Promise.all([
        api.etat(),
        api.personnes(),
        api.sessions(),
      ]);
      setStatus(s);
      setPeople(p);
      setHistory(h);
    } catch (e) {
      setStatus(null);
      setNotice({ error: true, text: e.message });
    }
  };
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    localStorage.setItem("voicescope-settings", JSON.stringify(options));
  }, [options]);
  useEffect(() => {
    localStorage.setItem("voicescope-schedule", JSON.stringify(schedule));
  }, [schedule]);
  const run = async (action) => {
    setBusy(true);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setNotice({ error: true, text: e.message });
    } finally {
      setBusy(false);
    }
  };
  const analyse = () =>
    run(async () => {
      const context = schedule.find((s) => s.id === selectedSchedule);
      const r = await api.analyser(audio, {
        ...options,
        ...(context ? {
          professeur: context.professeur,
          classe: context.classe,
          matiere: context.matiere,
          salle: context.salle,
          seance: `${context.semestre} · ${context.semaine} · ${context.jour} ${context.debut}–${context.fin}`,
        } : {}),
      });
      setResult(r);
      setSelected(0);
      setPage("Overview");
      await refresh();
      setNotice({
        text: "Analyse terminée. Les capacités indisponibles sont signalées ci-dessous.",
      });
    });
  const add = () =>
    run(async () => {
      const r = await api.ajouter(name.trim(), voice);
      setPeople(r.personnes);
      setVoice(null);
      setNotice({ text: `Échantillon ajouté pour ${r.nom}.` });
    });
  const addSchedule = () => {
    if (!scheduleDraft.professeur.trim() || !scheduleDraft.classe.trim() || !scheduleDraft.matiere.trim()) return;
    setSchedule([...schedule, { ...scheduleDraft, id: crypto.randomUUID() }]);
    setScheduleDraft({ ...scheduleDraft, professeur: "", classe: "", matiere: "", salle: "" });
  };
  const a = result?.acoustics,
    frame = result?.niveaux[selected];
  const traffic = frame
    ? frame.dbfs >= result.options.high_dbfs
      ? "red"
      : frame.dbfs >= result.options.moderate_dbfs
        ? "orange"
        : "green"
    : "off";
  const dominantSpeaker = result?.statistics
    .filter((s) => !["Inconnu", "Indéterminé"].includes(s.nom))
    .sort((x, y) => y.secondes - x.secondes)[0]?.nom;
  const noiseLeader = result?.locuteur_bruit_principal;
  const empty = (
    <div className="empty">
      <AudioLines size={40} />
      <h2>Votre salle de classe, en perspective.</h2>
      <p>
        Importez ou enregistrez une séance pour explorer le son, les voix et les
        interventions.
      </p>
      <button className="btn primary" onClick={() => setPage("Audio Analysis")}>
        Analyser un enregistrement <ArrowUpRight size={16} />
      </button>
    </div>
  );
  const settings = (
    <section className="card">
      <h2>Paramètres d'analyse</h2>
      <p className="hint">
        Appliqués à la prochaine analyse. Les résultats existants conservent
        leurs paramètres.
      </p>
      <div className="settings-grid">
        <label className="field">
          Modèle Whisper
          <select
            value={options.modele}
            onChange={(e) => setOptions({ ...options, modele: e.target.value })}
          >
            {["tiny", "base", "small"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Langue
          <select
            value={options.langue}
            onChange={(e) => setOptions({ ...options, langue: e.target.value })}
          >
            {Object.entries({
              fr: "Français",
              en: "English",
              ar: "العربية",
              es: "Español",
              auto: "Automatique",
            }).map(([v, l]) => (
              <option value={v} key={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        {Object.entries({
          seuil: ["Similarité cosinus minimale", 0, 1, 0.01],
          ecart: ["Marge entre les deux profils", 0, 1, 0.01],
          fenetre: ["Fenêtre vocale (secondes)", 1, 10, 0.5],
          sound_threshold: ["Score YAMNet minimal", 0, 1, 0.05],
          moderate_dbfs: ["Seuil orange (dBFS)", -120, 0, 1],
          high_dbfs: ["Seuil rouge (dBFS)", -120, 0, 1],
          alert_seconds: ["Dépassement consécutif (secondes)", 0.25, 60, 0.25],
        }).map(([key, [label, min, max, step]]) => (
          <label className="field" key={key}>
            {label}
            <input
              type="number"
              min={min}
              max={max}
              step={step}
              value={options[key]}
              onChange={(e) =>
                setOptions({ ...options, [key]: Number(e.target.value) })
              }
            />
          </label>
        ))}
      </div>
      <label>
        <input
          type="checkbox"
          checked={options.stt}
          onChange={(e) => setOptions({ ...options, stt: e.target.checked })}
        />{" "}
        Transcription automatique
      </label>
      <label>
        <input
          type="checkbox"
          checked={options.classification}
          onChange={(e) =>
            setOptions({ ...options, classification: e.target.checked })
          }
        />{" "}
        Classification YAMNet
      </label>
      <p className="hint">
        Le niveau numérique dépend du microphone et de son gain. Il ne mesure
        pas le niveau acoustique en dB SPL.
      </p>
    </section>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <AudioLines />
          </span>
          <div>
            VoiceScope <b>AI</b>
            <small>CLASSROOM INTELLIGENCE</small>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav>
          {navigation.map(([label, Icon]) => (
            <button
              key={label}
              aria-current={page === label ? "page" : undefined}
              className={page === label ? "active" : ""}
              onClick={() => setPage(label)}
            >
              <Icon size={19} />
              {label}
            </button>
          ))}
        </nav>
        <div className="privacy">
          <ShieldCheck size={22} />
          <strong>Votre espace local</strong>
          <p>
            Les enregistrements sont traités sur cet ordinateur. Les profils
            restent sur disque.
          </p>
        </div>
        <div className="connection">
          <i className={status ? "online" : ""} />
          {status ? "API connectée" : "API hors ligne"}
          <button className="link" onClick={refresh}>
            Actualiser
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <div className="eyebrow">WORKSPACE / {page.toUpperCase()}</div>
            <h1>{page}</h1>
            <p>
              Analyse d'enregistrement · Intelligence acoustique pour la classe
            </p>
          </div>
          <span className="session-badge">
            <span className="dot" />{" "}
            {result ? "Séance analysée" : "Nouvelle séance"}
          </span>
        </header>
        {notice && (
          <div
            role={notice.error ? "alert" : "status"}
            className={`notice ${notice.error ? "error" : ""}`}
          >
            {notice.text}
            <button
              className="link"
              aria-label="Fermer la notification"
              onClick={() => setNotice(null)}
            >
              ×
            </button>
          </div>
        )}
        {busy && (
          <div className="notice" role="status">
            Traitement en cours… Le premier chargement des modèles peut prendre
            plusieurs minutes.
          </div>
        )}
        {result?.warnings.map((w) => (
          <div className="notice warning" role="status" key={w}>
            {w}
          </div>
        ))}
        {page === "Schedule" && (
          <>
            <section className="card">
              <h2>Ajouter une séance à l’emploi du temps</h2>
              <p className="hint">Ces informations sont facultatives et restent dans votre navigateur.</p>
              <div className="settings-grid">
                {[["professeur", "Professeur"], ["classe", "Classe"], ["matiere", "Matière"], ["salle", "Salle"]].map(([key, label]) => (
                  <label className="field" key={key}>{label}
                    <input value={scheduleDraft[key]} onChange={(e) => setScheduleDraft({ ...scheduleDraft, [key]: e.target.value })} placeholder={label} />
                  </label>
                ))}
                <label className="field">Jour
                  <select value={scheduleDraft.jour} onChange={(e) => setScheduleDraft({ ...scheduleDraft, jour: e.target.value })}>
                    {["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"].map((d) => <option key={d}>{d}</option>)}
                  </select>
                </label>
                <label className="field">Semestre
                  <select value={scheduleDraft.semestre} onChange={(e) => setScheduleDraft({ ...scheduleDraft, semestre: e.target.value })}>
                    <option>Semestre 1</option><option>Semestre 2</option>
                  </select>
                </label>
                <label className="field">Semaine
                  <select value={scheduleDraft.semaine} onChange={(e) => setScheduleDraft({ ...scheduleDraft, semaine: e.target.value })}>
                    <option>Toutes</option><option>Semaine 1</option><option>Semaine 2</option>
                  </select>
                </label>
                <label className="field">Début
                  <input type="time" value={scheduleDraft.debut} onChange={(e) => setScheduleDraft({ ...scheduleDraft, debut: e.target.value })} />
                </label>
                <label className="field">Fin
                  <input type="time" value={scheduleDraft.fin} onChange={(e) => setScheduleDraft({ ...scheduleDraft, fin: e.target.value })} />
                </label>
              </div>
              <button className="btn primary" onClick={addSchedule}>Ajouter la séance</button>
            </section>
            <section className="card">
              <h2>Mes séances</h2>
              {!schedule.length && <p className="empty-text">Aucune séance enregistrée.</p>}
              {schedule.map((s) => (
                <div className="schedule-row" key={s.id}>
                  <div><strong>{s.matiere}</strong><span>{s.classe} · {s.professeur} · {s.salle || "Salle non précisée"}</span></div>
                  <div><b>{s.jour}</b> {s.debut}–{s.fin}</div>
                  <button className="link" onClick={() => setSchedule(schedule.filter((x) => x.id !== s.id))}><Trash2 size={15} /> Supprimer</button>
                </div>
              ))}
            </section>
          </>
        )}
        {page === "Voice Profiles" && (
          <>
            <div className="section-title">
              <div>
                <h2>Donnez un nom à chaque voix</h2>
                <p>Trois personnes, plusieurs échantillons par profil.</p>
              </div>
              <span className="pill">{people.length} / 3 profils</span>
            </div>
            <div className="profile-grid">
              {people.map((p, i) => (
                <section className="card profile" key={p.nom}>
                  <span className="avatar" style={{ color: colors[i] }}>
                    {p.nom[0].toUpperCase()}
                  </span>
                  <h2>{p.nom}</h2>
                  <p>{p.echantillons} échantillon(s)</p>
                  <button className="btn" onClick={() => setName(p.nom)}>
                    Ajouter un échantillon
                  </button>
                  <button
                    className="link"
                    disabled={busy}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Supprimer définitivement le profil ${p.nom} ?`,
                        )
                      )
                        run(async () => setPeople(await api.supprimer(p.nom)));
                    }}
                  >
                    <Trash2 size={14} /> Supprimer
                  </button>
                </section>
              ))}
            </div>
            <section className="card">
              <h2>Enregistrer un profil vocal</h2>
              <p className="hint">
                Avec l'accord de la personne, enregistrez 10 à 15 secondes de
                parole seule et claire. Répétez avec des phrases différentes.
              </p>
              <label className="field">
                Nom
                <input
                  maxLength={40}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Nom de la personne"
                />
              </label>
              <AudioInput value={voice} onChange={setVoice} />
              <button
                className="btn primary"
                disabled={busy || !voice || !name.trim()}
                onClick={add}
              >
                Enregistrer l'empreinte
              </button>
            </section>
            <section className="card">
              <h2>Sauvegarder les profils</h2>
              <p className="hint">
                Les fichiers exportés contiennent des données biométriques non
                chiffrées. Conservez-les dans un emplacement privé.
              </p>
              <div className="row">
                <a className="btn" href="/api/voix/export" download>
                  Exporter les profils
                </a>
                <label className="btn file-label">
                  Importer les profils
                  <input
                    type="file"
                    accept=".json"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files[0];
                      e.target.value = "";
                      if (f) run(async () => setPeople(await api.importer(f)));
                    }}
                  />
                </label>
              </div>
            </section>
          </>
        )}
        {page === "Audio Analysis" && (
          <>
            <section className="card upload">
              <span className="upload-icon">
                <AudioLines size={32} />
              </span>
              <h2>Écouter. Comprendre. Analyser.</h2>
              <p>
                Enregistrez une séance ou importez un fichier audio. Maximum : 5
                minutes / 32 Mio.
              </p>
              <label className="field">
                Séance associée <span className="hint">(optionnel)</span>
                <select value={selectedSchedule} onChange={(e) => setSelectedSchedule(e.target.value)}>
                  <option value="">Analyse libre, sans emploi du temps</option>
                  {schedule.map((s) => <option value={s.id} key={s.id}>{s.jour} {s.debut} · {s.matiere} · {s.classe}</option>)}
                </select>
              </label>
              <AudioInput value={audio} onChange={setAudio} />
              <button
                className="btn primary"
                disabled={!audio || busy}
                onClick={analyse}
              >
                <Play size={16} />
                {busy ? "Analyse en cours…" : "Lancer l’analyse"}
              </button>
              <span className="hint">
                Le traitement commence après l'enregistrement. Aucun résultat en
                temps réel.
              </span>
            </section>
            {result && <AcousticPanels a={a} />}
          </>
        )}
        {page === "Overview" && (
          <>
            <section className="welcome">
              <div className="eyebrow">CHAQUE VOIX COMPTE</div>
              <h2>
                Une nouvelle façon
                <br />
                d'écouter votre classe.
              </h2>
              <p>Des signaux aux échanges : explorez votre séance.</p>
              <button
                className="btn primary"
                onClick={() => setPage("Audio Analysis")}
              >
                Nouvelle analyse <ArrowUpRight size={17} />
              </button>
              <Activity className="welcome-art" aria-hidden="true" />
            </section>
            <div className="kpis">
              {[
                ["Niveau moyen", number(a?.dbfs, " dBFS")],
                ["Fréquence dominante", number(a?.dominant_hz, " Hz", 0)],
                ["Profils vocaux", `${people.length} / 3`],
                ["Voix la plus sonore", noiseLeader || dominantSpeaker || "—"],
                ["Durée analysée", result ? clock(result.duree) : "—"],
                [
                  "Dépassements durables",
                  result ? String(result.alerts.length) : "—",
                ],
              ].map(([label, value]) => (
                <div className="kpi" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            {result ? (
              <>
                <div className="two-col">
                  <section className="card">
                    <h2>Niveau sonore numérique</h2>
                    <SignalChart
                      data={result.niveaux}
                      x="t"
                      y="dbfs"
                      unit="dBFS"
                    />
                    <label className="field">
                      Explorer le temps : {clock(frame?.t || 0)}
                      <input
                        type="range"
                        min={0}
                        max={result.niveaux.length - 1}
                        value={selected}
                        onChange={(e) => setSelected(Number(e.target.value))}
                      />
                    </label>
                  </section>
                  <section className="card">
                    <h2>État du segment sélectionné</h2>
                    <div className="traffic">
                      {["green", "orange", "red"].map((c) => (
                        <span key={c} className={traffic === c ? c : ""} />
                      ))}
                    </div>
                    <strong className="large">
                      {number(frame?.dbfs, " dBFS")}
                    </strong>
                    <p>
                      {
                        {
                          green: "Calme",
                          orange: "Modéré",
                          red: "Seuil dépassé",
                        }[traffic]
                      }
                    </p>
                    <p className="hint">
                      Alerte à partir de {result.options.high_dbfs} dBFS pendant{" "}
                      {result.options.alert_seconds} s consécutives.
                    </p>
                    {result.alerts.map((v, i) => (
                      <div className="notice warning" key={i}>
                        {clock(v.debut)} – {clock(v.fin)} : dépassement
                      </div>
                    ))}
                  </section>
                </div>
                <AcousticPanels a={a} />
              </>
            ) : (
              empty
            )}
          </>
        )}
        {page === "Transcription" &&
          (result ? (
            <section className="card">
              <div className="section-title">
                <h2>La conversation</h2>
                <span className="pill">
                  {result.langue || "Langue indisponible"}
                </span>
              </div>
              <p className="hint">
                Attribution prudente ; une phrase couvrant plusieurs voix reste
                indéterminée.
              </p>
              {!result.transcriptions.length && (
                <p className="empty-text">
                  Aucune transcription disponible pour cette séance.
                </p>
              )}
              {result.transcriptions.map((s, i) => (
                <article className="conversation" key={i}>
                  <span
                    className="avatar"
                    style={{
                      color:
                        colors[
                          Math.max(
                            0,
                            people.findIndex((p) => p.nom === s.locuteur),
                          ) % 3
                        ],
                    }}
                  >
                    {s.locuteur[0]}
                  </span>
                  <div>
                    <strong>{s.locuteur}</strong>
                    <time>
                      {clock(s.debut)} – {clock(s.fin)}
                    </time>
                    <p dir="auto">{s.texte}</p>
                    {s.raison && <span className="uncertain">{s.raison}</span>}
                    {s.scores && (
                      <p className="hint">
                        Similarités :{" "}
                        {Object.entries(s.scores)
                          .map(([n, v]) => `${n} ${v.toFixed(3)}`)
                          .join(" · ")}
                      </p>
                    )}
                  </div>
                </article>
              ))}
            </section>
          ) : (
            empty
          ))}
        {page === "Analytics" && (
          <>
            {result ? (
              <>
                <div className="two-col">
                  <section className="card">
                    <h2>Qui produit le plus de bruit vocal ?</h2>
                    <div className="noise-leader">
                      <strong>{result.locuteur_bruit_principal || "Aucun profil identifié"}</strong>
                      {result.locuteur_bruit_principal && (() => {
                        const leader = result.statistics.find(
                          (s) => s.nom === result.locuteur_bruit_principal,
                        );
                        return leader ? (
                          <span>
                            {number(leader.part_bruit, " % de l’énergie vocale")} · moyenne {number(leader.niveau_moyen_dbfs, " dBFS")}
                          </span>
                        ) : null;
                      })()}
                    </div>
                    <p className="hint">
                      Estimation basée sur l’énergie des segments attribués à chaque profil vocal.
                    </p>
                    <h2>Temps de parole estimé</h2>
                    <Participation data={result.statistics} />
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Personne</th>
                            <th>Durée</th>
                            <th>Participation</th>
                            <th>Prises</th>
                            <th>Énergie vocale</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.statistics.map((s) => (
                            <tr key={s.nom}>
                              <td>{s.nom}</td>
                              <td>{number(s.secondes, " s")}</td>
                              <td>{number(s.participation, " %")}</td>
                              <td>{s.prises}</td>
                              <td>{number(s.part_bruit, " %")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="hint">
                      Le dénominateur inclut les voix inconnues et
                      indéterminées. Silences exclus.
                    </p>
                  </section>
                  <section className="card">
                    <h2>Catégories sonores</h2>
                    <Categories events={result.events} />
                    <p className="hint">
                      {result.classifier} · scores du modèle, non calibrés. Pas
                      d'inférence sur la cause d'un bruit.
                    </p>
                  </section>
                </div>
                <section className="card">
                  <h2>Timeline des interventions</h2>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Intervalle</th>
                          <th>Locuteur</th>
                          <th>Similarités cosinus</th>
                          <th>Observation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.segments.map((s, i) => (
                          <tr key={i}>
                            <td>
                              {clock(s.debut)} – {clock(s.fin)}
                            </td>
                            <td>{s.locuteur}</td>
                            <td>
                              {s.scores
                                ? Object.entries(s.scores)
                                    .map(([n, v]) => `${n}: ${v.toFixed(3)}`)
                                    .join(" / ")
                                : "—"}
                            </td>
                            <td>{s.raison || "Attribution estimée"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="card">
                  <h2>Événements sonores</h2>
                  <div className="event-list">
                    {result.events.map((e, i) => (
                      <div className="event" key={i}>
                        <time>
                          {clock(e.debut)} – {clock(e.fin)}
                        </time>
                        <strong>{e.categorie}</strong>
                        <span>score {e.score.toFixed(3)}</span>
                      </div>
                    ))}
                    {!result.events.length && (
                      <p>Aucun résultat de classification disponible.</p>
                    )}
                  </div>
                </section>
              </>
            ) : (
              empty
            )}
            <section className="card">
              <h2>Historique de cette session serveur</h2>
              <p className="hint">
                Les 10 dernières analyses, en mémoire seulement. Exportez les
                résultats avant de fermer le serveur.
              </p>
              {history.map((h) => (
                <div className="row" key={h.id}>
                  <button
                    className="btn"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        setResult(await api.session(h.id));
                        setSelected(0);
                      })
                    }
                  >
                    {new Date(h.date).toLocaleString()} · {clock(h.duree)}
                  </button>
                  <button
                    className="link"
                    aria-label="Supprimer cette analyse"
                    onClick={() =>
                      run(async () => {
                        await api.deleteSession(h.id);
                        if (result?.id === h.id) setResult(null);
                        await refresh();
                      })
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </section>
          </>
        )}
        {page === "Reports" &&
          (result ? (
            <>
              <section className="card">
                <h2>Emportez votre analyse</h2>
                <p>
                  Rapport de la séance du{" "}
                  {new Date(result.date).toLocaleString()} ·{" "}
                  {clock(result.duree)}
                </p>
                <div className="report-grid">
                  {[
                    ["pdf", "Rapport complet"],
                    ["txt", "Transcription"],
                    ["csv", "Données tabulaires"],
                    ["json", "Résultats structurés"],
                  ].map(([ext, label]) => (
                    <button
                      className="report"
                      key={ext}
                      onClick={() => run(() => api.download(result.id, ext))}
                      disabled={busy}
                    >
                      <FileDown />
                      <strong>{ext.toUpperCase()}</strong>
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </section>
              <section className="card">
                <h2>Lire les résultats avec prudence</h2>
                {result.limitations.map((l) => (
                  <p key={l}>{l}</p>
                ))}
              </section>
            </>
          ) : (
            empty
          ))}
        {page === "Settings" && (
          <>
            {settings}
            <section className="card">
              <h2>Disponibilité des dépendances</h2>
              <p>
                Reconnaissance : {status?.pret ? "installée" : "absente"} ·
                Transcription :{" "}
                {status?.stt_disponible ? "installée" : "absente"} · YAMNet :{" "}
                {status?.classification_disponible ? "installé" : "absent"}
              </p>
              <p className="hint">
                La présence d'une dépendance ne garantit pas le chargement de
                ses poids. Les erreurs sont indiquées après traitement.
              </p>
            </section>
          </>
        )}
        <footer>
          VoiceScope AI · Classroom Audio Analytics{" "}
          <span>Signal numérique · Données locales</span>
        </footer>
      </main>
    </div>
  );
}
function AcousticPanels({ a }) {
  return (
    <div className="two-col">
      <section className="card">
        <h2>Waveform</h2>
        <SignalChart
          data={a.waveform}
          x="t"
          y="max"
          second="min"
          unit="amplitude"
        />
      </section>
      <section className="card">
        <h2>Distribution des fréquences</h2>
        <SignalChart data={a.spectrum} x="hz" y="power_db" unit="dB/Hz" />
        <p className="hint">
          Centroïde FFT : {number(a.centroid_hz, " Hz")} · RMS :{" "}
          {number(a.rms, "", 4)}
        </p>
      </section>
      <section className="card wide">
        <h2>Spectrogramme STFT</h2>
        <Spectrogram data={a.spectrogram} />
        <p className="hint">
          Amplitude spectrale numérique · Fenêtre Hann 512 échantillons · Pas
          256 · pics conservés par groupe temporel.
        </p>
      </section>
    </div>
  );
}
