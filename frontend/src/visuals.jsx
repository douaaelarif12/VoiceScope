import { useEffect, useRef, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
const tooltip = {
  background: "#172238",
  border: "1px solid #36445e",
  borderRadius: 10,
  color: "#f4f6ff",
};
export function SignalChart({ data, x, y, second, unit }) {
  return (
    <div className="plot" role="img" aria-label={`Graphique ${y} en ${unit}`}>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart
          data={data}
          margin={{ left: 4, right: 15, top: 15, bottom: 10 }}
        >
          <CartesianGrid stroke="#28354c" vertical={false} />
          <XAxis
            dataKey={x}
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v) =>
              `${Math.round(v)}${x === "hz" ? " Hz" : " s"}`
            }
            minTickGap={55}
            stroke="#a6b4cb"
          />
          <YAxis
            width={55}
            stroke="#a6b4cb"
            tickFormatter={(v) => Number(v).toFixed(1)}
          />
          <Tooltip
            contentStyle={tooltip}
            labelFormatter={(v) =>
              `${Number(v).toFixed(2)} ${x === "hz" ? "Hz" : "s"}`
            }
            formatter={(v) => [`${Number(v).toFixed(3)} ${unit}`]}
          />
          <Line
            dataKey={y}
            stroke="#22d3ee"
            dot={false}
            isAnimationActive={false}
            strokeWidth={1.5}
          />
          {second && (
            <Line
              dataKey={second}
              stroke="#818cf8"
              dot={false}
              isAnimationActive={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Participation({ data }) {
  return data.length ? (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data}>
        <XAxis dataKey="nom" stroke="#a6b4cb" />
        <YAxis stroke="#a6b4cb" />
        <Tooltip contentStyle={tooltip} />
        <Bar dataKey="secondes" fill="#818cf8" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  ) : (
    <p>Aucune parole attribuable détectée.</p>
  );
}
export function Categories({ events }) {
  const totals = {};
  events.forEach(
    (e) => (totals[e.categorie] = (totals[e.categorie] || 0) + e.fin - e.debut),
  );
  return events.length ? (
    <Participation
      data={Object.entries(totals).map(([nom, secondes]) => ({
        nom,
        secondes,
      }))}
    />
  ) : (
    <p>Aucune catégorie sonore disponible.</p>
  );
}
export function Spectrogram({ data }) {
  const ref = useRef(null),
    [probe, setProbe] = useState(null);
  useEffect(() => {
    const canvas = ref.current,
      ctx = canvas.getContext("2d"),
      w = data.times.length,
      h = data.frequencies.length;
    canvas.width = w;
    canvas.height = h;
    const img = ctx.createImageData(w, h);
    for (let x = 0; x < w; x++)
      for (let y = 0; y < h; y++) {
        const v = Math.max(0, Math.min(1, (data.db[y][x] + 100) / 100)),
          i = ((h - 1 - y) * w + x) * 4;
        img.data[i] = Math.round(20 + 95 * v);
        img.data[i + 1] = Math.round(20 + 195 * v);
        img.data[i + 2] = Math.round(45 + 190 * v);
        img.data[i + 3] = 255;
      }
    ctx.putImageData(img, 0, 0);
  }, [data]);
  const show = (e) => {
    const r = e.currentTarget.getBoundingClientRect(),
      x = Math.max(
        0,
        Math.min(
          data.times.length - 1,
          Math.floor(((e.clientX - r.left) / r.width) * data.times.length),
        ),
      ),
      y = Math.max(
        0,
        Math.min(
          data.frequencies.length - 1,
          Math.floor(
            (1 - (e.clientY - r.top) / r.height) * data.frequencies.length,
          ),
        ),
      );
    setProbe({ x, y });
  };
  return (
    <div>
      <div className="spectrogram">
        <span>
          8 kHz
          <br />
          <br />
          <br />0 Hz
        </span>
        <canvas
          ref={ref}
          role="img"
          aria-label="Spectrogramme temps-fréquence de 0 à 8 kHz"
          onPointerMove={show}
        />
      </div>
      <p className="hint">
        0 s → {data.times.at(-1)?.toFixed(2)} s · Survolez pour explorer
      </p>
      <label className="field">
        Colonne temporelle (clavier)
        <input
          type="range"
          min="0"
          max={data.times.length - 1}
          value={probe?.x || 0}
          onChange={(e) =>
            setProbe({ x: Number(e.target.value), y: probe?.y || 0 })
          }
        />
      </label>
      <label className="field">
        Bande de fréquence
        <input
          type="range"
          min="0"
          max={data.frequencies.length - 1}
          value={probe?.y || 0}
          onChange={(e) =>
            setProbe({ x: probe?.x || 0, y: Number(e.target.value) })
          }
        />
      </label>
      <output>
        {probe
          ? `${data.times[probe.x].toFixed(2)} s · ${data.frequencies[probe.y].toFixed(1)} Hz · ${data.db[probe.y][probe.x].toFixed(1)} dB`
          : "Sélectionnez un point du spectrogramme."}
      </output>
    </div>
  );
}
