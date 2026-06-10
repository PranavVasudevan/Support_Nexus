import React, { useState, useEffect, useRef, useCallback } from "react";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ── Auth token helpers ─────────────────────────────────────────
const TOKEN_KEY = "ticketai_token";
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); }

// fetch wrapper that prepends the API base and attaches the JWT.
function authFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const tok = getToken();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  return fetch(`${API}${path}`, { ...opts, headers });
}

// (legacy hardcoded USERS removed — auth is now server-side via /api/auth)

const SELF_HELP = {
  VPN:              ["Disconnect and reconnect the VPN client","Restart the VPN service from Windows Services","Verify your internet works without VPN first","Re-import your VPN profile after clearing the cache"],
  Password_Reset:   ["Use the self-service portal at portal.company.com/reset","Check your registered email for a reset link","Accounts auto-unlock after 30 minutes of no attempts","Ask your manager for an emergency temporary password"],
  Network:          ["Restart your router and modem — unplug for 30 seconds","Try an ethernet cable instead of WiFi","Run ipconfig /flushdns in Command Prompt","Check if colleagues nearby have the same issue"],
  Hardware:         ["Restart the device fully, not sleep or hibernate","Check all cable connections are firmly seated","Run the built-in hardware diagnostic tool","Open Device Manager and look for warning icons"],
  Software_Install: ["Run the installer as Administrator — right-click, Run as admin","Temporarily disable antivirus during installation","Confirm you have at least 2 GB of free disk space","Download a fresh installer copy in case it is corrupted"],
  Email:            ["Check your spam and junk folders first","Verify IMAP and SMTP port settings in your client","Clear the Outlook cache via File, Account Settings, Data Files","Try webmail to determine if the issue is client or server"],
  Printer:          ["Remove and re-add the printer from Settings","Clear the print queue by restarting the Print Spooler service","Reinstall the printer driver from the manufacturer website","Print a test page directly from the printer settings"],
  Access_Request:   ["Check your role assignments in the company portal","Ask your manager to submit an access request on your behalf","Confirm you are signed in with your work account","Access provisioning typically takes one business day after approval"],
  Performance:      ["Close unused applications and browser tabs","Open Task Manager and end processes with high CPU or RAM","Run Disk Cleanup and delete temporary files","A full restart often resolves performance issues"],
  Database:         ["Confirm the database service is running on the server","Check your connection string and credentials","Verify network connectivity to the database host","Review the database error logs for specific messages"],
  Application_Error:["Restart the application completely","Clear application cache and temporary files","Check the company status page for known outages","Try the action in an incognito browser window"],
  Security:         ["Do not click any suspicious links or attachments","Disconnect from the network if you suspect a breach","Document exactly what happened and when","Contact the security team immediately"],
  Compliance:       ["Document the issue with timestamps and screenshots","Do not attempt to resolve compliance issues independently","Escalate to your compliance officer or manager","Preserve all related logs and communications"],
};

function getSelfHelp(category) {
  return SELF_HELP[category] || [
    "Restart the affected system or service",
    "Check for any recent changes that may have caused this",
    "Document the exact error message and when it started",
    "Search the company IT knowledge base for known solutions",
  ];
}

// ── Theme ─────────────────────────────────────────────────────
const THEMES = {
  light: {
    bg:         "#f5f2ec",
    sidebar:    "#edeae2",
    surface:    "#ffffff",
    surfaceAlt: "#f9f7f3",
    border:     "#d4cfc5",
    borderLt:   "#e8e4db",
    accent:     "#1e6b45",
    accentHov:  "#185a39",
    accentLt:   "#e3f0e8",
    accentText: "#1e6b45",
    textPri:    "#1a1710",
    textSec:    "#6b6157",
    textMut:    "#9c9287",
    green:      "#1e6b45",
    greenLt:    "#e3f0e8",
    amber:      "#8a5c1a",
    amberLt:    "#fef3e2",
    red:        "#b03a3a",
    redLt:      "#fde8e8",
    blue:       "#2d5fa8",
    blueLt:     "#e8f0fb",
    shadow:     "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04)",
    shadowMd:   "0 4px 12px rgba(0,0,0,0.07), 0 2px 6px rgba(0,0,0,0.04)",
    scrollThumb:"#c8c3b8",
    userBubble: "#1e6b45",
    userText:   "#ffffff",
  },
  dark: {
    bg:         "#0f1117",
    sidebar:    "#161922",
    surface:    "#1a1d2e",
    surfaceAlt: "#222538",
    border:     "#2d3154",
    borderLt:   "#252843",
    accent:     "#2d9e60",
    accentHov:  "#268a53",
    accentLt:   "#1a3328",
    accentText: "#4ade80",
    textPri:    "#f1f5f9",
    textSec:    "#94a3b8",
    textMut:    "#475569",
    green:      "#22c55e",
    greenLt:    "#14291e",
    amber:      "#f59e0b",
    amberLt:    "#2a1f08",
    red:        "#ef4444",
    redLt:      "#2a1010",
    blue:       "#60a5fa",
    blueLt:     "#0f1e35",
    shadow:     "0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)",
    shadowMd:   "0 4px 12px rgba(0,0,0,0.3), 0 2px 6px rgba(0,0,0,0.2)",
    scrollThumb:"#2d3154",
    userBubble: "#2d9e60",
    userText:   "#ffffff",
  },
};

function buildCss(T) {
  return `
    @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=DM+Mono:wght@400;500&display=swap');
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; }
    body {
      background: ${T.bg};
      color: ${T.textPri};
      font-family: 'EB Garamond', 'Times New Roman', Georgia, serif;
      font-size: 16px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    input, select, textarea, button { font-family: 'EB Garamond', 'Times New Roman', Georgia, serif; }
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: ${T.scrollThumb}; border-radius: 3px; }

    @keyframes fadeIn  { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
    @keyframes blink   { 0%,100%{opacity:1} 50%{opacity:0.3} }
    .fade-in  { animation: fadeIn 0.25s ease forwards; }
    .dot1 { display:inline-block; animation: blink 1.4s ease infinite; }
    .dot2 { display:inline-block; animation: blink 1.4s ease 0.2s infinite; }
    .dot3 { display:inline-block; animation: blink 1.4s ease 0.4s infinite; }

    .btn-primary {
      background: ${T.accent};
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 9px 20px;
      font-family: 'EB Garamond', serif;
      font-size: 15px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-primary:hover:not(:disabled) { background: ${T.accentHov}; }
    .btn-primary:active:not(:disabled) { transform: translateY(1px); }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

    .btn-ghost {
      background: transparent;
      color: ${T.textSec};
      border: 1px solid ${T.border};
      border-radius: 6px;
      padding: 6px 14px;
      font-family: 'EB Garamond', serif;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-ghost:hover { background: ${T.surfaceAlt}; color: ${T.textPri}; }

    .input-field {
      width: 100%;
      padding: 10px 14px;
      background: ${T.surface};
      border: 1px solid ${T.border};
      border-radius: 6px;
      color: ${T.textPri};
      font-family: 'EB Garamond', serif;
      font-size: 15px;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    .input-field:focus { border-color: ${T.accent}; box-shadow: 0 0 0 3px ${T.accentLt}; }
    .input-field::placeholder { color: ${T.textMut}; }

    select option { background: ${T.surface}; color: ${T.textPri}; }
  `;
}

// ── Status helpers ────────────────────────────────────────────
function statusColor(status, T) {
  return {
    open:      [T.blue,  T.blueLt],
    in_review: [T.amber, T.amberLt],
    resolved:  [T.green, T.greenLt],
    escalated: [T.red,   T.redLt],
  }[status] || [T.textMut, T.surfaceAlt];
}

function slaColor(deadline, T) {
  if (!deadline) return T.textMut;
  const diff = new Date(deadline) - new Date();
  if (diff < 0) return T.red;
  if (diff < 3600000) return T.amber;
  return T.green;
}

