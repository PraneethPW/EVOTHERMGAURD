import { FormEvent, ReactNode, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, warmAppData } from "./api/client";
type User = { id: string; name: string; email: string };
type Eq = {
  id: string;
  equipment_name: string;
  equipment_type: string;
  asset_code?: string;
  location_label?: string;
};
const ORIGIN = (
    import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
  ).replace("/api/v1", ""),
  RISKS = ["NORMAL", "WARNING", "HIGH_RISK", "CRITICAL"],
  COLORS = ["#22d3ee", "#fbbf24", "#fb6b24", "#ff2e43"];
const glyph: any = {
  home: "◉",
  inspect: "⌁",
  history: "↶",
  risk: "△",
  lab: "◇",
  ai: "✦",
  equipment: "⬡",
  logout: "↗",
  upload: "↑",
  arrow: "→",
  temp: "♨",
  weather: "☼",
  model: "◈",
};
function I({ n }: { n: string }) {
  return <span className="icon">{glyph[n] || "•"}</span>;
}
function tone(r?: string) {
  return (r || "pending").toLowerCase().replace("_", "-");
}
function label(r?: string) {
  return (r || "PENDING").replace("_", " ");
}
function date(v?: string) {
  return v
    ? new Date(v).toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}
function Bg() {
  return (
    <div className="thermal-bg">
      <div className="grid-overlay" />
      <div className="heat-bloom one" />
      <div className="heat-bloom two" />
      <div className="cool-bloom" />
      <div className="scan-lines" />
      <div className="noise" />
    </div>
  );
}
function Brand() {
  return (
    <Link className="brand" to="/">
      <span className="brand-mark">
        <I n="equipment" />
        <i />
      </span>
      <span>
        Evo<span>Therm</span>Guard
      </span>
    </Link>
  );
}
function Glass({
  children,
  className = "",
  tone = "",
}: {
  children: ReactNode;
  className?: string;
  tone?: string;
}) {
  return (
    <motion.section
      whileHover={{ y: -3 }}
      className={`glass-card ${tone} ${className}`}
    >
      {children}
    </motion.section>
  );
}
function Badge({ risk }: { risk?: string }) {
  return (
    <span className={`risk-badge ${tone(risk)}`}>
      <i />
      {label(risk)}
    </span>
  );
}
function Btn({
  children,
  type = "button",
  onClick,
  disabled = false,
  loading = false,
}: {
  children: ReactNode;
  type?: "button" | "submit";
  onClick?: () => void | Promise<void>;
  disabled?: boolean;
  loading?: boolean;
}) {
  const [pending, setPending] = useState(false);
  async function handleClick() {
    if (!onClick) return;
    setPending(true);
    try {
      await onClick();
    } finally {
      setPending(false);
    }
  }
  const isLoading = loading || pending;
  return (
    <motion.button
      whileHover={{ scale: 1.015 }}
      whileTap={{ scale: 0.98 }}
      className="btn primary"
      type={type}
      onClick={handleClick}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
    >
      <i className="shine" />
      {isLoading ? <><span className="button-loader" /> Working…</> : children}
    </motion.button>
  );
}
function Page({
  eye,
  title,
  sub,
  action,
  children,
}: {
  eye: string;
  title: string;
  sub: string;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <motion.main
      className="page"
      initial={{ opacity: 0, y: 10, filter: "blur(7px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
      exit={{ opacity: 0, y: -6 }}
    >
      <header className="page-heading">
        <div>
          <span className="eyebrow">{eye}</span>
          <h1>{title}</h1>
          <p>{sub}</p>
        </div>
        {action}
      </header>
      {children}
    </motion.main>
  );
}
function Title({ eye, title }: { eye: string; title: string }) {
  return (
    <div className="section-title">
      <span>{eye}</span>
      <h2>{title}</h2>
    </div>
  );
}
function Empty({
  title,
  copy,
  action,
}: {
  title: string;
  copy: string;
  action?: ReactNode;
}) {
  return (
    <div className="premium-empty">
      <div className="radar-rings">
        <i />
        <i />
        <i />
        <span>
          <I n="equipment" />
        </span>
      </div>
      <div>
        <span className="eyebrow">AWAITING SIGNAL</span>
        <h2>{title}</h2>
        <p>{copy}</p>
        {action}
      </div>
    </div>
  );
}
function Landing() {
  return (
    <div className="landing rescue">
      <Bg />
      <nav className="landing-nav">
        <Brand />
        <div>
          <a href="#system">Intelligence</a>
          <a href="#evidence">Evidence</a>
          <Link to="/login">Sign in</Link>
          <Link className="btn primary" to="/register">
            Run inspection <I n="arrow" />
          </Link>
        </div>
      </nav>
      <section className="landing-hero">
        <div>
          <span className="eyebrow">
            MULTISPECTRAL INFRASTRUCTURE INTELLIGENCE
          </span>
          <h1>
            SEE HEAT
            <br />
            <em>IN CONTEXT.</em>
          </h1>
          <p>
            Fuse visual evidence, thermal patterns and environmental context
            into an interpretable infrastructure risk signal.
          </p>
          <Link className="btn primary" to="/register">
            Enter intelligence layer <I n="arrow" />
          </Link>
        </div>
        <Hero />
      </section>
      <section id="system" className="landing-section">
        <Title
          eye="ONE IMAGE DOESN'T TELL THE WHOLE STORY"
          title="Structure. Heat. Context. One evidence chain."
        />
        <div className="story-grid">
          {[
            [
              "equipment",
              "RGB sees structure",
              "Cool-channel equipment evidence",
            ],
            [
              "temp",
              "Thermal sees heat",
              "Relative intensity—not radiometric temperature",
            ],
            [
              "weather",
              "Environment adds context",
              "Operator-submitted conditions",
            ],
            [
              "model",
              "EvoThermGuard connects it",
              "Traceable risk and visual evidence",
            ],
          ].map((x, i) => (
            <Glass key={x[1]} className="story-card">
              <span>0{i + 1}</span>
              <I n={x[0]} />
              <h3>{x[1]}</h3>
              <p>{x[2]}</p>
              <i className="energy" />
            </Glass>
          ))}
        </div>
      </section>
      <section id="evidence" className="landing-section">
        <Title
          eye="MULTISPECTRAL FUSION"
          title="Evidence converges. Context stays visible."
        />
        <Fusion />
        <div className="bento">
          {[
            "Grad-CAM attribution",
            "Environment awareness",
            "Risk interpretation",
            "Evolutionary Model Lab",
            "Inspection history",
            "AI Analyst",
          ].map((x, i) => (
            <Glass key={x} className={i === 0 || i === 5 ? "wide" : ""}>
              <I
                n={["inspect", "weather", "risk", "lab", "history", "ai"][i]}
              />
              <h3>{x}</h3>
              <p>
                {
                  [
                    "Reveal model-attributed regions for review.",
                    "Keep site conditions attached to every run.",
                    "Translate risk class into deterministic guidance.",
                    "Visualise real NSGA-II experiments when available.",
                    "Preserve an audit-friendly evidence chain.",
                    "Explain only the selected inspection data.",
                  ][i]
                }
              </p>
            </Glass>
          ))}
        </div>
      </section>
      <section className="landing-cta">
        <span className="eyebrow">THE OPERATOR REMAINS IN CONTROL</span>
        <h2>Bring thermal evidence into context.</h2>
        <Link className="btn primary" to="/register">
          Run an inspection <I n="arrow" />
        </Link>
      </section>
    </div>
  );
}
function Hero() {
  const [p, setP] = useState(55);
  return (
    <div
      className="thermal-hero"
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        setP(((e.clientX - r.left) / r.width) * 100);
      }}
    >
      <div className="hero-panel rgb">
        <div className="transformer">
          <i />
          <i />
          <i />
          <span />
        </div>
        <small>RGB / STRUCTURE</small>
      </div>
      <div
        className="hero-panel thermal"
        style={{ clipPath: `inset(0 0 0 ${p}%)` }}
      >
        <div className="thermal-map">
          <i />
          <i />
          <i />
        </div>
        <small>THERMAL / RELATIVE HEAT</small>
      </div>
      <i className="reveal-line" style={{ left: `${p}%` }} />
      <div className="float-chip top">ENVIRONMENT · LINKED</div>
      <div className="float-chip bottom">BASELINE · UNVALIDATED</div>
    </div>
  );
}
function Fusion() {
  return (
    <Glass className="fusion-stage">
      <div>
        <I n="equipment" />
        <b>RGB STREAM</b>
      </div>
      <i />
      <div>
        <I n="temp" />
        <b>FUSION CORE</b>
        <span />
      </div>
      <i />
      <div>
        <I n="weather" />
        <b>CONTEXTUAL RISK</b>
      </div>
    </Glass>
  );
}
function Auth({
  register = false,
  onAuth,
}: {
  register?: boolean;
  onAuth: (u: User) => void;
}) {
  const nav = useNavigate();
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(
        register ? "/auth/register" : "/auth/login",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      localStorage.setItem("etg_token", r.data.access_token);
      onAuth(r.data.user);
      nav("/app");
    } catch (x: any) {
      setErr(x.response?.data?.detail || "Access request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth rescue">
      <Bg />
      <section className="auth-visual">
        <Brand />
        <div>
          <span className="eyebrow">EVOTHERMGUARD ACCESS PORTAL</span>
          <h1>
            Enter the thermal
            <br />
            <em>intelligence layer.</em>
          </h1>
          <p>
            Multispectral evidence.
            <br />
            Environmental context.
            <br />
            Explainable risk.
          </p>
        </div>
        <div className="auth-scene">
          <i />
          <i />
          <i />
          <span>
            <I n="equipment" />
          </span>
        </div>
      </section>
      <section className="auth-form-side">
        <form className="auth-card rescue" onSubmit={submit}>
          <span className="eyebrow">
            {register ? "NEW OPERATOR PROFILE" : "SECURE OPERATOR ACCESS"}
          </span>
          <h2>{register ? "Create your workspace" : "Welcome back"}</h2>
          <p>
            {register
              ? "Start a traceable inspection workspace."
              : "Continue to the command center."}
          </p>
          {register && (
            <Field l="Operator name">
              <input
                name="name"
                required
                minLength={2}
                placeholder="Your name"
              />
            </Field>
          )}
          <Field l="Email">
            <input
              name="email"
              type="email"
              required
              placeholder="operator@company.com"
            />
          </Field>
          <Field l="Password">
            <input
              name="password"
              type="password"
              minLength={8}
              maxLength={128}
              required
              placeholder="8+ secure characters"
            />
          </Field>
          {err && <div className="error-panel">△ {err}</div>}
          <Btn type="submit" disabled={busy}>
            {busy
              ? "Authenticating…"
              : register
                ? "Create operator account"
                : "Enter command center"}{" "}
            <I n="arrow" />
          </Btn>
          <p>
            {register ? "Already registered?" : "New here?"}{" "}
            <Link to={register ? "/login" : "/register"}>
              {register ? "Sign in" : "Create account"}
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
function Field({ l, children }: { l: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{l}</span>
      {children}
    </label>
  );
}
const NAV = [
  ["home", "Dashboard", "/app"],
  ["inspect", "New Inspection", "/app/inspect"],
  ["history", "Inspections", "/app/history"],
  ["equipment", "Equipment", "/app/equipment"],
  ["risk", "Risk Monitor", "/app/risk"],
  ["lab", "Model Lab", "/app/lab"],
  ["ai", "AI Analyst", "/app/ai"],
];
function Shell({ user, out }: { user: User; out: () => void }) {
  const loc = useLocation();
  return (
    <div className="shell rescue">
      <Bg />
      <aside className="sidebar rescue">
        <Brand />
        <div className="system-chip">
          <i />
          <span>
            <b>SYSTEM ONLINE</b>
            <small>API availability</small>
          </span>
        </div>
        <nav>
          {NAV.map((x) => (
            <NavLink end={x[2] === "/app"} to={x[2]} key={x[2]}>
              <I n={x[0]} />
              <span>{x[1]}</span>
              <i />
            </NavLink>
          ))}
        </nav>
        <div className="model-tile">
          <span>ACTIVE MODEL</span>
          <b>BASELINE HEURISTIC</b>
          <small>UNVALIDATED · DEMO</small>
        </div>
        <div className="operator-block">
          <b>{user.name.slice(0, 2).toUpperCase()}</b>
          <span>
            {user.name}
            <small>Operator</small>
          </span>
          <button onClick={out}>
            <I n="logout" />
          </button>
        </div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <span>
            <i /> THERMAL INTELLIGENCE OS
          </span>
          <b>BASELINE / UNVALIDATED</b>
        </header>
        <AnimatePresence mode="wait">
          <Routes location={loc} key={loc.pathname}>
            <Route index element={<Dashboard />} />
            <Route path="inspect" element={<Inspect />} />
            <Route path="history" element={<History />} />
            <Route path="inspections/:id" element={<Detail />} />
            <Route path="equipment" element={<Equipment />} />
            <Route path="equipment/:id" element={<EquipmentDetail />} />
            <Route path="risk" element={<Risk />} />
            <Route path="lab" element={<Lab />} />
            <Route path="ai" element={<AI />} />
          </Routes>
        </AnimatePresence>
      </section>
      <nav className="mobile-dock">
        {NAV.filter((_, i) => [0, 1, 2, 4, 6].includes(i)).map((x) => (
          <NavLink end={x[2] === "/app"} to={x[2]} key={x[2]}>
            <I n={x[0]} />
            <span>{x[1].split(" ")[0]}</span>
            <i />
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
function Dashboard() {
  return <Dashboard2 />;
}
function DashboardData({ d }: { d: any }) {
  const pie = RISKS.map((x, i) => ({
      name: x,
      value: d.risk_distribution[x],
      color: COLORS[i],
    })),
    act = d.activity
      .map((x: any) => ({
        date: new Date(x.date).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        risk: x.risk_level ? RISKS.indexOf(x.risk_level) + 1 : 0,
      }))
      .reverse();
  return (
    <div className="dashboard-bento">
      <Glass className="chart-panel">
        <Title eye="RISK DISTRIBUTION" title="Assessment spectrum" />
        <ResponsiveContainer height={240}>
          <PieChart>
            <Pie
              data={pie}
              dataKey="value"
              innerRadius={65}
              outerRadius={90}
              stroke="none"
            >
              {pie.map((x) => (
                <Cell fill={x.color} key={x.name} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <div className="legend">
          {pie.map((x) => (
            <span>
              <i style={{ background: x.color }} />
              {label(x.name)} <b>{x.value}</b>
            </span>
          ))}
        </div>
      </Glass>
      <Glass className="chart-panel">
        <Title eye="INSPECTION ACTIVITY" title="Risk timeline" />
        <ResponsiveContainer height={240}>
          <AreaChart data={act}>
            <CartesianGrid stroke="#24303a" strokeDasharray="3 8" />
            <XAxis dataKey="date" stroke="#70808c" />
            <YAxis hide domain={[0, 4]} />
            <Area dataKey="risk" stroke="#ff6a00" fill="#ff6a0020" />
          </AreaChart>
        </ResponsiveContainer>
      </Glass>
      <Glass className="recent-panel">
        <Title eye="RECENT INSPECTIONS" title="Latest evidence records" />
        {d.recent.map((x: any) => (
          <Row x={x} />
        ))}
      </Glass>
      <Glass className="equipment-matrix">
        <Title eye="EQUIPMENT RISK MATRIX" title="Latest asset state" />
        {d.equipment_matrix.map((x: any) => (
          <Link to={`/app/equipment/${x.id}`}>
            <b>{x.name}</b>
            <small>{x.location || x.type}</small>
            <Badge risk={x.latest?.risk_level} />
          </Link>
        ))}
      </Glass>
    </div>
  );
}
function Row({ x }: { x: any }) {
  return (
    <Link className="inspection-row" to={`/app/inspections/${x.id}`}>
      <i className={tone(x.risk_level)} />
      <span>
        <b>{x.equipment || x.equipment_name}</b>
        <small>
          {date(x.created_at)} · {x.model_version || "Pending"}
        </small>
      </span>
      {x.environment && (
        <em>
          {x.environment.ambient_temperature}°C · {x.environment.weather}
        </em>
      )}
      <Badge risk={x.risk_level || x.prediction?.risk_level} />
      {x.confidence != null && (
        <strong>{(x.confidence * 100).toFixed(1)}%</strong>
      )}
    </Link>
  );
}
function Equipment() {
  const [items, setItems] = useState<Eq[]>([]),
    [open, setOpen] = useState(false),
    [type, setType] = useState("Distribution Transformer");
  async function load() {
    setItems((await api.get("/equipment")).data);
  }
  useEffect(() => {
    load();
  }, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data: any = Object.fromEntries(new FormData(e.currentTarget));
    data.equipment_type = type === "Other" ? data.custom_type || "Other" : type;
    await api.post("/equipment", data);
    setOpen(false);
    load();
  }
  const types = [
    "Distribution Transformer",
    "Power Transformer",
    "Electrical Switchgear",
    "Circuit Breaker",
    "Motor",
    "Generator",
    "Industrial Pump",
    "Compressor",
    "HVAC Unit",
    "Electrical Panel",
    "Busbar",
    "Cable Joint",
    "Bearing Assembly",
    "Other",
  ];
  return (
    <Page
      eye="ASSET INTELLIGENCE"
      title="Equipment Registry"
      sub="Infrastructure assets linked to the evidence history."
      action={
        <Btn onClick={() => setOpen(true)}>
          Register asset <I n="arrow" />
        </Btn>
      }
    >
      <div className="equipment-grid">
        {items.map((x) => (
          <Link to={`/app/equipment/${x.id}`}>
            <Glass className="equipment-card">
              <div className="asset-visual">
                <I n="equipment" />
                <i />
              </div>
              <span className="eyebrow">
                {x.asset_code || "UNASSIGNED CODE"}
              </span>
              <h3>{x.equipment_name}</h3>
              <p>
                {x.equipment_type} · {x.location_label || "Location not set"}
              </p>
              <span className="diagnostic-line">THERMAL NETWORK · READY</span>
            </Glass>
          </Link>
        ))}
        {!items.length && (
          <Glass>
            <Empty
              title="No equipment assets"
              copy="Create the first asset to begin an evidence chain."
              action={
                <Btn onClick={() => setOpen(true)}>Register first asset</Btn>
              }
            />
          </Glass>
        )}
      </div>
      {open && (
        <div className="modal-backdrop" onMouseDown={() => setOpen(false)}>
          <motion.div
            className="modal asset-modal"
            onMouseDown={(e) => e.stopPropagation()}
            initial={{ y: 15, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
          >
            <span className="eyebrow">REGISTER ASSET</span>
            <h2>Add infrastructure to the thermal intelligence network.</h2>
            <form onSubmit={create}>
              <div className="asset-steps">
                <span>01 IDENTITY</span>
                <span>02 CLASSIFICATION</span>
                <span>03 LOCATION</span>
              </div>
              <Field l="Equipment name">
                <input
                  required
                  name="equipment_name"
                  placeholder="Transformer-A01"
                />
              </Field>
              <div className="type-tiles">
                {[
                  ["equipment", "Distribution Transformer"],
                  ["model", "Motor"],
                  ["risk", "Generator"],
                  ["inspect", "Electrical Panel"],
                  ["weather", "Industrial Pump"],
                  ["arrow", "Other"],
                ].map((x) => (
                  <button
                    type="button"
                    className={type === x[1] ? "chosen" : ""}
                    onClick={() => setType(x[1])}
                  >
                    <I n={x[0]} />
                    <span>{x[1].replace("Industrial ", "")}</span>
                  </button>
                ))}
              </div>
              <Field l="Equipment type">
                <select value={type} onChange={(e) => setType(e.target.value)}>
                  {types.map((x) => (
                    <option>{x}</option>
                  ))}
                </select>
              </Field>
              {type === "Other" && (
                <Field l="Custom equipment type">
                  <input
                    required
                    name="custom_type"
                    placeholder="Describe the asset"
                  />
                </Field>
              )}
              <div className="form-grid">
                <Field l="Asset code">
                  <input name="asset_code" placeholder="TR-A01" />
                </Field>
                <Field l="Location type">
                  <select name="location_type">
                    <option>Indoor</option>
                    <option>Outdoor</option>
                    <option>Substation</option>
                    <option>Industrial Plant</option>
                    <option>Utility Room</option>
                    <option>Control Room</option>
                    <option>Manufacturing Floor</option>
                    <option>Power Station</option>
                    <option>Other</option>
                  </select>
                </Field>
                <Field l="Actual location">
                  <input name="location_label" placeholder="North substation" />
                </Field>
                <Field l="Voltage class">
                  <select name="voltage_class">
                    <option>Unknown</option>
                    <option>Low Voltage</option>
                    <option>Medium Voltage</option>
                    <option>High Voltage</option>
                    <option>Extra High Voltage</option>
                    <option>Not Applicable</option>
                  </select>
                </Field>
              </div>
              <Field l="Manufacturer">
                <input name="manufacturer" placeholder="Optional" />
              </Field>
              <Btn type="submit">
                Register asset <I n="arrow" />
              </Btn>
            </form>
          </motion.div>
        </div>
      )}
    </Page>
  );
}
function EquipmentDetail() {
  const { id } = useParams();
  const [d, setD] = useState<any>();
  useEffect(() => {
    api.get(`/equipment/${id}`).then((r) => setD(r.data));
  }, [id]);
  return (
    <Page
      eye="ASSET PROFILE"
      title={d?.equipment_name || "Linking asset intelligence"}
      sub={
        d
          ? `${d.equipment_type} · ${d.asset_code || "No asset code"}`
          : "Retrieving equipment history…"
      }
      action={
        d && (
          <Link className="btn primary" to={`/app/inspect?equipment=${id}`}>
            Inspect asset <I n="arrow" />
          </Link>
        )
      }
    >
      {d && (
        <div className="asset-profile">
          <Glass className="asset-identity">
            <div className="asset-visual large">
              <I n="equipment" />
            </div>
            <dl>
              <dt>Location</dt>
              <dd>{d.location_label || "Not provided"}</dd>
              <dt>Manufacturer</dt>
              <dd>{d.manufacturer || "Not provided"}</dd>
              <dt>Inspections</dt>
              <dd>{d.inspection_count}</dd>
              <dt>Latest risk</dt>
              <dd>
                <Badge risk={d.latest_risk} />
              </dd>
            </dl>
          </Glass>
          <Glass className="recent-panel">
            <Title eye="INSPECTION HISTORY" title="Asset risk record" />
            {d.inspections.length ? (
              d.inspections.map((x: any) => (
                <Link
                  className="inspection-row"
                  to={`/app/inspections/${x.id}`}
                >
                  <span>
                    <b>{date(x.created_at)}</b>
                    <small>{x.status}</small>
                  </span>
                  <Badge risk={x.risk_level} />
                  {x.confidence && (
                    <strong>{(x.confidence * 100).toFixed(1)}%</strong>
                  )}
                </Link>
              ))
            ) : (
              <Empty
                title="No inspection history"
                copy="Run the first inspection for this asset."
              />
            )}
          </Glass>
        </div>
      )}
    </Page>
  );
}
const PIPE = [
  ["input_acquired", "INPUT ACQUIRED"],
  ["preprocessing", "PREPROCESSING"],
  ["registration", "RGB / THERMAL REGISTRATION"],
  ["fusion", "MULTISPECTRAL FUSION"],
  ["inference", "MODEL INFERENCE"],
  ["gradcam", "GRAD-CAM EVIDENCE"],
  ["risk_interpretation", "RISK INTERPRETATION"],
];

function evidenceAssetFor(equipmentType: string) {
  const type = equipmentType.toLowerCase();
  if (type.includes("switchgear") || type.includes("panel") || type.includes("breaker")) return "/assets/thermal-switchgear-3d.png";
  if (type.includes("pump") || type.includes("compressor")) return "/assets/thermal-pump-3d.png";
  if (type.includes("generator")) return "/assets/thermal-generator-3d.png";
  if (type.includes("motor")) return "/assets/thermal-motor-3d.png";
  return "/assets/thermal-transformer-3d.png";
}

async function demoEvidenceFile(
  asset: Eq,
  kind: "rgb" | "thermal",
): Promise<File> {
  const source = new Image();
  source.src = evidenceAssetFor(asset.equipment_type);
  await new Promise<void>((resolve, reject) => {
    source.onload = () => resolve();
    source.onerror = () => reject(new Error("The demo evidence asset could not be loaded."));
  });
  const canvas = document.createElement("canvas");
  canvas.width = 1280;
  canvas.height = 720;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Image generation is not available in this browser.");
  ctx.fillStyle = "#05090c";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  const heatX = 720 + (asset.equipment_name.length * 29) % 330;
  const heatY = 240 + (asset.equipment_type.length * 23) % 250;
  if (kind === "thermal") {
    ctx.globalCompositeOperation = "screen";
    const heat = ctx.createRadialGradient(heatX, heatY, 12, heatX, heatY, 210);
    heat.addColorStop(0, "rgba(255, 245, 120, .98)");
    heat.addColorStop(.22, "rgba(255, 110, 0, .8)");
    heat.addColorStop(.55, "rgba(220, 35, 58, .36)");
    heat.addColorStop(1, "rgba(74, 19, 127, 0)");
    ctx.fillStyle = heat;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.globalCompositeOperation = "source-over";
  }
  ctx.fillStyle = "rgba(3, 8, 12, .74)";
  ctx.fillRect(28, 28, 480, 70);
  ctx.strokeStyle = kind === "thermal" ? "#ff6a00" : "#00e5ff";
  ctx.strokeRect(28, 28, 480, 70);
  ctx.fillStyle = "#f4f7fa";
  ctx.font = "500 18px monospace";
  ctx.fillText(`AI DEMO / ${kind.toUpperCase()} / ${asset.equipment_type}`, 48, 72);
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("Unable to create demo evidence."))), "image/png"),
  );
  const slug = (asset.asset_code || asset.equipment_name).replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  return new File([blob], `ai-demo-${slug}-${kind}.png`, { type: "image/png" });
}

function Inspect() {
  const nav = useNavigate(),
    q = new URLSearchParams(useLocation().search);
  const [eq, setEq] = useState<Eq[]>([]),
    [selected, setSelected] = useState(q.get("equipment") || ""),
    [files, setFiles] = useState<any>({}),
    [env, setEnv] = useState<any>({
      ambient_temperature: "",
      humidity: "",
      weather: "Sunny",
      season: "Summer",
      time_of_day: "Afternoon",
      sun_exposure: "",
    }),
    [err, setErr] = useState(""),
    [generating, setGenerating] = useState(false),
    [running, setRunning] = useState(false),
    [status, setStatus] = useState<any>();
  useEffect(() => {
    api.get("/equipment").then((r) => setEq(r.data));
  }, []);
  const selectedAsset = eq.find((asset) => asset.id === selected);
  async function generateDemoEvidence() {
    if (!selectedAsset) {
      setErr("Select an equipment asset before generating demo evidence.");
      return;
    }
    setErr("");
    setGenerating(true);
    try {
      const [rgb, thermal] = await Promise.all([
        demoEvidenceFile(selectedAsset, "rgb"),
        demoEvidenceFile(selectedAsset, "thermal"),
      ]);
      setFiles({ rgb, thermal });
    } catch (x: any) {
      setErr(x.message || "Unable to generate demo evidence.");
    } finally {
      setGenerating(false);
    }
  }
  const step = !selected
    ? 0
    : !files.rgb
      ? 1
      : !files.thermal
        ? 2
        : !env.ambient_temperature || !env.humidity
          ? 3
          : 4;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setRunning(true);
    let polling: ReturnType<typeof setInterval> | undefined;
    try {
      const id = (
        await api.post("/inspections", {
          equipment_id: selected,
          ...env,
          ambient_temperature: +env.ambient_temperature,
          humidity: +env.humidity,
        })
      ).data.id;
      setStatus({ id, current: "input_acquired", stages: {} });
      const f = new FormData();
      f.append("rgb", files.rgb);
      f.append("thermal", files.thermal);
      await api.post(`/inspections/${id}/images`, f);
      polling = setInterval(
        () =>
          api
            .get(`/inspections/${id}/processing-status`, { params: { _fresh: Date.now() } })
            .then((r) => setStatus({ id, ...r.data })),
        150,
      );
      await api.post(`/inspections/${id}/analyze`);
      clearInterval(polling);
      setTimeout(() => nav(`/app/inspections/${id}`), 400);
    } catch (x: any) {
      if (polling) clearInterval(polling);
      setErr(x.response?.data?.detail || "Analysis failed.");
      setStatus(null);
      setRunning(false);
    }
  }
  if (status) return <Processing s={status} />;
  return (
    <Page
      eye="MULTISPECTRAL INSPECTION WORKSTATION"
      title="Acquire a new evidence chain"
      sub="RGB structure + thermal pattern + environmental context → operator review"
    >
      <div className="stepper">
        {["Equipment", "RGB", "Thermal", "Context", "Analyse"].map((x, i) => (
          <div className={i < step ? "complete" : i === step ? "active" : ""}>
            <span>0{i + 1}</span>
            <b>{x}</b>
            <i />
          </div>
        ))}
      </div>
      <form className="inspection-workstation" onSubmit={submit}>
        <Glass>
          <Title eye="01 / EQUIPMENT" title="Select the infrastructure asset" />
          <select
            required
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Choose an asset</option>
            {eq.map((x) => (
              <option value={x.id}>
                {x.equipment_name} · {x.equipment_type}
              </option>
            ))}
          </select>
        </Glass>
        <div className="upload-grid">
          <Upload
            kind="rgb"
            file={files.rgb}
            set={(f: any) => setFiles({ ...files, rgb: f })}
            onGenerate={generateDemoEvidence}
            generateDisabled={!selected || generating}
            generating={generating}
          />
          <Upload
            kind="thermal"
            file={files.thermal}
            set={(f: any) => setFiles({ ...files, thermal: f })}
            onGenerate={generateDemoEvidence}
            generateDisabled={!selected || generating}
            generating={generating}
          />
        </div>
        <Glass className="environment-array">
          <Title
            eye="04 / ENVIRONMENTAL CONTEXT ARRAY"
            title="Describe acquisition conditions"
          />
          <div className="environment-layout">
            <div className="environment-fields">
              {[
                ["temp", "Ambient °C", "ambient_temperature"],
                ["weather", "Humidity %", "humidity"],
              ].map((x) => (
                <Field l={x[1]}>
                  <input
                    required
                    type="number"
                    value={env[x[2]]}
                    onChange={(e) => setEnv({ ...env, [x[2]]: e.target.value })}
                  />
                </Field>
              ))}
              {[
                ["Weather", "weather", ["Sunny", "Cloudy", "Rainy", "Other"]],
                ["Season", "season", ["Summer", "Monsoon", "Winter", "Spring"]],
                [
                  "Time of day",
                  "time_of_day",
                  ["Morning", "Afternoon", "Evening", "Night"],
                ],
                [
                  "Sun exposure",
                  "sun_exposure",
                  ["", "Low", "Moderate", "High"],
                ],
              ].map((x) => (
                <Field l={String(x[0])}>
                  <select
                    value={env[String(x[1])]}
                    onChange={(e) =>
                      setEnv({ ...env, [String(x[1])]: e.target.value })
                    }
                  >
                    {(x[2] as string[]).map((v) => (
                      <option>{v || "Not specified"}</option>
                    ))}
                  </select>
                </Field>
              ))}
            </div>
            <div className="env-snapshot">
              <span className="eyebrow">ENVIRONMENT SNAPSHOT</span>
              <b>{env.ambient_temperature || "—"}°C</b>
              <b>{env.humidity || "—"}%</b>
              <span>{env.weather}</span>
              <span>{env.time_of_day}</span>
              <i />
            </div>
          </div>
        </Glass>
        {err && <div className="error-panel">△ {err}</div>}
        <Btn type="submit" disabled={step < 4 || running} loading={running}>
          RUN MULTISPECTRAL ANALYSIS <I n="arrow" />
        </Btn>
      </form>
    </Page>
  );
}
function Upload({
  kind,
  file,
  set,
  onGenerate,
  generateDisabled,
  generating,
}: {
  kind: string;
  file?: File;
  set: (f?: File) => void;
  onGenerate: () => void;
  generateDisabled: boolean;
  generating: boolean;
}) {
  const [p, setP] = useState("");
  useEffect(() => {
    if (!file) {
      setP("");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setP(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  function pick(f?: File) {
    set(f);
    setP(f ? URL.createObjectURL(f) : "");
  }
  return (
    <Glass className={`upload-zone ${kind} ${file ? "selected" : ""}`}>
      {p ? (
        <img src={p} />
      ) : (
        <div className="upload-illustration">
          <I n={kind === "rgb" ? "equipment" : "temp"} />
          <i />
          <i />
        </div>
      )}
      <span className="eyebrow">
        {kind === "rgb" ? "02 / RGB EVIDENCE" : "03 / THERMAL EVIDENCE"}
      </span>
      <h3>{file?.name || `${kind.toUpperCase()} image stream`}</h3>
      <p>
        {file
          ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ${file.type}`
          : "JPEG or PNG · max 10 MB"}
      </p>
      <label className="drop-action">
        <I n="upload" />
        {file ? "Replace image" : "Select image"}
        <input
          type="file"
          accept="image/jpeg,image/png"
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </label>
      <button
        className="generate-demo"
        type="button"
        disabled={generateDisabled}
        onClick={onGenerate}
      >
        <I n="ai" />
        {generating ? "Generating evidence…" : "Generate AI demo evidence"}
      </button>
      {!file && <small className="generated-note">For workflow testing only — not a field capture.</small>}
      {file && (
        <button type="button" onClick={() => pick()}>
          Remove
        </button>
      )}
    </Glass>
  );
}
function Processing({ s }: { s: any }) {
  return (
    <Page
      eye="ANALYSIS WORKSTATION"
      title="Thermal intelligence pipeline"
      sub={`Inspection ${s.id} · actual backend stage state`}
    >
      <Glass className="processing-core">
        <Fusion />
        <div className="pipeline-stages">
          {PIPE.map((x, i) => {
            const z = s.stages?.[x[0]] || "pending";
            return (
              <div className={z}>
                <span>{z === "complete" ? "✓" : `0${i + 1}`}</span>
                <b>{x[1]}</b>
                <small>{z.toUpperCase()}</small>
                <i />
              </div>
            );
          })}
        </div>
        <p>No fabricated completion percentages are shown.</p>
      </Glass>
    </Page>
  );
}
function History() {
  const [items, setItems] = useState<any[]>([]),
    [filter, setFilter] = useState({ risk: "", search: "" });
  useEffect(() => {
    const t = setTimeout(
      () =>
        api
          .get("/inspections", {
            params: Object.fromEntries(
              Object.entries(filter).filter(([, v]) => v),
            ),
          })
          .then((r) => setItems(r.data)),
      200,
    );
    return () => clearTimeout(t);
  }, [filter]);
  return (
    <Page
      eye="TRACEABLE EVIDENCE HISTORY"
      title="Inspection Records"
      sub="Search every preserved multimodal inspection."
    >
      <Glass className="filter-bar">
        <label>
          ⌕
          <input
            placeholder="Search equipment…"
            value={filter.search}
            onChange={(e) => setFilter({ ...filter, search: e.target.value })}
          />
        </label>
        <select
          value={filter.risk}
          onChange={(e) => setFilter({ ...filter, risk: e.target.value })}
        >
          <option value="">All risk levels</option>
          {RISKS.map((x) => (
            <option>{x}</option>
          ))}
        </select>
      </Glass>
      {items.length ? (
        <div className="history-grid">
          {items.map((x) => (
            <Link to={`/app/inspections/${x.id}`}>
              <Glass className="history-card">
                <div className="history-thumb">
                  {x.thumbnail ? (
                    <img src={ORIGIN + x.thumbnail} />
                  ) : (
                    <I n="inspect" />
                  )}
                  <Badge risk={x.prediction?.risk_level} />
                </div>
                <span className="eyebrow">{date(x.created_at)}</span>
                <h3>{x.equipment_name}</h3>
                <p>
                  {x.equipment_type} · {x.model_version || "Draft"}
                </p>
                {x.environment && (
                  <div className="env-row">
                    <span>{x.environment.ambient_temperature}°C</span>
                    <span>{x.environment.humidity}% RH</span>
                    <span>{x.environment.weather}</span>
                  </div>
                )}
              </Glass>
            </Link>
          ))}
        </div>
      ) : (
        <Glass>
          <Empty
            title="No matching inspection records"
            copy="Adjust filters or run a new inspection."
            action={
              <Link className="btn primary" to="/app/inspect">
                Run inspection
              </Link>
            }
          />
        </Glass>
      )}
    </Page>
  );
}
function Detail() {
  const { id } = useParams();
  const [d, setD] = useState<any>(),
    [tab, setTab] = useState("RGB"),
    [compare, setCompare] = useState(50),
    [report, setReport] = useState(""),
    [asking, setAsking] = useState(false);
  useEffect(() => {
    api.get(`/inspections/${id}`).then((r) => setD(r.data));
  }, [id]);
  useEffect(() => {
    if (!d || d.prediction || d.status === "COMPLETED") return;
    const poll = setInterval(() => api.get(`/inspections/${id}`, { params: { _fresh: Date.now() } }).then((r) => setD(r.data)), 500);
    return () => clearInterval(poll);
  }, [id, d?.prediction, d?.status]);
  if (!d)
    return (
      <Page
        eye="THERMAL EVIDENCE REVIEW"
        title="Linking evidence chain"
        sub="Retrieving image, model and context records…"
      >
        <div className="skeleton hero-skeleton" />
      </Page>
    );
  if (!d.prediction)
    return <Processing s={{ id: d.id, current: d.status?.toLowerCase() || "acquiring", stages: {} }} />;
  const p = d.prediction,
    imgs = Object.fromEntries(d.images.map((x: any) => [x.type, x]));
  async function ask() {
    setAsking(true);
    try {
      setReport(
        (
          await api.post(`/ai/inspections/${id}`, null, {
            params: { question: "Explain this inspection result." },
          })
        ).data.response,
      );
    } finally {
      setAsking(false);
    }
  }
  return (
    <Page
      eye="THERMAL EVIDENCE REVIEW WORKSTATION"
      title={d.equipment.name}
      sub={`Inspection ${d.id} · ${date(d.completed_at || d.created_at)}`}
    >
      <div className={`result-hero ${tone(p?.risk_level)}`}>
        <div
          className="risk-ring"
          style={{ "--score": `${(p?.confidence || 0) * 360}deg` } as any}
        >
          <span>
            {p ? (p.confidence * 100).toFixed(1) + "%" : "—"}
            <small>HEURISTIC SCORE</small>
          </span>
        </div>
        <div>
          <span className="eyebrow">CONTEXTUAL RISK ASSESSMENT</span>
          <h2>{label(p?.risk_level)}</h2>
          <p>{d.recommended_action}</p>
        </div>
        <div className="trace-panel">
          <span>
            MODEL MODE<b>BASELINE HEURISTIC</b>
          </span>
          <span>
            VALIDATION<b>UNVALIDATED</b>
          </span>
          <span>
            REGISTRATION
            <b>{p?.explanation_metadata?.registration_status || "—"}</b>
          </span>
        </div>
      </div>
      {p && (
        <div className="result-layout">
          <Glass className="evidence-workspace">
            <div className="evidence-tabs">
              {["RGB", "THERMAL", "FUSED", "GRADCAM", "COMPARE"].map((x) => (
                <button
                  className={tab === x ? "active" : ""}
                  onClick={() => setTab(x)}
                >
                  {x === "GRADCAM" ? "ATTRIBUTION" : x}
                </button>
              ))}
            </div>
            <div className="evidence-viewer">
              {tab === "COMPARE" && imgs.RGB && imgs.GRADCAM ? (
                <div className="compare">
                  <img src={ORIGIN + imgs.RGB.url} />
                  <img
                    src={ORIGIN + imgs.GRADCAM.url}
                    style={{ clipPath: `inset(0 0 0 ${compare}%)` }}
                  />
                  <i style={{ left: `${compare}%` }} />
                  <input
                    type="range"
                    value={compare}
                    onChange={(e) => setCompare(+e.target.value)}
                  />
                </div>
              ) : imgs[tab] ? (
                <motion.img
                  key={tab}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  src={ORIGIN + imgs[tab].url}
                />
              ) : (
                <Empty
                  title="Evidence unavailable"
                  copy="This artifact was not generated."
                />
              )}
            </div>
            <p>
              Model-attributed regions support review; they are not confirmed
              fault locations.
            </p>
          </Glass>
          <Glass className="probability-panel">
            <Title eye="MODEL OUTPUT" title="Risk spectrum" />
            {Object.entries(p.probabilities).map(([k, v]: any) => (
              <div className="probability">
                <span>{label(k)}</span>
                <i>
                  <motion.b
                    initial={{ width: 0 }}
                    animate={{ width: `${v * 100}%` }}
                    style={{ background: COLORS[RISKS.indexOf(k)] }}
                  />
                </i>
                <strong>{(v * 100).toFixed(1)}%</strong>
              </div>
            ))}
          </Glass>
          <Glass className="environment-panel">
            <Title eye="ENVIRONMENT EFFECT PANEL" title="Submitted context" />
            <div className="environment-chips">
              {[
                ["temp", "Ambient", d.environment.ambient_temperature + "°C"],
                ["weather", "Humidity", d.environment.humidity + "%"],
                ["weather", "Weather", d.environment.weather],
                ["time", "Time", d.environment.time_of_day],
              ].map((x) => (
                <div>
                  <I n={x[0]} />
                  <span>
                    <small>{x[1]}</small>
                    <b>{x[2]}</b>
                  </span>
                </div>
              ))}
            </div>
          </Glass>
          <Glass className="action-card">
            <span className="eyebrow">RECOMMENDED REVIEW</span>
            <h2>{d.recommended_action}</h2>
            <p>
              Deterministically mapped from risk class. Engineering review
              remains authoritative.
            </p>
            <Badge risk={p.risk_level} />
          </Glass>
          <Glass className="ai-report">
            <Title
              eye="EVOTHERM AI ANALYST"
              title="Inspection-grounded explanation"
            />
            {report ? (
              <p>{report}</p>
            ) : (
                <Btn onClick={ask} loading={asking}>
                Explain this inspection <I n="arrow" />
              </Btn>
            )}
          </Glass>
          <Feedback id={d.id} existing={d.feedback} />
        </div>
      )}
    </Page>
  );
}
function Feedback({ id, existing }: { id: string; existing: any[] }) {
  const [saved, setSaved] = useState(existing.length > 0);
  async function go(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const x: any = Object.fromEntries(new FormData(e.currentTarget));
    x.verified = !!x.verified;
    await api.post(`/inspections/${id}/feedback`, x);
    setSaved(true);
  }
  return (
    <Glass className="feedback-card">
      <Title eye="OPERATOR FEEDBACK" title="Close the evidence loop" />
      {saved ? (
        <p>✓ Follow-up recorded for this inspection.</p>
      ) : (
        <form onSubmit={go}>
          <select name="operator_status">
            <option>Reviewed</option>
            <option>Escalated</option>
          </select>
          <input name="actual_issue" placeholder="Issue confirmed?" />
          <input required name="action_taken" placeholder="Action taken" />
          <textarea name="notes" placeholder="Notes" />
          <label>
            <input type="checkbox" name="verified" /> Verified
          </label>
          <Btn type="submit">Record feedback</Btn>
        </form>
      )}
    </Glass>
  );
}
function Risk() {
  const [d, setD] = useState<any>();
  useEffect(() => {
    api.get("/risk/overview").then((r) => setD(r.data));
  }, []);
  return (
    <Page
      eye="RISK INTELLIGENCE LAYER"
      title="Risk Monitor"
      sub="Historical inspection signals—not a live telemetry feed."
    >
      {d && !d.timeline.length ? (
        <Glass>
          <Empty
            title="No active risk signals"
            copy="Run an inspection to populate the risk intelligence layer."
            action={
              <Link className="btn primary" to="/app/inspect">
                Run inspection
              </Link>
            }
          />
        </Glass>
      ) : (
        d && (
          <div className="risk-layout">
            <Glass className="risk-radar">
              <Title eye="ASSET RISK FIELD" title="Latest equipment state" />
              <Radar equipment={d.equipment} />
            </Glass>
            <Glass>
              <Title eye="RISK DISTRIBUTION" title="Recorded assessments" />
              <div className="risk-bars">
                {RISKS.map((x, i) => (
                  <div>
                    <span>{label(x)}</span>
                    <i>
                      <b
                        style={{
                          width: `${Math.max(3, (d.distribution[x] / d.timeline.length) * 100)}%`,
                          background: COLORS[i],
                        }}
                      />
                    </i>
                    <strong>{d.distribution[x]}</strong>
                  </div>
                ))}
              </div>
            </Glass>
            <Glass className="risk-alerts">
              <Title eye="RECENT ALERT EVENTS" title="Review queue" />
              {d.alerts.length ? (
                d.alerts.map((x: any) => (
                  <Link to={`/app/inspections/${x.inspection_id}`}>
                    <Badge risk={x.severity} />
                    <p>{x.message}</p>
                    <small>{date(x.created_at)}</small>
                  </Link>
                ))
              ) : (
                <p>No alert events recorded.</p>
              )}
            </Glass>
          </div>
        )
      )}
    </Page>
  );
}
function Radar({ equipment }: { equipment: any[] }) {
  return (
    <div className="radar">
      <svg viewBox="0 0 400 300">
        <circle cx="200" cy="150" r="120" />
        <circle cx="200" cy="150" r="80" />
        <circle cx="200" cy="150" r="40" />
        <motion.path
          d="M200 150L200 30A120 120 0 011303 89Z"
          animate={{ rotate: 360 }}
          transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "200px 150px" }}
        />
        {equipment.slice(0, 8).map((x: any, i: number) => {
          const a = (i / Math.max(1, equipment.length)) * 6.28,
            r = 55 + (i % 3) * 28,
            cx = 200 + Math.cos(a) * r,
            cy = 150 + Math.sin(a) * r;
          return (
            <g>
              <circle
                className={tone(x.latest?.risk_level)}
                cx={cx}
                cy={cy}
                r="7"
              />
              <text x={cx + 10} y={cy}>
                {x.name}
              </text>
            </g>
          );
        })}
      </svg>
      <span>NON-GEOGRAPHIC ASSET SIGNAL FIELD</span>
    </div>
  );
}
function Lab() {
  const [s, setS] = useState<any>(),
    [e, setE] = useState<any[]>([]);
  useEffect(() => {
    api.get("/models/status").then((r) => setS(r.data));
    api.get("/experiments").then((r) => setE(r.data));
  }, []);
  return (
    <Page
      eye="EVOLUTIONARY MODEL LAB"
      title="Compare. Optimise. Validate."
      sub="Model lineage and multi-objective research workspace."
    >
      <div className="lab-grid">
        <Glass className="active-model">
          <span className="eyebrow">ACTIVE MODEL</span>
          <h2>{s?.version || "Loading registry…"}</h2>
          <dl>
            <dt>MODE</dt>
            <dd>{s?.mode?.toUpperCase()}</dd>
            <dt>VALIDATION</dt>
            <dd>UNVALIDATED</dd>
            <dt>BACKBONE</dt>
            <dd>Deterministic heuristic</dd>
            <dt>CHECKPOINT</dt>
            <dd>Not loaded</dd>
          </dl>
        </Glass>
        <Glass className="architecture">
          <Title eye="MULTIMODAL ARCHITECTURE" title="Configured signal path" />
          <Fusion />
        </Glass>
        <Glass className="comparison">
          <Title eye="MODEL COMPARISON" title="Evaluation readiness" />
          {[
            "RGB-only",
            "Thermal-only",
            "Fusion",
            "Fusion + Environment",
            "NSGA-II Optimised",
          ].map((x, i) => (
            <div>
              <span>0{i + 1}</span>
              <b>{x}</b>
              <small>NOT EVALUATED</small>
            </div>
          ))}
        </Glass>
        <Glass className="nsga">
          <Title
            eye="NSGA-II PARETO FRONT"
            title={
              e.length ? "Experiment candidates" : "No optimisation run yet"
            }
          />
          <div className="pareto-grid">
            <svg viewBox="0 0 100 60">
              <path d="M10,13C34,17 48,29 61,43C72,53 85,55 94,57" />
            </svg>
          </div>
          <p>Run on a labelled validation dataset to populate the frontier.</p>
          <code>python -m ml_training.optimize</code>
        </Glass>
      </div>
    </Page>
  );
}
function AI() {
  const [items, setItems] = useState<any[]>([]),
    [id, setId] = useState(""),
    [q, setQ] = useState("Explain this inspection result."),
    [r, setR] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/inspections").then((x) => {
      const z = x.data.filter((i: any) => i.prediction);
      setItems(z);
      setId(z[0]?.id || "");
    });
  }, []);
  async function ask() {
    setBusy(true);
    try {
      setR(
        (
          await api.post(`/ai/inspections/${id}`, null, {
            params: { question: q },
          })
        ).data.response,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Page
      eye="EVOTHERM / AI COPILOT"
      title="EvoTherm AI Analyst"
      sub="Inspection-grounded explanations with deterministic fallback."
    >
      <div className="ai-console">
        <Glass>
          <Title eye="INSPECTION CONTEXT" title="Select an evidence record" />
          <select value={id} onChange={(e) => setId(e.target.value)}>
            <option value="">Choose completed inspection</option>
            {items.map((x) => (
              <option value={x.id}>
                {x.equipment_name} · {label(x.prediction.risk_level)}
              </option>
            ))}
          </select>
          <div className="context-lock">✓ ONLY SELECTED INSPECTION DATA</div>
        </Glass>
        <Glass className="ai-command">
          <div className="command-orb">
            <I n="ai" />
            <i />
            <i />
          </div>
          <Title
            eye="ASK EVOTHERM"
            title="Ask about equipment, evidence or risk"
          />
          <div className="suggested-prompts">
            {[
              "Explain this risk result.",
              "Summarize the evidence.",
              "How might environment influence interpretation?",
              "Create a maintenance review summary.",
            ].map((x) => (
              <button onClick={() => setQ(x)}>{x}</button>
            ))}
          </div>
          <textarea value={q} onChange={(e) => setQ(e.target.value)} />
          <Btn onClick={ask} disabled={!id || busy}>
            {busy ? "Reviewing context…" : "Generate intelligence report"}
          </Btn>
        </Glass>
        <Glass className="ai-output">
          <Title
            eye="INTELLIGENCE REPORT"
            title={r ? "Operator guidance" : "Awaiting a command"}
          />
          {r ? (
            <p>{r}</p>
          ) : (
            <Empty
              title="No report generated"
              copy="Choose an inspection and submit a grounded question."
            />
          )}
        </Glass>
      </div>
    </Page>
  );
}
function Gauge({
  label,
  value,
  max = 100,
  unit = "",
  tone = "hot",
}: {
  label: string;
  value: number;
  max?: number;
  unit?: string;
  tone?: string;
}) {
  const safe = Math.max(0, Math.min(1, value / max));
  return (
    <motion.div
      className={`hud-gauge ${tone}`}
      initial={{ "--fill": "0deg" } as any}
      animate={{ "--fill": `${safe * 260 - 130}deg` } as any}
      transition={{ duration: 1.15, ease: [0.2, 0.8, 0.2, 1] }}
    >
      <div className="gauge-arc">
        <i />
        <span>
          <b>
            {value.toFixed(value % 1 ? 1 : 0)}
            <small>{unit}</small>
          </b>
          <em>{label}</em>
        </span>
      </div>
      <div className="gauge-scale">
        <i>0</i>
        <i>{max}</i>
      </div>
    </motion.div>
  );
}
function FusionCore() {
  return (
    <div className="fusion-core">
      <i />
      <i />
      <i />
      <span>
        <I n="model" />
      </span>
      <b>
        FUSION
        <br />
        ENGINE
      </b>
    </div>
  );
}
function Landing2() {
  const [scanner, setScanner] = useState(52);
  return (
    <div className="landing racing">
      <Bg />
      <nav className="landing-nav">
        <Brand />
        <div>
          <a href="#story">Engine</a>
          <a href="#gauge">Risk index</a>
          <a href="#preview">System</a>
          <Link to="/login">Sign in</Link>
          <Link className="btn primary engine-cta" to="/register">
            Start inspection <I n="arrow" />
          </Link>
        </div>
      </nav>
      <section className="landing-hero race-hero">
        <div className="hero-copy">
          <span className="eyebrow">
            THERMAL INTELLIGENCE FOR INFRASTRUCTURE
          </span>
          <h1>
            SEE HEAT.
            <br />
            <em>UNDERSTAND CONTEXT.</em>
          </h1>
          <p>
            Contextual thermal evidence for precision infrastructure review.
            RGB, thermal patterns and environmental telemetry converge in one
            operator-controlled system.
          </p>
          <div className="hero-actions">
            <Link className="btn primary engine-cta" to="/register">
              Start inspection <I n="arrow" />
            </Link>
            <a className="btn secondary" href="#story">
              Explore the system
            </a>
          </div>
          <small className="demo-note">
            DEMONSTRATION VISUALIZATION · NOT LIVE EQUIPMENT DATA
          </small>
        </div>
        <div
          className="engine-visual"
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            setScanner(
              Math.max(8, Math.min(92, ((e.clientX - r.left) / r.width) * 100)),
            );
          }}
        >
          <div className="hud-reticle" style={{ left: `${scanner}%` }} />
          <div className="engine-rgb">
            <TechnicalAsset />
          </div>
          <div
            className="engine-thermal"
            style={{ clipPath: `inset(0 0 0 ${scanner}%)` }}
          >
            <ThermalAsset />
          </div>
          <div className="engine-scanner" style={{ left: `${scanner}%` }} />
          <div className="hero-tel t1">
            <span>THERMAL CORE</span>
            <b>62.4°</b>
          </div>
          <div className="hero-tel t2">
            <span>AMBIENT</span>
            <b>31.2°</b>
          </div>
          <div className="hero-tel t3">
            <span>RISK</span>
            <b>ELEVATED</b>
          </div>
          <div className="hero-tel t4">
            <span>MODEL</span>
            <b>FUSION</b>
          </div>
        </div>
      </section>
      <div className="telemetry-ticker">
        <div>
          THERMAL ENGINE <b>ONLINE</b> <i /> EVIDENCE CORE <b>READY</b> <i />{" "}
          MODEL MODE <b>BASELINE</b> <i /> OPERATOR CONTROL <b>ACTIVE</b> <i />{" "}
          THERMAL ENGINE <b>ONLINE</b> <i /> EVIDENCE CORE <b>READY</b>
        </div>
      </div>
      <section id="story" className="scroll-story">
        <div className="story-copy">
          <span className="eyebrow">EVIDENCE DOESN'T EXIST IN ISOLATION</span>
          <h2>
            Heat is a signal.
            <br />
            <em>Context makes it useful.</em>
          </h2>
          <p>
            Scroll through the evidence chain: technical structure, relative
            heat, environmental telemetry, model attribution and operator
            action.
          </p>
          <div className="story-steps">
            {[
              "RGB SEES STRUCTURE",
              "THERMAL SEES HEAT",
              "CONTEXT EXPLAINS WHY",
              "AI CONNECTS SIGNALS",
              "YOU GET EVIDENCE",
            ].map((x, i) => (
              <span>
                <b>0{i + 1}</b>
                {x}
              </span>
            ))}
          </div>
        </div>
        <div className="story-screen">
          <TechnicalAsset />
          <div className="story-heat" />
          <div className="story-context">
            <span>AMBIENT 42°C</span>
            <span>HUMIDITY 31%</span>
            <span>SUN HIGH</span>
          </div>
          <FusionCore />
        </div>
      </section>
      <section className="landing-section telemetry-section">
        <Title
          eye="FROM SIGNAL TO DECISION"
          title="A risk index, not a generic alert."
        />
        <div id="gauge" className="landing-gauges">
          <Gauge label="RISK INDEX" value={82} tone="risk" />
          <Gauge label="THERMAL DEVIATION" value={62.4} max={90} unit="°" />
          <Gauge label="HEURISTIC STRENGTH" value={86.4} unit="%" tone="cool" />
        </div>
        <p className="demo-note center">
          Illustrative landing-page instruments. Authenticated pages render
          values derived from actual inspection records.
        </p>
      </section>
      <section className="landing-section">
        <Title
          eye="MULTISPECTRAL ENGINE"
          title="Power flows into one explainable decision path."
        />
        <div className="power-flow">
          <span>RGB</span>
          <i />
          <span>THERMAL</span>
          <i />
          <span>ENVIRONMENT</span>
          <div>
            <FusionCore />
          </div>
          <i />
          <strong>
            RISK
            <br />
            EVIDENCE
          </strong>
        </div>
      </section>
      <section className="landing-section">
        <Title
          eye="INTERACTIVE CAPABILITIES"
          title="Built as a performance machine, not an admin template."
        />
        <div className="race-bento">
          <Glass className="fusion-card">
            <FusionCore />
            <h3>Multispectral Fusion</h3>
            <p>Technical, thermal and environmental streams converge.</p>
          </Glass>
          <Glass className="mini-gauge">
            <Gauge label="RISK" value={58} />
          </Glass>
          <Glass className="heat-card">
            <ThermalAsset />
            <h3>Grad-CAM Evidence</h3>
          </Glass>
          <Glass className="environment-card">
            <div className="weather-wheel">☼</div>
            <b>32.5°</b>
            <span>AMBIENT · 55% RH</span>
          </Glass>
          <Glass className="pareto-card">
            <div className="pareto-grid">
              <svg viewBox="0 0 100 60">
                <path d="M10,13C34,17 48,29 61,43C72,53 85,55 94,57" />
              </svg>
            </div>
            <h3>Evolutionary AI</h3>
          </Glass>
          <Glass className="stream-card">
            <span>AI COPILOT</span>
            <i />
            <i />
            <i />
            <p>Grounded intelligence report ready.</p>
          </Glass>
        </div>
      </section>
      <section id="preview" className="landing-section">
        <Title
          eye="THE PRODUCT, IN MOTION"
          title="Cinematic outside. Functional thermal cockpit inside."
        />
        <div className="product-preview">
          <div className="preview-bar">
            <i />
            <i />
            <i />
            <span>EVOTHERM / COMMAND CENTER</span>
          </div>
          <div className="preview-content">
            <Gauge label="RISK" value={34} />
            <div className="preview-lines">
              <b>INFRASTRUCTURE RISK OVERVIEW</b>
              <i />
              <i />
              <i />
              <i />
            </div>
            <FusionCore />
          </div>
        </div>
      </section>
      <section className="landing-cta final">
        <span className="eyebrow">TURN HEAT INTO EVIDENCE</span>
        <h2>
          Run your first multispectral
          <br />
          <em>infrastructure inspection.</em>
        </h2>
        <Link className="btn primary engine-cta" to="/register">
          Enter EvoTherm <I n="arrow" />
        </Link>
      </section>
    </div>
  );
}
function TechnicalAsset() {
  return (
    <div className="technical-asset">
      <div className="asset-grid" />
      <i />
      <i />
      <i />
      <b />
      <span />
      <em>STRUCTURAL SIGNAL / LOCKED</em>
    </div>
  );
}
function ThermalAsset() {
  return (
    <div className="thermal-asset">
      <TechnicalAsset />
      <div className="hotspot a" />
      <div className="hotspot b" />
      <div className="hotspot c" />
    </div>
  );
}
function Dashboard2() {
  const [d, setD] = useState<any>();
  useEffect(() => {
    api.get("/dashboard").then((r) => setD(r.data));
  }, []);
  const runs = d?.inspection_count || 0,
    warnings = d?.active_warnings || 0,
    high = d?.high_risk_events || 0;
  const latest = d?.recent?.[0];
  const thermal = latest?.prediction?.explanation_metadata
    ?.thermal_intensity_p95
    ? Math.round(
        latest.prediction.explanation_metadata.thermal_intensity_p95 * 90,
      )
    : 0;
  const confidence = latest?.confidence
    ? Math.round(latest.confidence * 100)
    : 0;
  return (
    <Page
      eye="EVOTHERM / COMMAND CENTER"
      title="Thermal Intelligence Cockpit"
      sub="Infrastructure signal, evidence and operator readiness."
      action={
        <Link className="btn primary engine-cta" to="/app/inspect">
          Start inspection <I n="arrow" />
        </Link>
      }
    >
      <div className="cockpit-ticker">
        <span>
          ASSETS <b>{d?.equipment_count ?? "—"}</b>
        </span>
        <i />{" "}
        <span>
          INSPECTIONS <b>{runs}</b>
        </span>
        <i />
        <span>
          WARNINGS <b>{warnings}</b>
        </span>
        <i />
        <span>
          HIGH RISK <b>{high}</b>
        </span>
        <i />
        <span>
          MODEL <b>BASELINE</b>
        </span>
        <i />
        <span>
          SYSTEM <b>READY</b>
        </span>
      </div>
      <section className="cockpit-cluster">
        <Glass className="primary-gauge">
          <Gauge
            label="RISK INDEX"
            value={
              high
                ? Math.min(100, 60 + high * 10)
                : latest?.confidence
                  ? Math.round(latest.confidence * 100)
                  : 0
            }
            tone="risk"
          />
          <div>
            <span className="eyebrow">
              SYSTEM / {high ? "ATTENTION" : "NOMINAL"}
            </span>
            <h2>{latest ? label(latest.risk_level) : "STANDING BY"}</h2>
            <p>
              {latest
                ? "Latest actual inspection signal"
                : "Create equipment and run an inspection to energise the cockpit."}
            </p>
          </div>
        </Glass>
        <Glass className="minor-gauge">
          <Gauge label="THERMAL" value={thermal} max={90} unit="°" />
          <small>
            {latest ? "P95 derived intensity" : "Awaiting thermal evidence"}
          </small>
        </Glass>
        <Glass className="minor-gauge cool">
          <Gauge label="HEURISTIC" value={confidence} unit="%" tone="cool" />
          <small>
            {latest ? "Latest inspection score" : "Model baseline ready"}
          </small>
        </Glass>
        <Glass className="status-panel">
          <Title eye="ENGINE STATUS" title="Signal readiness" />
          {[
            ["THERMAL ENGINE", "ONLINE"],
            ["DATABASE", "CONNECTED"],
            ["MODEL", "BASELINE"],
            ["EVIDENCE CORE", "READY"],
          ].map((x) => (
            <div>
              <i />
              <span>{x[0]}</span>
              <b>{x[1]}</b>
            </div>
          ))}
        </Glass>
      </section>
      {d && runs === 0 ? (
        <Glass>
          <Empty
            title="No inspection signal"
            copy="The system is standing by. Register an asset and initiate a diagnostic run."
            action={
              <Link className="btn primary" to="/app/inspect">
                Start inspection
              </Link>
            }
          />
        </Glass>
      ) : (
        d && <DashboardData d={d} />
      )}
    </Page>
  );
}
export default function App() {
  const [u, setU] = useState<User | null>(null),
    [check, setCheck] = useState(true);
  useEffect(() => {
    const t = localStorage.getItem("etg_token");
    if (!t) {
      setCheck(false);
      return;
    }
    api
      .get("/auth/me")
      .then((r) => setU(r.data))
      .catch(() => localStorage.removeItem("etg_token"))
      .finally(() => setCheck(false));
  }, []);
  useEffect(() => {
    if (u) void warmAppData();
  }, [u]);
  if (check)
    return (
      <div className="boot">
        <Bg />
        <Brand />
        <span>Linking intelligence workspace…</span>
      </div>
    );
  return (
    <div
      onClickCapture={(event) => {
        const button = (event.target as HTMLElement).closest("button");
        if (!button || button.disabled) return;
        button.classList.add("button-feedback");
        window.setTimeout(() => button.classList.remove("button-feedback"), 550);
      }}
    >
      <Routes>
      <Route path="/" element={<Landing2 />} />
      <Route path="/login" element={<Auth onAuth={setU} />} />
      <Route path="/register" element={<Auth register onAuth={setU} />} />
      <Route
        path="/app/*"
        element={
          u ? (
            <Shell
              user={u}
              out={() => {
                localStorage.removeItem("etg_token");
                setU(null);
              }}
            />
          ) : (
            <Auth onAuth={setU} />
          )
        }
      />
      </Routes>
    </div>
  );
}