function slaLabel(deadline) {
  if (!deadline) return "";
  const diff = new Date(deadline) - new Date();
  if (diff < 0) return "SLA breached";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}h ${m}m remaining`;
  return `${m}m remaining`;
}

// ── Login ─────────────────────────────────────────────────────
function LoginScreen({ onLogin, T }) {
  const [mode, setMode]         = useState("login");   // login | signup
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const submit = async () => {
    const u = username.trim().toLowerCase();
    const p = password.trim();
    if (!u || !p) { setError("Enter a username and password."); return; }
    if (mode === "signup" && p.length < 4) { setError("Password must be at least 4 characters."); return; }
    setLoading(true); setError("");
    try {
      const path = mode === "signup" ? "/api/auth/register" : "/api/auth/login";
      const res = await fetch(`${API}${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Authentication failed.");
      } else {
        setToken(data.access_token);
        onLogin(data.user);
      }
    } catch {
      setError("Could not reach the server. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height:"100vh", display:"flex", alignItems:"center", justifyContent:"center", background:T.bg }}>
      <div className="fade-in" style={{
        width:400, padding:"44px 40px",
        background:T.surface, borderRadius:12,
        border:`1px solid ${T.border}`, boxShadow:T.shadowMd,
      }}>
        <div style={{ textAlign:"center", marginBottom:36 }}>
          <div style={{
            width:44, height:44, borderRadius:8, background:T.accent,
            display:"flex", alignItems:"center", justifyContent:"center",
            margin:"0 auto 14px", boxShadow:`0 2px 8px ${T.accent}44`,
            fontSize:20, color:"#fff", fontWeight:700,
          }}>T</div>
          <h1 style={{ fontSize:26, fontWeight:600, color:T.textPri, marginBottom:4 }}>TicketAI</h1>
          <p style={{ fontSize:14, color:T.textSec }}>
            {mode === "signup" ? "Create your account" : "UPS Intelligent Support System"}
          </p>
        </div>

        <div style={{ marginBottom:18 }}>
          <label style={{ display:"block", fontSize:13, color:T.textSec, marginBottom:6, fontWeight:500 }}>Username</label>
          <input className="input-field" value={username} onChange={e=>setUsername(e.target.value)} onKeyDown={e=>e.key==="Enter"&&submit()} placeholder={mode==="signup"?"choose a username":"your username"} autoFocus />
        </div>
        <div style={{ marginBottom:24 }}>
          <label style={{ display:"block", fontSize:13, color:T.textSec, marginBottom:6, fontWeight:500 }}>Password</label>
          <input className="input-field" type="password" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==="Enter"&&submit()} placeholder="••••••••" />
        </div>

        {error && (
          <div style={{ fontSize:13, color:T.red, marginBottom:16, padding:"8px 12px", background:T.redLt, borderRadius:6, border:`1px solid ${T.red}33` }}>
            {error}
          </div>
        )}

        <button className="btn-primary" onClick={submit} disabled={loading} style={{ width:"100%", padding:"11px", fontSize:16 }}>
          {loading ? (mode==="signup"?"Creating...":"Signing in...") : (mode==="signup"?"Sign up":"Sign in")}
        </button>

        <div style={{ textAlign:"center", marginTop:18, fontSize:13.5, color:T.textSec }}>
          {mode === "login" ? (
            <>New here?{" "}
              <span onClick={()=>{setMode("signup");setError("");}} style={{ color:T.accentText, cursor:"pointer", fontWeight:600 }}>Create an account</span>
            </>
          ) : (
            <>Already have an account?{" "}
              <span onClick={()=>{setMode("login");setError("");}} style={{ color:T.accentText, cursor:"pointer", fontWeight:600 }}>Sign in</span>
            </>
          )}
        </div>

        {mode === "login" && (
          <div style={{ marginTop:20, padding:"12px 14px", background:T.surfaceAlt, borderRadius:6, border:`1px solid ${T.borderLt}`, fontSize:13, color:T.textSec, lineHeight:1.9 }}>
            <div style={{ fontWeight:600, marginBottom:2 }}>Demo accounts</div>
            <div>client / user123 — Support chat</div>
            <div>admin / admin123 — Dashboard and review</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Chat bubble ───────────────────────────────────────────────
function Bubble({ msg, T }) {
  const isUser = msg.role === "user";
  return (
    <div className="fade-in" style={{ display:"flex", justifyContent:isUser?"flex-end":"flex-start", marginBottom:12, gap:10 }}>
      {!isUser && (
        <div style={{
          width:28, height:28, borderRadius:"50%", flexShrink:0,
          background:T.accent, display:"flex", alignItems:"center",
          justifyContent:"center", fontSize:12, color:"#fff",
          alignSelf:"flex-end", marginBottom:2, fontWeight:700,
        }}>AI</div>
      )}
      <div style={{
        maxWidth:"70%", padding:"10px 16px",
        borderRadius: isUser ? "18px 18px 4px 18px" : "4px 18px 18px 18px",
        background: isUser ? T.userBubble : T.surface,
        color: isUser ? T.userText : T.textPri,
        fontSize:15, lineHeight:1.65, whiteSpace:"pre-wrap",
        border: isUser ? "none" : `1px solid ${T.borderLt}`,
        boxShadow:T.shadow,
      }}>
        {msg.content}
      </div>
    </div>
  );
}

// ── Clarifying-questions card ─────────────────────────────────
// Shown while the assistant is gathering details about the issue.
function QuestionCard({ questions, title, T }) {
  if (!questions?.length) return null;
  return (
    <div className="fade-in" style={{ margin:"4px 0 12px 38px", border:`1px solid ${T.accent}44`, borderRadius:8, background:T.surface, boxShadow:T.shadow, overflow:"hidden" }}>
      <div style={{ padding:"10px 14px", background:T.accentLt, borderBottom:`1px solid ${T.accent}22`, fontSize:14, fontWeight:600, color:T.accentText }}>
        {title || "A few details to help me solve this"}
      </div>
      <div style={{ padding:"12px 14px" }}>
        {questions.map((q,i) => (
          <div key={i} style={{ display:"flex", gap:10, marginBottom:9, fontSize:14, color:T.textPri, alignItems:"flex-start" }}>
            <span style={{ width:20, height:20, borderRadius:"50%", background:T.accent, color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, flexShrink:0, marginTop:2 }}>{i+1}</span>
            <span style={{ lineHeight:1.5 }}>{q}</span>
          </div>
        ))}
        <div style={{ fontSize:12.5, color:T.textMut, marginTop:6, paddingTop:8, borderTop:`1px solid ${T.borderLt}`, fontStyle:"italic" }}>
          Reply with as much as you can — you don't have to answer every question.
        </div>
      </div>
    </div>
  );
}

// ── Similar / duplicate tickets card ──────────────────────────
function SimilarTicketsCard({ items, T }) {
  if (!items?.length) return null;
  return (
    <div className="fade-in" style={{ margin:"2px 0 12px 38px", border:`1px solid ${T.amber}44`, borderRadius:8, background:T.surface, boxShadow:T.shadow, overflow:"hidden" }}>
      <div style={{ padding:"9px 14px", background:T.amberLt, borderBottom:`1px solid ${T.amber}22`, fontSize:13.5, fontWeight:600, color:T.amber }}>
        🔁 {items.length} similar ticket{items.length>1?"s":""} reported recently
      </div>
      <div style={{ padding:"10px 14px" }}>
        {items.map((s,i) => (
          <div key={i} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", fontSize:13, color:T.textPri, marginBottom:6 }}>
            <span><span style={{ fontFamily:"'DM Mono',monospace", fontSize:11.5, color:T.accentText, marginRight:8 }}>{s.ticket_id}</span>{s.title}</span>
            <span style={{ fontSize:11, color:T.textMut, flexShrink:0, marginLeft:10 }}>{Math.round(s.similarity*100)}% match · {s.status}</span>
          </div>
        ))}
        <div style={{ fontSize:12, color:T.textMut, marginTop:4, fontStyle:"italic" }}>
          If these describe the same problem, it may be a known/widespread issue.
        </div>
      </div>
    </div>
  );
}

// ── Feedback bar (👍 / 👎 on a resolution) ────────────────────
function FeedbackBar({ ticketId, T }) {
  const [done, setDone] = useState(null);   // null | true | false
  const send = async (helpful) => {
    setDone(helpful);
    try {
      await authFetch(`/api/tickets/${ticketId}/feedback`, {
        method:"POST", headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ helpful }),
      });
    } catch {}
  };
  return (
    <div style={{ margin:"2px 0 14px 38px", display:"flex", alignItems:"center", gap:8, fontSize:13, color:T.textSec }}>
      {done === null ? (
        <>
          <span>Was this helpful?</span>
          <button className="btn-ghost" onClick={()=>send(true)}  title="Helpful"     style={{ fontSize:15, padding:"3px 10px", lineHeight:1 }}>👍</button>
          <button className="btn-ghost" onClick={()=>send(false)} title="Not helpful" style={{ fontSize:15, padding:"3px 10px", lineHeight:1 }}>👎</button>
        </>
      ) : (
        <span style={{ color: done ? T.green : T.amber }}>
          {done ? "Thanks for the feedback! 🎉"
                : "Thanks — sorry it didn't help. Reply \"it didn't work\" and I'll escalate it to a specialist."}
        </span>
      )}
    </div>
  );
}

// ── Self-help card ────────────────────────────────────────────
function SelfHelpCard({ category, resolution, T }) {
  const [open, setOpen] = useState(true);
  const tips = getSelfHelp(category);
  const isHuman = resolution === "human";
  const color = isHuman ? T.red : T.amber;
  const bgColor = isHuman ? T.redLt : T.amberLt;

  return (
    <div className="fade-in" style={{ margin:"12px 0 12px 38px", border:`1px solid ${color}33`, borderRadius:8, background:T.surface, boxShadow:T.shadow, overflow:"hidden" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"10px 14px", cursor:"pointer", background:bgColor, borderBottom:open?`1px solid ${color}22`:"none" }} onClick={()=>setOpen(o=>!o)}>
        <div style={{ fontSize:14, fontWeight:600, color }}>
          {isHuman ? "Escalated to specialist" : "Under review"} — while you wait
        </div>
        <span style={{ color, fontSize:11 }}>{open?"▲":"▼"}</span>
      </div>
      {open && (
        <div style={{ padding:"12px 14px" }}>
          <div style={{ fontSize:13, color:T.textSec, marginBottom:10, fontStyle:"italic" }}>
            Self-help steps for <strong>{category?.replace(/_/g," ")}</strong>:
          </div>
          {tips.map((tip,i) => (
            <div key={i} style={{ display:"flex", gap:10, marginBottom:8, fontSize:14, color:T.textPri, alignItems:"flex-start" }}>
              <span style={{ width:20, height:20, borderRadius:"50%", background:color+"22", color, display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, flexShrink:0, marginTop:2 }}>{i+1}</span>
              <span style={{ lineHeight:1.5 }}>{tip}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Autonomous resolution card ────────────────────────────────
// Shows exactly how an autonomous ticket was solved (steps, ref, ETA).
function ResolutionCard({ resolution, T }) {
  const [open, setOpen] = useState(true);
  if (!resolution) return null;
  const inProgress = resolution.status === "in_progress";
  const color = inProgress ? T.amber : T.green;
  const bgColor = inProgress ? T.amberLt : T.greenLt;

  return (
    <div className="fade-in" style={{ margin:"12px 0 12px 38px", border:`1px solid ${color}44`, borderRadius:8, background:T.surface, boxShadow:T.shadow, overflow:"hidden" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"10px 14px", cursor:"pointer", background:bgColor, borderBottom:open?`1px solid ${color}22`:"none" }} onClick={()=>setOpen(o=>!o)}>
        <div style={{ fontSize:14, fontWeight:600, color }}>
          {inProgress ? "Auto-fix in progress" : "Resolved automatically"} — here's how
        </div>
        <span style={{ color, fontSize:11 }}>{open?"▲":"▼"}</span>
      </div>
      {open && (
        <div style={{ padding:"12px 14px" }}>
          <div style={{ fontSize:13.5, color:T.textPri, marginBottom:10 }}>{resolution.summary}</div>
          {resolution.steps?.map((s,i) => (
            <div key={i} style={{ display:"flex", gap:10, marginBottom:8, fontSize:14, color:T.textPri, alignItems:"flex-start" }}>
              <span style={{ width:18, height:18, borderRadius:"50%", background: s.status==="failed"?T.red:T.green, color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, flexShrink:0, marginTop:2 }}>
                {s.status==="failed" ? "×" : "✓"}
              </span>
              <span style={{ lineHeight:1.5 }}>
                {s.action}
                {s.detail && <span style={{ color:T.textMut, fontSize:13 }}> — {s.detail}</span>}
              </span>
            </div>
          ))}
          <div style={{ display:"flex", gap:8, flexWrap:"wrap", marginTop:10, paddingTop:10, borderTop:`1px solid ${T.borderLt}` }}>
            {resolution.reference_id && <Tag label={`Ref: ${resolution.reference_id}`} T={T} />}
            {resolution.system && <Tag label={resolution.system} T={T} />}
            {resolution.eta && <Tag label={`ETA: ${resolution.eta}`} T={T} accent />}
          </div>
          {resolution.follow_up && (
            <div style={{ fontSize:13, color:T.textSec, marginTop:10, lineHeight:1.6 }}>
              <strong style={{ color:T.accentText }}>Next:</strong> {resolution.follow_up}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── My Tickets view ───────────────────────────────────────────
// Category → department map (mirrors backend core/teams.py) for grouping.
const DEPARTMENTS = {
  "Network & Connectivity": ["VPN","Network"],
  "Accounts & Access":      ["Password_Reset","Access_Request","Onboarding","Offboarding"],
  "Hardware & Devices":     ["Hardware","Mobile_Device","Printer","Performance"],
  "Software & Applications":["Software_Install","Application_Error","Email"],
  "Data & Storage":         ["Database","Data_Recovery","Cloud_Storage"],
  "Security & Compliance":  ["Security","Compliance"],
  "Finance":                ["Payroll","Billing"],
  "People & Workplace":     ["HR","Facilities","Other"],
};
function departmentFor(cat) {
  if (!cat) return "Other";
  for (const [d, cats] of Object.entries(DEPARTMENTS)) if (cats.includes(cat)) return d;
  return "People & Workplace";
}

function MyTicketsView({ sessionId, isAdmin, T }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`/api/tickets/mine?limit=100`);
      setTickets(await res.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === "all" ? tickets : tickets.filter(t => t.status === filter);
  const counts   = tickets.reduce((a,t) => ({ ...a, [t.status]: (a[t.status]||0)+1 }), {});

  const statusOpts = [
    { v:"all",       l:"All tickets" },
    { v:"open",      l:"Open" },
    { v:"in_review", l:"In review" },
    { v:"resolved",  l:"Resolved" },
    { v:"escalated", l:"Escalated" },
  ];

  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      {/* Header */}
      <div style={{ padding:"20px 28px 14px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:600, color:T.textPri }}>{isAdmin ? "All Tickets" : "My Tickets"}</h2>
          <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{tickets.length} total</p>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <select value={filter} onChange={e=>setFilter(e.target.value)} style={{ padding:"7px 12px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:14 }}>
            {statusOpts.map(o => <option key={o.v} value={o.v}>{o.l} {o.v!=="all"&&counts[o.v]?`(${counts[o.v]})`:""}</option>)}
          </select>
          <button className="btn-ghost" onClick={load} style={{ fontSize:13, padding:"7px 14px" }}>Refresh</button>
        </div>
      </div>

      {/* Status summary pills */}
      <div style={{ display:"flex", gap:8, padding:"12px 28px", borderBottom:`1px solid ${T.borderLt}`, background:T.surface, flexWrap:"wrap" }}>
        {[["open",T.blue,T.blueLt],["in_review",T.amber,T.amberLt],["resolved",T.green,T.greenLt],["escalated",T.red,T.redLt]].map(([s,c,bg]) => (
          <div key={s} style={{ padding:"3px 12px", borderRadius:999, background:bg, border:`1px solid ${c}33`, fontSize:12, color:c, fontWeight:600 }}>
            {s.replace("_"," ").replace(/\b\w/g,l=>l.toUpperCase())}: {counts[s]||0}
          </div>
        ))}
      </div>

      {/* Ticket list */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px" }}>
        {loading && <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:40 }}>Loading...</div>}
        {!loading && filtered.length === 0 && (
          <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:60 }}>
            {filter === "all" ? "No tickets yet." : `No ${filter.replace("_"," ")} tickets.`}
          </div>
        )}
        {!loading && (() => {
          // Group the (filtered) tickets by department, keeping canonical order.
          const groups = {};
          filtered.forEach(t => { const d = departmentFor(t.category); (groups[d] = groups[d] || []).push(t); });
          const order = Object.keys(DEPARTMENTS).filter(d => groups[d]?.length);

          const card = (t) => {
            const [sc, sbg] = statusColor(t.status, T);
            const sla = slaLabel(t.sla_deadline);
            const slaC = slaColor(t.sla_deadline, T);
            return (
              <div key={t.ticket_id} className="fade-in" style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", marginBottom:10, boxShadow:T.shadow }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:6 }}>
                  <div>
                    <span style={{ fontFamily:"'DM Mono',monospace", fontSize:12, color:T.accentText, marginRight:10 }}>{t.ticket_id}</span>
                    <span style={{ fontSize:15, fontWeight:600, color:T.textPri }}>{t.title}</span>
                  </div>
                  <span style={{ fontSize:11, padding:"2px 10px", borderRadius:999, background:sbg, color:sc, border:`1px solid ${sc}33`, fontWeight:600, flexShrink:0, marginLeft:10 }}>
                    {t.status?.replace("_"," ").replace(/\b\w/g,l=>l.toUpperCase())}
                  </span>
                </div>
                <p style={{ fontSize:13, color:T.textSec, lineHeight:1.5, marginBottom:8, overflow:"hidden", display:"-webkit-box", WebkitLineClamp:2, WebkitBoxOrient:"vertical" }}>
                  {t.description}
                </p>
                <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
                  {t.category && <Tag label={t.category.replace(/_/g," ")} T={T} />}
                  <Tag label={`Priority: ${t.priority}`} T={T} />
                  {t.resolution_type && <Tag label={t.resolution_type} T={T} accent />}
                  <span style={{ fontSize:12, color:T.textMut, marginLeft:"auto" }}>
                    {new Date(t.created_at).toLocaleDateString()}
                  </span>
                  {sla && (t.status === "in_review" || t.status === "open") && (
                    <span style={{ fontSize:11, color:slaC, fontWeight:600 }}>⏱ {sla}</span>
                  )}
                </div>
              </div>
            );
          };

          return order.map(dept => (
            <div key={dept} style={{ marginBottom:18 }}>
              <div style={{ display:"flex", alignItems:"center", gap:10, margin:"4px 0 10px" }}>
                <span style={{ fontSize:13, fontWeight:700, color:T.textSec, textTransform:"uppercase", letterSpacing:"0.05em" }}>{dept}</span>
                <span style={{ fontSize:11, padding:"1px 9px", borderRadius:999, background:T.accentLt, color:T.accentText, fontWeight:600 }}>{groups[dept].length}</span>
                <div style={{ flex:1, height:1, background:T.borderLt }} />
              </div>
              {groups[dept].map(card)}
            </div>
          ));
        })()}
      </div>
    </div>
  );
}

// ── Shared: ticket card list with a Resolve action ────────────
function AdminTicketList({ tickets, busy, onResolve, emptyText, T }) {
  return (
    <div style={{ flex:1, overflowY:"auto", padding:"16px 28px" }}>
      {tickets.length === 0 && <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:50 }}>{emptyText || "No tickets."}</div>}
      {tickets.map(t => {
        const [sc, sbg] = statusColor(t.status, T);
        const sla = slaLabel(t.sla_deadline);
        const slaC = slaColor(t.sla_deadline, T);
        const isResolved = t.status === "resolved";
        return (
          <div key={t.ticket_id} className="fade-in" style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", marginBottom:10, boxShadow:T.shadow }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:6 }}>
              <div>
                <span style={{ fontFamily:"'DM Mono',monospace", fontSize:12, color:T.accentText, marginRight:10 }}>{t.ticket_id}</span>
                <span style={{ fontSize:15, fontWeight:600, color:T.textPri }}>{t.title}</span>
              </div>
              <span style={{ fontSize:11, padding:"2px 10px", borderRadius:999, background:sbg, color:sc, border:`1px solid ${sc}33`, fontWeight:600, flexShrink:0, marginLeft:10 }}>
                {t.status?.replace("_"," ").replace(/\b\w/g,l=>l.toUpperCase())}
              </span>
            </div>
            <p style={{ fontSize:13, color:T.textSec, lineHeight:1.5, marginBottom:8 }}>{t.description}</p>
            <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
              {t.category && <Tag label={t.category.replace(/_/g," ")} T={T} />}
              <Tag label={`Priority: ${t.priority}`} T={T} />
              {t.resolution_type && <Tag label={t.resolution_type} T={T} accent />}
              {sla && !isResolved && <span style={{ fontSize:11, color:slaC, fontWeight:600 }}>⏱ {sla}</span>}
              <button onClick={()=>onResolve(t.ticket_id)} disabled={isResolved || busy===t.ticket_id}
                className={isResolved ? "btn-ghost" : "btn-primary"}
                style={{ marginLeft:"auto", fontSize:12.5, padding:"5px 14px", opacity:isResolved?0.6:1, cursor:isResolved?"default":"pointer" }}>
                {isResolved ? "✓ Resolved" : (busy===t.ticket_id ? "Resolving…" : "Mark resolved")}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Admin: Users → Tickets → Resolve ──────────────────────────
function AdminUsersView({ T }) {
  const [users, setUsers]       = useState([]);
  const [selected, setSelected] = useState(null);   // selected user
  const [tickets, setTickets]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [busy, setBusy]         = useState(null);    // ticket id being resolved

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try { setUsers(await (await authFetch("/api/admin/users")).json()); } catch {}
    setLoading(false);
  }, []);
  useEffect(() => { loadUsers(); }, [loadUsers]);

  const openUser = async (u) => {
    setSelected(u); setTickets([]);
    try { setTickets(await (await authFetch(`/api/tickets/?user_id=${u.id}&limit=200`)).json()); } catch {}
  };

  const resolve = async (tid) => {
    setBusy(tid);
    try {
      await authFetch(`/api/tickets/${tid}/resolve`, { method:"POST" });
      setTickets(ts => ts.map(t => t.ticket_id===tid ? { ...t, status:"resolved" } : t));
      loadUsers();
    } catch {}
    setBusy(null);
  };

  // ── Drill-down: a user's tickets ──
  if (selected) {
    return (
      <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
        <div style={{ padding:"20px 28px 14px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", alignItems:"center", gap:14 }}>
          <button className="btn-ghost" onClick={()=>setSelected(null)} style={{ fontSize:13, padding:"6px 12px" }}>← Users</button>
          <div>
            <h2 style={{ fontSize:19, fontWeight:600, color:T.textPri }}>{selected.username}</h2>
            <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{tickets.length} ticket(s) · {selected.role}</p>
          </div>
        </div>
        <div style={{ flex:1, overflowY:"auto", padding:"16px 28px" }}>
          {tickets.length === 0 && <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:50 }}>No tickets for this user.</div>}
          {tickets.map(t => {
            const [sc, sbg] = statusColor(t.status, T);
            const sla = slaLabel(t.sla_deadline);
            const slaC = slaColor(t.sla_deadline, T);
            const isResolved = t.status === "resolved";
            return (
              <div key={t.ticket_id} className="fade-in" style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", marginBottom:10, boxShadow:T.shadow }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:6 }}>
                  <div>
                    <span style={{ fontFamily:"'DM Mono',monospace", fontSize:12, color:T.accentText, marginRight:10 }}>{t.ticket_id}</span>
                    <span style={{ fontSize:15, fontWeight:600, color:T.textPri }}>{t.title}</span>
                  </div>
                  <span style={{ fontSize:11, padding:"2px 10px", borderRadius:999, background:sbg, color:sc, border:`1px solid ${sc}33`, fontWeight:600, flexShrink:0, marginLeft:10 }}>
                    {t.status?.replace("_"," ").replace(/\b\w/g,l=>l.toUpperCase())}
                  </span>
                </div>
                <p style={{ fontSize:13, color:T.textSec, lineHeight:1.5, marginBottom:8 }}>{t.description}</p>
                <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
                  {t.category && <Tag label={t.category.replace(/_/g," ")} T={T} />}
                  <Tag label={`Priority: ${t.priority}`} T={T} />
                  {t.resolution_type && <Tag label={t.resolution_type} T={T} accent />}
                  {sla && !isResolved && <span style={{ fontSize:11, color:slaC, fontWeight:600 }}>⏱ {sla}</span>}
                  <button
                    onClick={()=>resolve(t.ticket_id)}
                    disabled={isResolved || busy===t.ticket_id}
                    className={isResolved ? "btn-ghost" : "btn-primary"}
                    style={{ marginLeft:"auto", fontSize:12.5, padding:"5px 14px", opacity:isResolved?0.6:1, cursor:isResolved?"default":"pointer" }}>
                    {isResolved ? "✓ Resolved" : (busy===t.ticket_id ? "Resolving…" : "Mark resolved")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ── Users list ──
  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"20px 28px 14px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:600, color:T.textPri }}>Users</h2>
          <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{users.length} user(s) · click to view their tickets</p>
        </div>
        <button className="btn-ghost" onClick={loadUsers} style={{ fontSize:13, padding:"7px 14px" }}>Refresh</button>
      </div>
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px" }}>
        {loading && <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:40 }}>Loading…</div>}
        {!loading && users.map(u => (
          <div key={u.id} onClick={()=>openUser(u)} className="fade-in"
               style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", marginBottom:10, boxShadow:T.shadow, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <div style={{ display:"flex", alignItems:"center", gap:12 }}>
              <div style={{ width:34, height:34, borderRadius:"50%", background:T.accentLt, color:T.accentText, display:"flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:14 }}>
                {u.username.slice(0,2).toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize:15, fontWeight:600, color:T.textPri }}>{u.username}</div>
                <div style={{ fontSize:12, color:T.textMut }}>{u.role}</div>
              </div>
            </div>
            <div style={{ display:"flex", gap:8, alignItems:"center" }}>
              {u.open_count > 0 && <span style={{ fontSize:11, padding:"2px 10px", borderRadius:999, background:T.amberLt, color:T.amber, border:`1px solid ${T.amber}33`, fontWeight:600 }}>{u.open_count} open</span>}
              <span style={{ fontSize:12.5, color:T.textSec }}>{u.ticket_count} ticket(s)</span>
              <span style={{ color:T.textMut }}>›</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Admin: Teams/Departments → Tickets → Resolve ──────────────
function AdminTeamsView({ T }) {
  const [teams, setTeams]       = useState([]);
  const [selected, setSelected] = useState(null);
  const [tickets, setTickets]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [busy, setBusy]         = useState(null);

  const loadTeams = useCallback(async () => {
    setLoading(true);
    try { setTeams(await (await authFetch("/api/admin/teams")).json()); } catch {}
    setLoading(false);
  }, []);
  useEffect(() => { loadTeams(); }, [loadTeams]);

  const openTeam = async (tm) => {
    setSelected(tm); setTickets([]);
    try { setTickets(await (await authFetch(`/api/tickets/?department=${encodeURIComponent(tm.department)}&limit=200`)).json()); } catch {}
  };
  const resolve = async (tid) => {
    setBusy(tid);
    try { await authFetch(`/api/tickets/${tid}/resolve`, { method:"POST" });
      setTickets(ts => ts.map(t => t.ticket_id===tid ? { ...t, status:"resolved" } : t));
      loadTeams(); } catch {}
    setBusy(null);
  };

  if (selected) return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"16px 28px 12px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", alignItems:"center", gap:14 }}>
        <button className="btn-ghost" onClick={()=>setSelected(null)} style={{ fontSize:13, padding:"6px 12px" }}>← Teams</button>
        <div>
          <h2 style={{ fontSize:19, fontWeight:600, color:T.textPri }}>{selected.department}</h2>
          <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{tickets.length} ticket(s) · {selected.categories.map(c=>c.replace(/_/g," ")).join(", ")}</p>
        </div>
      </div>
      <AdminTicketList tickets={tickets} busy={busy} onResolve={resolve} emptyText="No tickets for this team." T={T} />
    </div>
  );

  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"16px 28px 12px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:600, color:T.textPri }}>Teams</h2>
          <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{teams.length} departments · click to view their tickets</p>
        </div>
        <button className="btn-ghost" onClick={loadTeams} style={{ fontSize:13, padding:"7px 14px" }}>Refresh</button>
      </div>
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px" }}>
        {loading && <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:40 }}>Loading…</div>}
        {!loading && teams.map(tm => (
          <div key={tm.department} onClick={()=>openTeam(tm)} className="fade-in"
               style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", marginBottom:10, boxShadow:T.shadow, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <div>
              <div style={{ fontSize:15, fontWeight:600, color:T.textPri }}>{tm.department}</div>
              <div style={{ fontSize:12, color:T.textMut, marginTop:2 }}>{tm.categories.map(c=>c.replace(/_/g," ")).join(" · ")}</div>
            </div>
            <div style={{ display:"flex", gap:8, alignItems:"center" }}>
              {tm.open_count > 0 && <span style={{ fontSize:11, padding:"2px 10px", borderRadius:999, background:T.amberLt, color:T.amber, border:`1px solid ${T.amber}33`, fontWeight:600 }}>{tm.open_count} open</span>}
              <span style={{ fontSize:12.5, color:T.textSec }}>{tm.ticket_count} ticket(s)</span>
              <span style={{ color:T.textMut }}>›</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Admin workspace: toggle between By User and By Team ────────
function AdminWorkspace({ T }) {
  const [mode, setMode] = useState("team");   // team | user
  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"12px 28px", borderBottom:`1px solid ${T.borderLt}`, background:T.surface, display:"flex", gap:8 }}>
        {[["team","By Team"],["user","By User"]].map(([m,l])=>(
          <button key={m} onClick={()=>setMode(m)} style={{
            padding:"6px 16px", borderRadius:999, border:`1px solid ${mode===m?T.accent:T.border}`,
            background: mode===m?T.accentLt:"transparent", color: mode===m?T.accentText:T.textSec,
            fontSize:13.5, fontWeight: mode===m?600:400, cursor:"pointer" }}>{l}</button>
        ))}
      </div>
      <div style={{ flex:1, minHeight:0 }}>
        {mode==="team" ? <AdminTeamsView T={T} /> : <AdminUsersView T={T} />}
      </div>
    </div>
  );
}

// ── Department agent: their scoped tickets → Resolve ──────────
function DeptTicketsView({ user, T }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy]       = useState(null);
  const [filter, setFilter]   = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try { setTickets(await (await authFetch("/api/tickets/?limit=300")).json()); } catch {}
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const resolve = async (tid) => {
    setBusy(tid);
    try {
      await authFetch(`/api/tickets/${tid}/resolve`, { method:"POST" });
      setTickets(ts => ts.map(t => t.ticket_id===tid ? { ...t, status:"resolved" } : t));
    } catch {}
    setBusy(null);
  };

  const filtered = filter === "all" ? tickets : tickets.filter(t => t.status === filter);
  const counts = tickets.reduce((a,t)=>({ ...a, [t.status]:(a[t.status]||0)+1 }), {});
  const opts = [["all","All"],["open","Open"],["in_review","In review"],["resolved","Resolved"],["escalated","Escalated"]];

  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"16px 28px 12px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:600, color:T.textPri }}>{user.department} — Tickets</h2>
          <p style={{ fontSize:13, color:T.textSec, marginTop:2 }}>{tickets.length} ticket(s) in your department's categories</p>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <select value={filter} onChange={e=>setFilter(e.target.value)} style={{ padding:"7px 12px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:14 }}>
            {opts.map(([v,l]) => <option key={v} value={v}>{l}{v!=="all"&&counts[v]?` (${counts[v]})`:""}</option>)}
          </select>
          <button className="btn-ghost" onClick={load} style={{ fontSize:13, padding:"7px 14px" }}>Refresh</button>
        </div>
      </div>
      {loading
        ? <div style={{ color:T.textMut, fontStyle:"italic", textAlign:"center", marginTop:40 }}>Loading…</div>
        : <AdminTicketList tickets={filtered} busy={busy} onResolve={resolve} emptyText="No tickets in your department yet." T={T} />}
    </div>
  );
}

// ── Chat view ─────────────────────────────────────────────────
const STORAGE_KEY = "ticketai_chat_history";
const SESSION_KEY = "ticketai_session_id";

function genSession() {
  const ex = sessionStorage.getItem(SESSION_KEY);
  if (ex) return ex;
  const id = `sess_${Math.random().toString(36).slice(2,10)}`;
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [{ role:"assistant", content:"Hi! I am your IT support assistant. How can I help you today?" }];
  } catch {
    return [{ role:"assistant", content:"Hi! I am your IT support assistant. How can I help you today?" }];
  }
}

function ChatView({ T }) {
  const [messages, setMessages]     = useState(loadHistory);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [sessionId]                 = useState(genSession);
  const [lastTicket, setLastTicket] = useState(null);
  const [ocrBusy, setOcrBusy]       = useState(false);
  const bottomRef                   = useRef(null);
  const inputRef                    = useRef(null);
  const textareaRef                 = useRef(null);
  const fileRef                     = useRef(null);

  const uploadImage = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";          // allow re-selecting the same file
    if (!f) return;
    setOcrBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await authFetch("/api/chat/extract", { method:"POST", body: fd });
      const data = await res.json();
      const text = (data.text || "").trim();
      setInput(text
        ? `${text}`
        : "I uploaded a screenshot but no text could be read — let me describe it: ");
      setTimeout(() => textareaRef.current?.focus(), 50);
    } catch {
      setInput("Couldn't read that image — please describe the issue instead.");
    } finally {
      setOcrBusy(false);
    }
  };

  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); }, [messages]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [messages, loading]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    const newMessages = [...messages, { role:"user", content:userMsg }];
    setMessages(newMessages);
    setLoading(true);
    setLastTicket(null);
    try {
      const res = await authFetch(`/api/chat/`, {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ session_id:sessionId, message:userMsg, history:newMessages.slice(-10) }),
      });
      const data = await res.json();
      setMessages(prev => [...prev, {
        role:"assistant",
        content: data.reply || "Your request has been processed.",
        questions: data.questions || [],
        questionsTitle: data.questions_title || null,
      }]);
      if (data.ticket_id && data.classification) setLastTicket(data);
    } catch {
      setMessages(prev => [...prev, { role:"assistant", content:"Connection issue — please try again." }]);
    } finally {
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const clearChat = () => {
    setMessages([{ role:"assistant", content:"Hi! I am your IT support assistant. How can I help you today?" }]);
    setLastTicket(null);
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(SESSION_KEY);
  };

  const handleInput = e => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  return (
    <div style={{ display:"flex", height:"100%", background:T.bg }}>
      {/* Sidebar */}
      <div style={{ width:220, flexShrink:0, background:T.sidebar, borderRight:`1px solid ${T.border}`, display:"flex", flexDirection:"column", padding:"16px 10px" }}>
        <div style={{ fontSize:12, color:T.textMut, fontWeight:600, marginBottom:10, paddingLeft:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>Conversations</div>
        <div style={{ padding:"8px 10px", borderRadius:6, background:T.accentLt, border:`1px solid ${T.accent}33`, fontSize:14, color:T.accentText, fontWeight:500, cursor:"pointer" }}>
          Current session
        </div>
        <div style={{ flex:1 }} />
        <button className="btn-ghost" onClick={clearChat} style={{ width:"100%", fontSize:13 }}>New chat</button>
      </div>

      {/* Messages */}
      <div style={{ flex:1, display:"flex", flexDirection:"column", minWidth:0 }}>
        <div style={{ flex:1, overflowY:"auto", padding:"28px 10%" }}>
          {messages.map((m,i) => (
            <React.Fragment key={i}>
              <Bubble msg={m} T={T} />
              {m.questions?.length > 0 && <QuestionCard questions={m.questions} title={m.questionsTitle} T={T} />}
            </React.Fragment>
          ))}
          {loading && (
            <div style={{ display:"flex", gap:10, alignItems:"flex-end", marginBottom:12 }}>
              <div style={{ width:28, height:28, borderRadius:"50%", background:T.accent, display:"flex", alignItems:"center", justifyContent:"center", fontSize:12, color:"#fff", fontWeight:700 }}>AI</div>
              <div style={{ padding:"10px 16px", borderRadius:"4px 18px 18px 18px", background:T.surface, border:`1px solid ${T.borderLt}`, boxShadow:T.shadow }}>
                <span className="dot1" style={{ fontSize:18, color:T.textMut }}>.</span>
                <span className="dot2" style={{ fontSize:18, color:T.textMut }}>.</span>
                <span className="dot3" style={{ fontSize:18, color:T.textMut }}>.</span>
              </div>
            </div>
          )}
          {lastTicket?.routing === "autonomous" && lastTicket?.resolution ? (
            <ResolutionCard resolution={lastTicket.resolution} T={T} />
          ) : lastTicket?.classification ? (
            <SelfHelpCard category={lastTicket.classification.category} resolution={lastTicket.classification.resolution_type} T={T} />
          ) : null}
          {lastTicket?.similar_tickets?.length > 0 && <SimilarTicketsCard items={lastTicket.similar_tickets} T={T} />}
          {lastTicket?.ticket_id && <FeedbackBar key={lastTicket.ticket_id} ticketId={lastTicket.ticket_id} T={T} />}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding:"14px 10%", borderTop:`1px solid ${T.borderLt}`, background:T.surface }}>
          <div style={{ display:"flex", gap:8, alignItems:"flex-end", background:T.surface, border:`1px solid ${T.border}`, borderRadius:10, padding:"8px 8px 8px 12px", boxShadow:T.shadow }}>
            <input ref={fileRef} type="file" accept="image/*" onChange={uploadImage} style={{ display:"none" }} />
            <button onClick={()=>fileRef.current?.click()} disabled={ocrBusy||loading} title="Attach a screenshot of the error"
              style={{ width:30, height:30, borderRadius:7, border:"none", flexShrink:0, alignSelf:"flex-end", background:"transparent", color:ocrBusy?T.accent:T.textMut, cursor:ocrBusy?"default":"pointer", fontSize:17 }}>
              {ocrBusy ? "…" : "📎"}
            </button>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={e => e.key==="Enter" && !e.shiftKey && (e.preventDefault(), send())}
              placeholder="Message TicketAI..."
              rows={1}
              style={{ flex:1, border:"none", outline:"none", resize:"none", background:"transparent", color:T.textPri, fontSize:15, lineHeight:1.6, fontFamily:"'EB Garamond', serif", maxHeight:120, overflowY:"auto" }}
            />
            <button onClick={send} disabled={loading||!input.trim()} style={{
              width:34, height:34, borderRadius:7, border:"none", flexShrink:0,
              background: input.trim()&&!loading ? T.accent : T.borderLt,
              color: input.trim()&&!loading ? "#fff" : T.textMut,
              cursor: input.trim()&&!loading ? "pointer" : "not-allowed",
              fontSize:16, transition:"all 0.15s",
              display:"flex", alignItems:"center", justifyContent:"center",
            }}>↑</button>
          </div>
          <div style={{ fontSize:12, color:T.textMut, textAlign:"center", marginTop:8 }}>
            Enter to send · Shift+Enter for new line · 📎 attach an error screenshot
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Admin: Review queue ───────────────────────────────────────
function ReviewView({ T }) {
  const [queue, setQueue]           = useState([]);
  const [selected, setSelected]     = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [filterCat, setFilterCat]   = useState("all");
  const [filterPri, setFilterPri]   = useState("all");

  const load = useCallback(async () => {
    try {
      let url = `/api/review/queue?status=pending&limit=100`;
      if (filterCat !== "all") url += `&category=${filterCat}`;
      if (filterPri !== "all") url += `&priority=${filterPri}`;
      const res = await authFetch(url);
      setQueue(await res.json());
    } catch {}
  }, [filterCat, filterPri]);

  useEffect(() => { load(); }, [load]);

  const decide = async (queueId, approved, overrides={}) => {
    setSubmitting(true);
    try {
      await authFetch(`/api/review/decide`, {
        method:"POST", headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ queue_id:queueId, agent_id:"admin", approved, ...overrides }),
      });
      setSelected(null);
      load();
    } catch {}
    setSubmitting(false);
  };

  const CATS = ["all","VPN","Password_Reset","Hardware","Software_Install","Payroll","Network","Security","Email","Printer","Access_Request","Data_Recovery","Performance","Onboarding","Offboarding","Compliance","Cloud_Storage","Mobile_Device","Database","Application_Error","Billing"];

  return (
    <div style={{ display:"flex", height:"100%", background:T.bg }}>
      {/* Queue list */}
      <div style={{ width:320, flexShrink:0, borderRight:`1px solid ${T.border}`, background:T.sidebar, display:"flex", flexDirection:"column" }}>
        <div style={{ padding:"14px 14px 10px", borderBottom:`1px solid ${T.border}` }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
            <span style={{ fontWeight:600, fontSize:16, color:T.textPri }}>
              Review Queue <span style={{ fontSize:13, color:T.accent, fontWeight:400 }}>({queue.length})</span>
            </span>
            <button className="btn-ghost" onClick={load} style={{ fontSize:12, padding:"3px 10px" }}>Refresh</button>
          </div>
          {/* Filters */}
          <div style={{ display:"flex", gap:6 }}>
            <select value={filterCat} onChange={e=>setFilterCat(e.target.value)} style={{ flex:1, padding:"5px 8px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:12 }}>
              {CATS.map(c => <option key={c} value={c}>{c==="all"?"All categories":c.replace(/_/g," ")}</option>)}
            </select>
            <select value={filterPri} onChange={e=>setFilterPri(e.target.value)} style={{ flex:1, padding:"5px 8px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:12 }}>
              {["all","low","medium","high","critical"].map(p => <option key={p} value={p}>{p==="all"?"All priorities":p}</option>)}
            </select>
          </div>
        </div>

        <div style={{ flex:1, overflowY:"auto", padding:8 }}>
          {queue.length===0 && <div style={{ textAlign:"center", color:T.textMut, fontSize:14, marginTop:60, fontStyle:"italic" }}>All clear</div>}
          {queue.map(item => {
            const conf   = item.ai_prediction?.confidence || 0;
            const confC  = conf>=0.85?T.green:conf>=0.60?T.amber:T.red;
            const slaC   = slaColor(item.sla_deadline, T);
            const slaLbl = slaLabel(item.sla_deadline);
            return (
              <div key={item.queue_id} onClick={()=>setSelected(item)} style={{
                padding:"10px 12px", borderRadius:7, marginBottom:4, cursor:"pointer",
                border:`1px solid ${selected?.queue_id===item.queue_id?T.accent:T.borderLt}`,
                background: selected?.queue_id===item.queue_id?T.accentLt:T.surface,
                boxShadow:T.shadow, transition:"all 0.12s",
              }}>
                <div style={{ fontFamily:"'DM Mono',monospace", fontSize:11, color:T.accentText, marginBottom:3 }}>{item.ticket_id}</div>
                <div style={{ fontSize:13, color:T.textPri, marginBottom:5, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {item.ticket?.title || item.ticket?.description?.slice(0,45)}
                </div>
                <div style={{ display:"flex", gap:6, alignItems:"center", flexWrap:"wrap" }}>
                  {(() => {
                    const p = item.ticket?.priority || "medium";
                    const pc = { critical:T.red, high:T.amber, medium:T.blue, low:T.textMut }[p] || T.textMut;
                    return (
                      <span style={{ fontSize:10, padding:"1px 7px", borderRadius:999, background:pc+"22", color:pc, border:`1px solid ${pc}44`, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.04em" }}>
                        {p}
                      </span>
                    );
                  })()}
                  <span style={{ fontSize:11, padding:"1px 7px", borderRadius:999, background:T.surfaceAlt, color:T.textSec, border:`1px solid ${T.border}` }}>
                    {item.ai_prediction?.category?.replace(/_/g," ")}
                  </span>
                  <span style={{ fontSize:11, color:confC, fontWeight:600 }}>{(conf*100).toFixed(0)}%</span>
                  {slaLbl && <span style={{ fontSize:10, color:slaC, fontWeight:600, marginLeft:"auto" }}>{slaLbl}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Detail */}
      <div style={{ flex:1, overflowY:"auto", padding:"28px 32px", background:T.bg }}>
        {!selected ? (
          <div style={{ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", height:"100%", color:T.textMut, fontStyle:"italic", fontSize:15 }}>
            Select a ticket to review
          </div>
        ) : (
          <ReviewPanel item={selected} onDecide={decide} submitting={submitting} T={T} />
        )}
      </div>
    </div>
  );
}

function ReviewPanel({ item, onDecide, submitting, T }) {
  const [cat, setCat]     = useState(item.ai_prediction.category);
  const [res, setRes]     = useState(item.ai_prediction.resolution_type);
  const [notes, setNotes] = useState("");
  const CATS = ["VPN","Password_Reset","Hardware","Software_Install","Payroll","Network","Security","Email","Printer","Access_Request","Data_Recovery","Performance","Onboarding","Offboarding","Compliance","Cloud_Storage","Mobile_Device","Database","Application_Error","Billing","HR","Facilities","Other"];
  const conf   = item.ai_prediction.confidence;
  const confC  = conf>=0.85?T.green:conf>=0.60?T.amber:T.red;
  const confBg = conf>=0.85?T.greenLt:conf>=0.60?T.amberLt:T.redLt;
  const slaC   = slaColor(item.sla_deadline, T);
  const slaLbl = slaLabel(item.sla_deadline);

  return (
    <div style={{ maxWidth:580 }}>
      <div style={{ fontFamily:"'DM Mono',monospace", fontSize:13, color:T.accentText, marginBottom:4 }}>{item.ticket_id}</div>
      <div style={{ fontSize:12, color:T.textMut, marginBottom: slaLbl ? 6 : 20 }}>
        {new Date(item.created_at).toLocaleString()}
      </div>
      {slaLbl && (
        <div style={{ fontSize:12, color:slaC, fontWeight:600, marginBottom:20 }}>{slaLbl}</div>
      )}

      <PanelSection title="Ticket details" T={T}>
        <h3 style={{ fontSize:17, fontWeight:600, marginBottom:6, color:T.textPri }}>{item.ticket?.title}</h3>
        <p style={{ fontSize:14, color:T.textSec, lineHeight:1.7 }}>{item.ticket?.description}</p>
        <div style={{ display:"flex", gap:8, marginTop:12, flexWrap:"wrap" }}>
          <Tag label={`Priority: ${item.ticket?.priority}`} T={T} />
          <Tag label={`Source: ${item.ticket?.source||"chat"}`} T={T} />
        </div>
      </PanelSection>

      <PanelSection title="AI prediction" T={T}>
        <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
          <Tag label={item.ai_prediction.category?.replace(/_/g," ")} T={T} accent />
          <Tag label={item.ai_prediction.resolution_type} T={T} />
          <span style={{ fontSize:13, fontWeight:600, color:confC, padding:"2px 10px", borderRadius:999, background:confBg, border:`1px solid ${confC}33` }}>
            {(conf*100).toFixed(0)}% confidence
          </span>
          <span style={{ fontSize:12, color:T.textMut, fontFamily:"'DM Mono',monospace" }}>{item.ai_prediction.model_used}</span>
        </div>
      </PanelSection>

      <PanelSection title="Your decision" T={T}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginBottom:14 }}>
          <div>
            <label style={{ display:"block", fontSize:13, color:T.textSec, marginBottom:5 }}>Category</label>
            <select value={cat} onChange={e=>setCat(e.target.value)} style={{ width:"100%", padding:"8px 12px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:14, outline:"none" }}>
              {CATS.map(c => <option key={c} value={c}>{c.replace(/_/g," ")}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display:"block", fontSize:13, color:T.textSec, marginBottom:5 }}>Resolution</label>
            <select value={res} onChange={e=>setRes(e.target.value)} style={{ width:"100%", padding:"8px 12px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:14, outline:"none" }}>
              <option value="autonomous">Autonomous</option>
              <option value="hitl">HITL</option>
              <option value="human">Human</option>
            </select>
          </div>
        </div>
        <label style={{ display:"block", fontSize:13, color:T.textSec, marginBottom:5 }}>Notes (optional)</label>
        <textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Add any notes for the record..." rows={2}
          style={{ width:"100%", padding:"8px 12px", borderRadius:6, border:`1px solid ${T.border}`, background:T.surface, color:T.textPri, fontSize:14, resize:"vertical", outline:"none", marginBottom:14, fontFamily:"'EB Garamond',serif" }} />
        <div style={{ display:"flex", gap:10 }}>
          <button onClick={()=>onDecide(item.queue_id,true,{override_category:cat,override_resolution:res,notes})} disabled={submitting}
            style={{ flex:1, padding:"10px", borderRadius:7, border:"none", background:T.green, color:"#fff", fontWeight:600, cursor:"pointer", fontSize:15, fontFamily:"'EB Garamond',serif", opacity:submitting?0.6:1 }}>
            Approve
          </button>
          <button onClick={()=>onDecide(item.queue_id,false,{override_category:cat,override_resolution:res,notes})} disabled={submitting}
            style={{ flex:1, padding:"10px", borderRadius:7, border:"none", background:T.red, color:"#fff", fontWeight:600, cursor:"pointer", fontSize:15, fontFamily:"'EB Garamond',serif", opacity:submitting?0.6:1 }}>
            Override
          </button>
        </div>
      </PanelSection>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────
// ── Dashboard chart widgets (hand-drawn SVG, no chart lib) ────
function DPanel({ title, children, T }) {
  return (
    <div style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"14px 16px", boxShadow:T.shadow }}>
      <div style={{ fontSize:13, fontWeight:600, color:T.textSec, marginBottom:12 }}>{title}</div>
      {children}
    </div>
  );
}

function TrendChart({ data, T }) {
  const w = 720, h = 150, pad = 26;
  const n = data.length;
  if (!n) return null;
  const max = Math.max(1, ...data.map(d => Math.max(d.created, d.resolved)));
  const x = i => pad + (i * (w - 2*pad)) / Math.max(1, n-1);
  const y = v => h - pad - (v / max) * (h - 2*pad);
  const poly = key => data.map((d,i) => `${x(i)},${y(d[key])}`).join(" ");
  const area = `${pad},${h-pad} ` + data.map((d,i)=>`${x(i)},${y(d.created)}`).join(" ") + ` ${x(n-1)},${h-pad}`;
  return (
    <div style={{ width:"100%", overflowX:"auto" }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width:"100%", maxWidth:w, height:h }}>
        <polygon points={area} fill={T.accent+"22"} />
        <polyline points={poly("created")} fill="none" stroke={T.accent} strokeWidth="2.5" />
        <polyline points={poly("resolved")} fill="none" stroke={T.green} strokeWidth="2" strokeDasharray="5 3" />
        {data.map((d,i)=> <circle key={i} cx={x(i)} cy={y(d.created)} r="2.5" fill={T.accent} />)}
      </svg>
      <div style={{ display:"flex", gap:18, fontSize:12, color:T.textSec, marginTop:2 }}>
        <span><span style={{ color:T.accent }}>●</span> Created</span>
        <span><span style={{ color:T.green }}>▬</span> Resolved</span>
        <span style={{ marginLeft:"auto", color:T.textMut }}>{data[0]?.date} → {data[n-1]?.date}</span>
      </div>
    </div>
  );
}

function Donut({ segments, T }) {
  const total = segments.reduce((a,s)=>a+s.value,0) || 1;
  const r = 42, c = 2*Math.PI*r; let offset = 0;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:14 }}>
      <svg viewBox="0 0 110 110" style={{ width:92, height:92, flexShrink:0 }}>
        <g transform="translate(55,55) rotate(-90)">
          <circle r={r} fill="none" stroke={T.borderLt} strokeWidth="14" />
          {segments.map((s,i)=>{
            const len = (s.value/total)*c;
            const el = <circle key={i} r={r} fill="none" stroke={s.color} strokeWidth="14" strokeDasharray={`${len} ${c-len}`} strokeDashoffset={-offset} strokeLinecap="butt" />;
            offset += len; return el;
          })}
        </g>
        <text x="55" y="61" textAnchor="middle" fontSize="22" fontWeight="700" fill={T.textPri}>{total}</text>
      </svg>
      <div>
        {segments.map((s,i)=>(
          <div key={i} style={{ fontSize:12.5, color:T.textSec, marginBottom:3 }}>
            <span style={{ color:s.color }}>●</span> {s.label} — {s.value} ({Math.round(100*s.value/total)}%)
          </div>
        ))}
      </div>
    </div>
  );
}

function PriorityBars({ pri, T }) {
  const order = [["critical",T.red],["high",T.amber],["medium",T.blue],["low",T.textMut]];
  const max = Math.max(1, ...order.map(([k])=>pri?.[k]||0));
  return (
    <div>
      {order.map(([k,col])=>(
        <div key={k} style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
          <span style={{ width:66, fontSize:12.5, color:T.textSec, textTransform:"capitalize" }}>{k}</span>
          <div style={{ flex:1, height:8, background:T.borderLt, borderRadius:4, overflow:"hidden" }}>
            <div style={{ width:`${100*(pri?.[k]||0)/max}%`, height:"100%", background:col, borderRadius:4 }} />
          </div>
          <span style={{ width:26, textAlign:"right", fontSize:12, color:T.textMut }}>{pri?.[k]||0}</span>
        </div>
      ))}
    </div>
  );
}

function SlaGauge({ sla, T }) {
  const pct = sla?.compliance_pct;
  const col = pct==null ? T.textMut : pct>=90 ? T.green : pct>=70 ? T.amber : T.red;
  return (
    <div style={{ textAlign:"center" }}>
      <div style={{ fontSize:34, fontWeight:700, color:col }}>{pct==null?"—":pct+"%"}</div>
      <div style={{ fontSize:12, color:T.textMut, marginBottom:10 }}>resolved within SLA</div>
      <div style={{ height:8, background:T.redLt, borderRadius:4, overflow:"hidden" }}>
        <div style={{ width:`${pct||0}%`, height:"100%", background:col }} />
      </div>
      <div style={{ fontSize:11.5, color:T.textSec, marginTop:6 }}>{sla?.met||0} on time · {sla?.late||0} late</div>
    </div>
  );
}

function FeedbackRatio({ fb, T }) {
  const total = (fb?.up||0)+(fb?.down||0);
  const pct = total ? Math.round(100*(fb.up||0)/total) : null;
  const col = pct==null ? T.textMut : pct>=70 ? T.green : pct>=40 ? T.amber : T.red;
  return (
    <div style={{ textAlign:"center" }}>
      <div style={{ fontSize:34, fontWeight:700, color:col }}>{pct==null?"—":pct+"%"}</div>
      <div style={{ fontSize:12, color:T.textMut, marginBottom:12 }}>found solutions helpful</div>
      <div style={{ display:"flex", gap:18, justifyContent:"center", fontSize:15, color:T.textSec }}>
        <span>👍 {fb?.up||0}</span><span>👎 {fb?.down||0}</span>
      </div>
    </div>
  );
}

function DashboardView({ T }) {
  const [stats, setStats]     = useState(null);
  const [hitl, setHitl]       = useState(null);
  const [perf, setPerf]       = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, h, p, a] = await Promise.all([
        authFetch(`/api/metrics/dashboard`).then(r=>r.json()),
        authFetch(`/api/review/stats`).then(r=>r.json()),
        authFetch(`/api/metrics/model-performance`).then(r=>r.json()),
        authFetch(`/api/metrics/analytics`).then(r=>r.json()),
      ]);
      setStats(s); setHitl(h); setPerf(p); setAnalytics(a);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", color:T.textMut, fontStyle:"italic" }}>Loading metrics...</div>;

  const total   = stats?.total_tickets || 0;
  const routing = stats?.routing || {};
  const topCats = stats?.top_categories || [];
  const maxCount = Math.max(...topCats.map(c=>c.count), 1);
  const pct = n => total && n ? ((n/total)*100).toFixed(0)+"%" : "0%";

  const dashTabs = [
    { id:"overview",     label:"Overview" },
    { id:"model",        label:"Model Performance" },
  ];

  return (
    <div style={{ height:"100%", display:"flex", flexDirection:"column", background:T.bg }}>
      <div style={{ padding:"16px 28px 0", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", justifyContent:"space-between", alignItems:"flex-end" }}>
        <div style={{ display:"flex", gap:2 }}>
          {dashTabs.map(t => (
            <button key={t.id} onClick={()=>setActiveTab(t.id)} style={{
              padding:"8px 16px", border:"none", cursor:"pointer", fontSize:14,
              background:"transparent", color: activeTab===t.id?T.accentText:T.textSec,
              fontFamily:"'EB Garamond',serif", fontWeight: activeTab===t.id?600:400,
              borderBottom: activeTab===t.id?`2px solid ${T.accent}`:"2px solid transparent",
              transition:"all 0.12s",
            }}>{t.label}</button>
          ))}
        </div>
        <button className="btn-ghost" onClick={load} style={{ fontSize:12, padding:"5px 12px", marginBottom:8 }}>Refresh</button>
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:"24px 28px" }}>
        {activeTab === "overview" && (
          <>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))", gap:12, marginBottom:28 }}>
              <StatCard label="Total Tickets"    value={total}                    T={T} />
              <StatCard label="Auto-resolved"    value={routing.autonomous||0}    sub={pct(routing.autonomous)}  color={T.green} T={T} />
              <StatCard label="HITL Queue"       value={routing.hitl||0}          sub={pct(routing.hitl)}        color={T.amber} T={T} />
              <StatCard label="Human-only"       value={routing.human||0}         sub={pct(routing.human)}       color={T.red}   T={T} />
              <StatCard label="Pending Review"   value={hitl?.pending||0}         color={T.blue}  T={T} />
              <StatCard label="SLA Breached"     value={hitl?.sla_breached||0}    color={T.red}   T={T} />
              <StatCard label="Correction Rate"  value={hitl?((hitl.correction_rate||0)*100).toFixed(1)+"%":"0%"} color={T.blue} T={T} />
              {stats?.avg_resolution_hours != null && (
                <StatCard label="Avg Resolution"   value={`${stats.avg_resolution_hours}h`} color={T.green} T={T} />
              )}
            </div>

            {analytics && (
              <>
                <h3 style={{ fontSize:16, fontWeight:600, color:T.textPri, marginBottom:14 }}>Tickets — last 14 days</h3>
                <div style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"16px", boxShadow:T.shadow, marginBottom:20 }}>
                  <TrendChart data={analytics.trend} T={T} />
                </div>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))", gap:16, marginBottom:28 }}>
                  <DPanel title="Routing mix" T={T}>
                    <Donut T={T} segments={[
                      { label:"Autonomous", value:routing.autonomous||0, color:T.green },
                      { label:"HITL", value:routing.hitl||0, color:T.amber },
                      { label:"Human", value:routing.human||0, color:T.red },
                    ]} />
                  </DPanel>
                  <DPanel title="Priority mix" T={T}><PriorityBars pri={analytics.priority} T={T} /></DPanel>
                  <DPanel title="SLA compliance" T={T}><SlaGauge sla={analytics.sla} T={T} /></DPanel>
                  <DPanel title="User feedback" T={T}><FeedbackRatio fb={analytics.feedback} T={T} /></DPanel>
                </div>
              </>
            )}

            <h3 style={{ fontSize:16, fontWeight:600, color:T.textPri, marginBottom:14 }}>Top Categories</h3>
            {topCats.length===0 && <div style={{ color:T.textMut, fontStyle:"italic", fontSize:14 }}>No ticket data yet.</div>}
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {topCats.map(({ category, count }) => (
                <div key={category} style={{ display:"flex", alignItems:"center", gap:14 }}>
                  <span style={{ width:170, fontSize:14, color:T.textSec, flexShrink:0 }}>{category.replace(/_/g," ")}</span>
                  <div style={{ flex:1, height:6, background:T.borderLt, borderRadius:3, overflow:"hidden" }}>
                    <div style={{ width:`${(count/maxCount)*100}%`, height:"100%", background:T.accent, borderRadius:3, transition:"width 0.6s ease" }} />
                  </div>
                  <span style={{ width:36, textAlign:"right", fontSize:13, color:T.textMut, fontFamily:"'DM Mono',monospace" }}>{count}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {activeTab === "model" && (
          <ModelPerformancePanel perf={perf} hitl={hitl} T={T} />
        )}
      </div>
    </div>
  );
}

function ModelPerformancePanel({ perf, hitl, T }) {
  if (!perf?.has_data) {
    return (
      <div style={{ textAlign:"center", padding:"60px 0" }}>
        <div style={{ fontSize:18, color:T.textSec, marginBottom:12 }}>No model metrics recorded yet</div>
        <div style={{ fontSize:14, color:T.textMut, maxWidth:420, margin:"0 auto", lineHeight:1.7 }}>
          Model performance data is recorded after each retraining run.
          The nightly retrainer runs at 2:00 AM UTC once {100} feedback samples are collected.
        </div>
        <div style={{ marginTop:24, padding:"16px 20px", background:T.surfaceAlt, borderRadius:8, border:`1px solid ${T.borderLt}`, display:"inline-block", textAlign:"left" }}>
          <div style={{ fontSize:13, color:T.textSec, marginBottom:6, fontWeight:600 }}>Current live stats</div>
          <div style={{ fontSize:14, color:T.textPri }}>Correction rate: <strong>{hitl?((hitl.correction_rate||0)*100).toFixed(1):0}%</strong></div>
          <div style={{ fontSize:14, color:T.textPri, marginTop:4 }}>Total feedback samples: <strong>{hitl?.total_feedback||0}</strong></div>
          <div style={{ fontSize:14, color:T.textPri, marginTop:4 }}>Samples needed to retrain: <strong>{Math.max(0,100-(hitl?.total_feedback||0))}</strong></div>
        </div>
      </div>
    );
  }

  const history = perf.history || [];

  return (
    <div>
      <h3 style={{ fontSize:18, fontWeight:600, color:T.textPri, marginBottom:20 }}>Model Performance Over Time</h3>

      {/* Current stats */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))", gap:12, marginBottom:28 }}>
        {history.length > 0 && (
          <>
            <StatCard label="Latest F1 Score"  value={history[history.length-1]?.f1?.toFixed(3)||"—"}  color={T.green} T={T} />
            <StatCard label="Latest Accuracy"  value={history[history.length-1]?.accuracy?.toFixed(3)||"—"} color={T.blue} T={T} />
          </>
        )}
        <StatCard label="Correction Rate"  value={hitl?((hitl.correction_rate||0)*100).toFixed(1)+"%":"0%"} color={T.amber} T={T} />
        <StatCard label="Total Feedback"   value={hitl?.total_feedback||0} color={T.textSec} T={T} />
      </div>

      {/* History table */}
      <h4 style={{ fontSize:15, fontWeight:600, color:T.textPri, marginBottom:12 }}>Retraining History</h4>
      <div style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, overflow:"hidden", boxShadow:T.shadow }}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr 1fr", padding:"10px 16px", background:T.surfaceAlt, borderBottom:`1px solid ${T.borderLt}` }}>
          {["Date","F1 Score","Accuracy","Correction Rate","Samples"].map(h => (
            <span key={h} style={{ fontSize:12, fontWeight:600, color:T.textMut, textTransform:"uppercase", letterSpacing:"0.05em" }}>{h}</span>
          ))}
        </div>
        {history.map((row,i) => (
          <div key={i} style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr 1fr", padding:"10px 16px", borderBottom: i<history.length-1?`1px solid ${T.borderLt}`:"none" }}>
            <span style={{ fontSize:14, color:T.textSec }}>{row.date}</span>
            <span style={{ fontSize:14, color:T.green, fontFamily:"'DM Mono',monospace" }}>{row.f1?.toFixed(3)||"—"}</span>
            <span style={{ fontSize:14, color:T.blue,  fontFamily:"'DM Mono',monospace" }}>{row.accuracy?.toFixed(3)||"—"}</span>
            <span style={{ fontSize:14, color:T.amber, fontFamily:"'DM Mono',monospace" }}>{row.correction_rate?((row.correction_rate)*100).toFixed(1)+"%":"—"}</span>
            <span style={{ fontSize:14, color:T.textSec, fontFamily:"'DM Mono',monospace" }}>{row.total_samples||"—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Shared components ─────────────────────────────────────────
function PanelSection({ title, children, T }) {
  return (
    <div style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:8, padding:"16px 18px", marginBottom:14, boxShadow:T.shadow }}>
      <div style={{ fontSize:11, fontWeight:600, color:T.textMut, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12 }}>{title}</div>
      {children}
    </div>
  );
}

function Tag({ label, accent, T }) {
  return (
    <span style={{ fontSize:12, padding:"2px 10px", borderRadius:999, fontWeight:500, background:accent?T.accentLt:T.surfaceAlt, color:accent?T.accentText:T.textSec, border:`1px solid ${accent?T.accent+"33":T.border}` }}>
      {label}
    </span>
  );
}

function StatCard({ label, value, sub, color, T }) {
  return (
    <div style={{ background:T.surface, border:`1px solid ${T.borderLt}`, borderRadius:10, padding:"16px 18px", boxShadow:T.shadow }}>
      <div style={{ fontSize:11, color:T.textMut, marginBottom:6, textTransform:"uppercase", letterSpacing:"0.06em" }}>{label}</div>
      <div style={{ fontSize:26, fontWeight:600, color:color||T.textPri, letterSpacing:"-0.5px" }}>{value}</div>
      {sub && <div style={{ fontSize:12, color:T.textMut, marginTop:3 }}>{sub} of total</div>}
    </div>
  );
}

// ── App shell ─────────────────────────────────────────────────
export default function App() {
  const [user, setUser]     = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [tab, setTab]       = useState("chat");
  const [dark, setDark]     = useState(false);
  const [sessionId]         = useState(() => {
    const ex = sessionStorage.getItem("ticketai_session_id");
    if (ex) return ex;
    const id = `sess_${Math.random().toString(36).slice(2,10)}`;
    sessionStorage.setItem("ticketai_session_id", id);
    return id;
  });

  // Restore session from a stored token on load.
  useEffect(() => {
    const tok = getToken();
    if (!tok) { setAuthChecked(true); return; }
    authFetch("/api/auth/me")
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(u => setUser(u))
      .catch(() => setToken(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const logout = () => { setToken(null); setUser(null); };

  const T = dark ? THEMES.dark : THEMES.light;

  const isAdmin = user?.role === "admin";
  const isDept  = user?.role === "department";

  const clientTabs = [
    { id:"chat",      label:"Support Chat" },
    { id:"tickets",   label:"My Tickets" },
  ];
  const adminTabs = [
    { id:"review",    label:"Review Queue" },
    { id:"tickets",   label:"All Tickets" },
    { id:"dashboard", label:"Dashboard" },
  ];
  const deptTabs = [
    { id:"review",    label:"Review Queue" },
    { id:"tickets",   label:`${user?.department||"Dept"} Tickets` },
    { id:"dashboard", label:"Dashboard" },
  ];
  const tabs = isAdmin ? adminTabs : isDept ? deptTabs : clientTabs;

  useEffect(() => {
    if (user) setTab((isAdmin || isDept) ? "review" : "chat");
  }, [user]);

  if (!authChecked) return (
    <>
      <style>{buildCss(T)}</style>
      <div style={{ height:"100vh", display:"flex", alignItems:"center", justifyContent:"center", background:T.bg, color:T.textMut }}>Loading…</div>
    </>
  );

  if (!user) return (
    <>
      <style>{buildCss(T)}</style>
      <LoginScreen onLogin={setUser} T={T} />
    </>
  );

  return (
    <>
      <style>{buildCss(T)}</style>
      <div style={{ height:"100vh", display:"flex", flexDirection:"column", background:T.bg }}>
        {/* Top bar */}
        <div style={{ background:T.surface, borderBottom:`1px solid ${T.border}`, padding:"0 20px", display:"flex", alignItems:"center", gap:20, height:50, flexShrink:0, boxShadow:"0 1px 0 rgba(0,0,0,0.06)" }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ width:26, height:26, borderRadius:6, background:T.accent, display:"flex", alignItems:"center", justifyContent:"center", fontSize:12, color:"#fff", fontWeight:700 }}>T</div>
            <span style={{ fontWeight:600, fontSize:16, color:T.textPri, letterSpacing:"-0.2px" }}>TicketAI</span>
          </div>

          <div style={{ flex:1, display:"flex", gap:2 }}>
            {tabs.map(t => (
              <button key={t.id} onClick={()=>setTab(t.id)} style={{
                padding:"6px 14px", borderRadius:6, border:"none", cursor:"pointer",
                fontSize:14, background: tab===t.id?T.accentLt:"transparent",
                color: tab===t.id?T.accentText:T.textSec,
                fontFamily:"'EB Garamond',serif", fontWeight: tab===t.id?600:400,
                transition:"all 0.12s",
              }}>{t.label}</button>
            ))}
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            {/* Dark mode toggle */}
            <button onClick={()=>setDark(d=>!d)} style={{
              padding:"4px 10px", borderRadius:20, border:`1px solid ${T.border}`,
              background:T.surfaceAlt, color:T.textSec, cursor:"pointer",
              fontSize:13, display:"flex", alignItems:"center", gap:5,
            }}>
              <span style={{ fontSize:14 }}>{dark?"☀":"☾"}</span>
              <span>{dark?"Light":"Dark"}</span>
            </button>
            <div style={{ fontSize:13, color:T.textSec, padding:"4px 10px", borderRadius:999, background:T.surfaceAlt, border:`1px solid ${T.border}` }}>
              {isAdmin?"Admin":isDept?`${user.department} agent`:"Client"} — {user.username}
            </div>
            <button className="btn-ghost" onClick={logout} style={{ fontSize:13, padding:"4px 12px" }}>Sign out</button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex:1, overflow:"hidden" }}>
          {tab==="chat"      && <ChatView T={T} />}
          {tab==="tickets"   && (isAdmin ? <AdminWorkspace T={T} /> : isDept ? <DeptTicketsView user={user} T={T} /> : <MyTicketsView sessionId={sessionId} isAdmin={isAdmin} T={T} />)}
          {tab==="review"    && <ReviewView T={T} />}
          {tab==="dashboard" && <DashboardView T={T} />}
        </div>
      </div>
    </>
  );
}
