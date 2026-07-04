/* TicketAI — professional deck (UPS brown & gold). */
const path = require("path");
const GROOT = require("child_process").execSync("npm root -g").toString().trim();
const req = (m) => require(path.join(GROOT, m));
const pptxgen = req("pptxgenjs");
const React = req("react");
const ReactDOMServer = req("react-dom/server");
const sharp = req("sharp");
const FA = req("react-icons/fa");

// ── Palette (UPS brown + gold) ───────────────────────────────────────────
const BROWN_DARK = "271710"; // deep espresso (title / section / closing bg)
const BROWN      = "3A2417";
const BROWN_MID  = "6B4A30";
const GOLD       = "F2A900"; // UPS gold
const GOLD_LT    = "FFC83D";
const WHITE      = "FFFFFF";
const CREAM      = "FAF5EE"; // warm panel (brand-justified)
const INK        = "271710"; // text on light
const MUTED      = "8C7B6C"; // warm gray caption
const LINE       = "E9E0D6";
const GREEN      = "2E7D52";
const AMBER      = "C9821A";
const RED        = "B0432F";

const LOGO = path.join(__dirname, "assets", "ups-logo.png");
const LOGO_AR = 400 / 480; // w/h

const HFONT = "Georgia";
const BFONT = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
const PW = 13.333, PH = 7.5;
pres.author = "TicketAI";
pres.title = "TicketAI — Hybrid AI Ticket Triage";

const shadow = () => ({ type: "outer", color: "000000", blur: 9, offset: 3, angle: 90, opacity: 0.16 });

// ── Icon rasteriser ──────────────────────────────────────────────────────
const iconCache = {};
async function icon(name, color) {
  const key = name + color;
  if (iconCache[key]) return iconCache[key];
  const Comp = FA[name];
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + color, size: "256" })
  );
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  const data = "image/png;base64," + png.toString("base64");
  iconCache[key] = data;
  return data;
}

// ── Reusable bits ──────────────────────────────────────────────────────────
function logo(slide, x, y, h) {
  slide.addImage({ path: LOGO, x, y, w: h * LOGO_AR, h });
}
function footer(slide, n) {
  logo(slide, 0.45, PH - 0.62, 0.34);
  slide.addText("TicketAI", { x: 0.85, y: PH - 0.62, w: 3, h: 0.34, fontFace: HFONT,
    fontSize: 10, color: MUTED, valign: "middle", margin: 0 });
  slide.addText(String(n), { x: PW - 0.9, y: PH - 0.62, w: 0.45, h: 0.34, fontFace: BFONT,
    fontSize: 10, color: MUTED, align: "right", valign: "middle" });
}
// Eyebrow + title block for content slides
function head(slide, eyebrow, title) {
  slide.addText(eyebrow.toUpperCase(), { x: 0.7, y: 0.5, w: 11, h: 0.3, fontFace: BFONT,
    fontSize: 12, bold: true, color: GOLD, charSpacing: 3, margin: 0 });
  slide.addText(title, { x: 0.7, y: 0.78, w: 12, h: 0.7, fontFace: HFONT,
    fontSize: 30, bold: true, color: INK, margin: 0 });
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 1 — TITLE
// ════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BROWN_DARK };
  // gold corner accent block (bottom-right, subtle)
  s.addShape(pres.shapes.RECTANGLE, { x: PW - 0.18, y: 0, w: 0.18, h: PH, fill: { color: GOLD } });
  s.addShape(pres.shapes.OVAL, { x: PW - 5.6, y: PH - 5.2, w: 7.4, h: 7.4,
    fill: { color: BROWN }, line: { color: BROWN } });

  logo(s, 0.9, 0.85, 1.55);

  s.addText("AI-POWERED IT SERVICE DESK", { x: 0.95, y: 2.95, w: 9, h: 0.35, fontFace: BFONT,
    fontSize: 14, bold: true, color: GOLD, charSpacing: 4, margin: 0 });
  s.addText("TicketAI", { x: 0.9, y: 3.3, w: 11, h: 1.25, fontFace: HFONT,
    fontSize: 72, bold: true, color: WHITE, margin: 0 });
  s.addText("Hybrid AI for Ticket Triage, Routing & Autonomous Resolution",
    { x: 0.95, y: 4.65, w: 10.5, h: 0.6, fontFace: HFONT, fontSize: 22, italic: true,
      color: "E7DCCF", margin: 0 });

  // bottom strip facts
  const facts = [["100%", "local & private"], ["$0", "cloud cost"], ["3", "AI models"], ["5", "departments"]];
  let fx = 0.95;
  facts.forEach(([a, b]) => {
    s.addText(a, { x: fx, y: 5.85, w: 1.5, h: 0.55, fontFace: HFONT, fontSize: 30, bold: true,
      color: GOLD, margin: 0 });
    s.addText(b, { x: fx, y: 6.42, w: 2.2, h: 0.35, fontFace: BFONT, fontSize: 12, color: "C9BBAC", margin: 0 });
    fx += 2.45;
  });
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 2 — PROBLEM STATEMENT
// ════════════════════════════════════════════════════════════════════════
async function slideProblem() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  head(s, "The Problem", "IT support desks can't keep up");
  s.addText("Every employee request becomes a manual ticket. Agents read, categorise, prioritise and route each one by hand — slow, inconsistent, and impossible after hours.",
    { x: 0.7, y: 1.55, w: 7.0, h: 1.0, fontFace: BFONT, fontSize: 16, color: BROWN_MID, lineSpacingMultiple: 1.15, margin: 0 });

  const items = [
    ["FaClock", "Slow first response", "Manual triage means simple, fixable issues wait in a queue for hours."],
    ["FaRandom", "Misrouted tickets", "Vague requests land in the wrong team and bounce around before action."],
    ["FaUserClock", "No after-hours cover", "Outside office hours nothing moves — even a password reset waits till morning."],
    ["FaCoins", "High cost per ticket", "Skilled agents spend time on repetitive, low-value classification work."],
  ];
  let y = 1.7;
  for (const [ic, t, d] of items) {
    s.addShape(pres.shapes.OVAL, { x: 8.0, y, w: 0.62, h: 0.62, fill: { color: CREAM }, line: { color: GOLD, width: 1 } });
    s.addImage({ data: await icon(ic, AMBER), x: 8.13, y: y + 0.13, w: 0.36, h: 0.36 });
    s.addText(t, { x: 8.8, y: y - 0.02, w: 4.2, h: 0.34, fontFace: HFONT, fontSize: 16, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: 8.8, y: y + 0.32, w: 4.25, h: 0.7, fontFace: BFONT, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.05, margin: 0 });
    y += 1.28;
  }

  // big stat callout (left lower)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 4.45, w: 6.9, h: 2.05, fill: { color: BROWN_DARK }, shadow: shadow() });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 4.45, w: 0.12, h: 2.05, fill: { color: GOLD } });
  s.addText("≈ 40%", { x: 1.05, y: 4.65, w: 3.0, h: 0.95, fontFace: HFONT, fontSize: 54, bold: true, color: GOLD, margin: 0 });
  s.addText("of help-desk tickets are repetitive, low-risk issues that could be resolved automatically — if something could safely decide which ones.",
    { x: 4.0, y: 4.7, w: 3.4, h: 1.6, fontFace: BFONT, fontSize: 13.5, color: "EADFD1", valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  footer(s, 2);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 3 — THE SOLUTION (value props)
// ════════════════════════════════════════════════════════════════════════
async function slideSolution() {
  const s = pres.addSlide();
  s.background = { color: CREAM };
  head(s, "The Solution", "An AI agent that handles the whole ticket");
  s.addText("TicketAI chats with the user, understands the real problem, classifies and routes it to the right department — and safely resolves the routine ones on its own.",
    { x: 0.7, y: 1.5, w: 12, h: 0.6, fontFace: BFONT, fontSize: 16, color: BROWN_MID, margin: 0 });

  const cards = [
    ["FaComments", "Understands", "Tells a greeting from a keyword from a real ticket, then asks smart questions until the issue is clear."],
    ["FaBrain", "Classifies", "A fine-tuned DistilBERT model assigns the category in ~36 ms, with a local LLM as a second opinion."],
    ["FaSitemap", "Routes", "Each category maps to one of five departments — agents only ever see tickets that are theirs."],
    ["FaRobot", "Resolves", "Safe, routine tickets get step-by-step fixes generated on-device; risky ones go to a human."],
  ];
  const cw = 2.78, gap = 0.26, x0 = 0.7, cy = 2.35, ch = 4.05;
  let x = x0;
  for (const [ic, t, d] of cards) {
    s.addShape(pres.shapes.RECTANGLE, { x, y: cy, w: cw, h: ch, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y: cy, w: cw, h: 0.12, fill: { color: GOLD } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: cy + 0.42, w: 0.95, h: 0.95, fill: { color: BROWN_DARK } });
    s.addImage({ data: await icon(ic, GOLD), x: x + 0.55, y: cy + 0.67, w: 0.45, h: 0.45 });
    s.addText(t, { x: x + 0.3, y: cy + 1.55, w: cw - 0.6, h: 0.45, fontFace: HFONT, fontSize: 21, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.3, y: cy + 2.05, w: cw - 0.55, h: 1.8, fontFace: BFONT, fontSize: 13, color: BROWN_MID, lineSpacingMultiple: 1.18, margin: 0 });
    x += cw + gap;
  }
  footer(s, 3);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 4 — HOW IT WORKS (pipeline)
// ════════════════════════════════════════════════════════════════════════
async function slideFlow() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  head(s, "How It Works", "From a chat message to a resolved ticket");

  const steps = [
    ["FaCommentDots", "Intent", "Greeting, keyword\nor real ticket?"],
    ["FaQuestionCircle", "Intake", "Asks tailored\nquestions until clear"],
    ["FaBrain", "Classify", "DistilBERT + LLM\nassign the category"],
    ["FaSitemap", "Route", "Map category to the\nowning department"],
  ];
  const bw = 2.7, bh = 1.7, gy = 1.95, x0 = 0.7, gap = 0.42;
  let x = x0;
  for (let i = 0; i < steps.length; i++) {
    const [ic, t, d] = steps[i];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: gy, w: bw, h: bh, rectRadius: 0.1,
      fill: { color: CREAM }, line: { color: GOLD, width: 1.25 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.28, y: gy + 0.3, w: 0.66, h: 0.66, fill: { color: BROWN_DARK } });
    s.addImage({ data: await icon(ic, GOLD), x: x + 0.42, y: gy + 0.44, w: 0.38, h: 0.38 });
    s.addText(`${i + 1}`, { x: x + bw - 0.7, y: gy + 0.18, w: 0.55, h: 0.5, fontFace: HFONT, fontSize: 26, bold: true, color: "E2D3C2", align: "right", margin: 0 });
    s.addText(t, { x: x + 0.28, y: gy + 1.02, w: bw - 0.5, h: 0.34, fontFace: HFONT, fontSize: 17, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.28, y: gy + 1.34, w: bw - 0.45, h: 0.34, fontFace: BFONT, fontSize: 11.5, color: MUTED, margin: 0 });
    if (i < steps.length - 1) {
      s.addText("›", { x: x + bw - 0.02, y: gy + 0.45, w: gap, h: 0.8, fontFace: HFONT, fontSize: 34, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0 });
    }
    x += bw + gap;
  }

  // Decision row — three outcomes
  s.addText("The Decision Engine then picks one of three outcomes:", { x: 0.7, y: 4.05, w: 12, h: 0.35, fontFace: BFONT, fontSize: 14, bold: true, color: BROWN_MID, margin: 0 });
  const outs = [
    ["FaRobot", "Autonomous", GREEN, "Generates the fix in the user's language and resolves it on the spot."],
    ["FaUserCheck", "Human-in-the-loop", AMBER, "Queued for the owning department with an AI-suggested answer attached."],
    ["FaUserShield", "Human escalation", RED, "Sensitive or out-of-domain — sent straight to a person, no auto-action."],
  ];
  const ow = 3.77, og = 0.30; let ox = 0.7, oy = 4.5;
  for (const [ic, t, c, d] of outs) {
    s.addShape(pres.shapes.RECTANGLE, { x: ox, y: oy, w: ow, h: 1.75, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: ox, y: oy, w: 0.12, h: 1.75, fill: { color: c } });
    s.addImage({ data: await icon(ic, c), x: ox + 0.32, y: oy + 0.3, w: 0.5, h: 0.5 });
    s.addText(t, { x: ox + 1.0, y: oy + 0.32, w: ow - 1.1, h: 0.45, fontFace: HFONT, fontSize: 17, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: ox + 0.34, y: oy + 0.92, w: ow - 0.6, h: 0.75, fontFace: BFONT, fontSize: 12.5, color: BROWN_MID, lineSpacingMultiple: 1.1, margin: 0 });
    ox += ow + og;
  }
  footer(s, 4);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 5 — HYBRID AI ARCHITECTURE
// ════════════════════════════════════════════════════════════════════════
async function slideArch() {
  const s = pres.addSlide();
  s.background = { color: BROWN_DARK };
  s.addText("THE ENGINE", { x: 0.7, y: 0.5, w: 11, h: 0.3, fontFace: BFONT, fontSize: 12, bold: true, color: GOLD, charSpacing: 3, margin: 0 });
  s.addText("A hybrid of three local models", { x: 0.7, y: 0.78, w: 12, h: 0.7, fontFace: HFONT, fontSize: 30, bold: true, color: WHITE, margin: 0 });
  s.addText("Fast where speed matters, smart where nuance matters — and everything runs on the laptop's own GPU and CPU. No cloud, no API keys.",
    { x: 0.7, y: 1.5, w: 12, h: 0.55, fontFace: BFONT, fontSize: 15, color: "D9CBBB", margin: 0 });

  const cards = [
    ["FaBrain", "DistilBERT", "Category classifier", "Fine-tuned on 20 IT categories. Runs on CPU in ~36 ms — the fast primary path for most tickets."],
    ["FaRobot", "Qwen 2.5 (Ollama)", "Conversational LLM", "Drives intent, clarifying questions, solution steps and translation. GPU-accelerated at ~64 tok/s."],
    ["FaProjectDiagram", "nomic-embed-text", "Embeddings", "768-dim vectors flag duplicate and similar tickets so the same problem isn't solved twice."],
  ];
  const cw = 3.77, gap = 0.30; let x = 0.7, cy = 2.4, ch = 3.35;
  for (const [ic, t, sub, d] of cards) {
    s.addShape(pres.shapes.RECTANGLE, { x, y: cy, w: cw, h: ch, fill: { color: BROWN }, line: { color: BROWN_MID, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: cy + 0.4, w: 1.0, h: 1.0, fill: { color: GOLD } });
    s.addImage({ data: await icon(ic, BROWN_DARK), x: x + 0.62, y: cy + 0.67, w: 0.46, h: 0.46 });
    s.addText(t, { x: x + 0.35, y: cy + 1.55, w: cw - 0.6, h: 0.4, fontFace: HFONT, fontSize: 20, bold: true, color: WHITE, margin: 0 });
    s.addText(sub, { x: x + 0.35, y: cy + 1.96, w: cw - 0.6, h: 0.3, fontFace: BFONT, fontSize: 12, bold: true, color: GOLD, charSpacing: 1, margin: 0 });
    s.addText(d, { x: x + 0.35, y: cy + 2.32, w: cw - 0.6, h: 0.95, fontFace: BFONT, fontSize: 12.5, color: "D9CBBB", lineSpacingMultiple: 1.15, margin: 0 });
    x += cw + gap;
  }
  s.addText("Confidence < 0.70 on DistilBERT → the LLM is asked for a second opinion before routing.",
    { x: 0.7, y: 6.05, w: 12, h: 0.4, fontFace: BFONT, fontSize: 13, italic: true, color: GOLD, align: "center", margin: 0 });
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 6 — KEY FEATURES (grid)
// ════════════════════════════════════════════════════════════════════════
async function slideFeatures() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  head(s, "Key Features", "What it brings to the desk");

  const feats = [
    ["FaComments", "3-way intent", "Never raises a ticket from a single word like “vpn”."],
    ["FaQuestionCircle", "Clarify loop", "Keeps asking until the problem is genuinely understood."],
    ["FaSitemap", "Department routing", "Five teams, each scoped to their own categories."],
    ["FaShieldAlt", "Safety guards", "Physical damage & out-of-domain go to a human, not auto-fix."],
    ["FaGlobe", "Full localization", "The entire reply is translated into the user's language."],
    ["FaImage", "Screenshot OCR", "Reads attached screenshots to capture the issue."],
    ["FaChartPie", "Live dashboard", "Trends, SLA, priority mix & feedback — scoped per team."],
    ["FaLock", "Self-service auth", "JWT + bcrypt sign-up with role-based access."],
  ];
  const cols = 4, cw = 2.78, ch = 1.95, gx = 0.26, gy = 0.3, x0 = 0.7, y0 = 1.65;
  for (let i = 0; i < feats.length; i++) {
    const [ic, t, d] = feats[i];
    const c = i % cols, r = Math.floor(i / cols);
    const x = x0 + c * (cw + gx), y = y0 + r * (ch + gy);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: ch, fill: { color: CREAM }, line: { color: LINE, width: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.28, y: y + 0.3, w: 0.62, h: 0.62, fill: { color: BROWN_DARK } });
    s.addImage({ data: await icon(ic, GOLD), x: x + 0.41, y: y + 0.43, w: 0.36, h: 0.36 });
    s.addText(t, { x: x + 1.0, y: y + 0.32, w: cw - 1.1, h: 0.55, fontFace: HFONT, fontSize: 15, bold: true, color: INK, valign: "middle", margin: 0 });
    s.addText(d, { x: x + 0.28, y: y + 1.02, w: cw - 0.5, h: 0.8, fontFace: BFONT, fontSize: 11.5, color: BROWN_MID, lineSpacingMultiple: 1.1, margin: 0 });
  }
  footer(s, 6);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 7 — DEPARTMENT ROUTING
// ════════════════════════════════════════════════════════════════════════
async function slideDepartments() {
  const s = pres.addSlide();
  s.background = { color: CREAM };
  head(s, "Department Routing", "Every category has an owner");
  s.addText("The AI-assigned category decides the team. Department agents are hard-scoped — they only ever see their own tickets. Shared categories (e.g. Onboarding) appear for every owning team.",
    { x: 0.7, y: 1.5, w: 12, h: 0.55, fontFace: BFONT, fontSize: 15, color: BROWN_MID, margin: 0 });

  const depts = [
    ["TSG", "Tech Support Group", "VPN · Network · Email · Password · Printer · Software · Hardware · Performance · Security · +6"],
    ["BASE", "Facilities", "Facilities · Access requests · Onboarding · Offboarding"],
    ["HR-GO", "HR Global Operations", "Payroll · Compliance · Onboarding · Offboarding"],
    ["HR-BP", "HR Business Partner", "People & conduct · Compliance · Onboarding · Offboarding"],
    ["Finance", "Finance", "Billing & reimbursements"],
  ];
  let y = 2.3; const rh = 0.86;
  for (const [code, name, cats] of depts) {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 11.93, h: rh - 0.14, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 2.0, h: rh - 0.14, fill: { color: BROWN_DARK } });
    s.addText(code, { x: 0.7, y, w: 2.0, h: rh - 0.14, fontFace: HFONT, fontSize: 18, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0 });
    s.addText(name, { x: 2.95, y: y + 0.06, w: 3.4, h: rh - 0.26, fontFace: HFONT, fontSize: 16, bold: true, color: INK, valign: "middle", margin: 0 });
    s.addText(cats, { x: 6.4, y: y + 0.06, w: 6.05, h: rh - 0.26, fontFace: BFONT, fontSize: 12, color: BROWN_MID, valign: "middle", lineSpacingMultiple: 1.0, margin: 0 });
    y += rh;
  }
  footer(s, 7);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 8 — TECH STACK
// ════════════════════════════════════════════════════════════════════════
async function slideStack() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  head(s, "Technology", "Built on a lean, local stack");

  const groups = [
    ["FaBrain", "AI / ML", ["DistilBERT (fine-tuned)", "Ollama · Qwen 2.5 3B", "nomic-embed-text", "Tesseract OCR"]],
    ["FaServer", "Backend", ["FastAPI + Uvicorn (async)", "PostgreSQL 17 + asyncpg", "SQLAlchemy (async ORM)", "JWT (PyJWT) + bcrypt"]],
    ["FaDesktop", "Frontend", ["React (Create React App)", "Single-page chat UI", "Role-based dashboards", "Localized interface"]],
    ["FaCogs", "Operations", ["Prometheus metrics", "APScheduler retraining", "Async SLA watchdog", "Audit & feedback logs"]],
  ];
  const cw = 2.78, gap = 0.26; let x = 0.7, cy = 1.7, ch = 4.4;
  for (const [ic, t, items] of groups) {
    s.addShape(pres.shapes.RECTANGLE, { x, y: cy, w: cw, h: ch, fill: { color: CREAM }, line: { color: LINE, width: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.32, y: cy + 0.35, w: 0.85, h: 0.85, fill: { color: BROWN_DARK } });
    s.addImage({ data: await icon(ic, GOLD), x: x + 0.54, y: cy + 0.57, w: 0.41, h: 0.41 });
    s.addText(t, { x: x + 0.32, y: cy + 1.32, w: cw - 0.6, h: 0.4, fontFace: HFONT, fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addShape(pres.shapes.LINE, { x: x + 0.32, y: cy + 1.78, w: cw - 0.64, h: 0, line: { color: GOLD, width: 1.5 } });
    s.addText(items.map((it, i) => ({ text: it, options: { bullet: { code: "2022", indent: 14 }, breakLine: true, paraSpaceAfter: 8 } })),
      { x: x + 0.34, y: cy + 1.95, w: cw - 0.55, h: 2.3, fontFace: BFONT, fontSize: 12.5, color: BROWN_MID, margin: 0 });
    x += cw + gap;
  }
  footer(s, 8);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 9 — RESULTS & METRICS
// ════════════════════════════════════════════════════════════════════════
async function slideResults() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  head(s, "Results", "Tested and measured");

  // four stat callouts (top)
  const stats = [
    ["100%", "Category accuracy", "on clearly-worded tickets"],
    ["~36 ms", "Classification time", "DistilBERT on CPU"],
    ["~7 s", "Full auto-resolution", "intake to solution"],
    ["100%", "Intent detection", "greeting / keyword / ticket"],
  ];
  const cw = 2.78, gap = 0.26; let x = 0.7, sy = 1.7;
  for (const [a, b, c] of stats) {
    s.addShape(pres.shapes.RECTANGLE, { x, y: sy, w: cw, h: 1.7, fill: { color: BROWN_DARK }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y: sy, w: cw, h: 0.1, fill: { color: GOLD } });
    s.addText(a, { x: x + 0.05, y: sy + 0.22, w: cw - 0.1, h: 0.7, fontFace: HFONT, fontSize: 38, bold: true, color: GOLD, align: "center", margin: 0 });
    s.addText(b, { x: x + 0.1, y: sy + 0.95, w: cw - 0.2, h: 0.32, fontFace: BFONT, fontSize: 13.5, bold: true, color: WHITE, align: "center", margin: 0 });
    s.addText(c, { x: x + 0.1, y: sy + 1.27, w: cw - 0.2, h: 0.3, fontFace: BFONT, fontSize: 11, color: "C9BBAC", align: "center", margin: 0 });
    x += cw + gap;
  }

  // chart — classification accuracy by ticket difficulty
  s.addText("Classification accuracy", { x: 0.7, y: 3.75, w: 6, h: 0.35, fontFace: HFONT, fontSize: 16, bold: true, color: INK, margin: 0 });
  s.addChart(pres.charts.BAR, [{
    name: "Accuracy", labels: ["Clear tickets", "Hard tickets", "Routing class"], values: [100, 75, 100],
  }], {
    x: 0.6, y: 4.15, w: 6.2, h: 2.7, barDir: "col",
    chartColors: [GOLD],
    valAxisMinVal: 0, valAxisMaxVal: 100,
    catAxisLabelColor: BROWN_MID, valAxisLabelColor: MUTED, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: INK, dataLabelFontBold: true, dataLabelFontSize: 12,
    showLegend: false, showTitle: false,
  });

  // right column — narrative
  s.addShape(pres.shapes.RECTANGLE, { x: 7.2, y: 4.15, w: 5.4, h: 2.7, fill: { color: CREAM }, line: { color: LINE, width: 1 } });
  s.addText("Why this matters", { x: 7.5, y: 4.32, w: 5, h: 0.35, fontFace: HFONT, fontSize: 15, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "Even when the exact category is hard to guess, the ", options: {} },
    { text: "routing class is right 100% of the time", options: { bold: true, color: BROWN } },
    { text: " — so a ticket always reaches the correct team, and a safe one is never auto-resolved by mistake.", options: {} },
  ], { x: 7.5, y: 4.75, w: 4.9, h: 1.95, fontFace: BFONT, fontSize: 13.5, color: BROWN_MID, lineSpacingMultiple: 1.25, valign: "top", margin: 0 });
  footer(s, 9);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 10 — ROADMAP
// ════════════════════════════════════════════════════════════════════════
async function slideRoadmap() {
  const s = pres.addSlide();
  s.background = { color: CREAM };
  head(s, "Roadmap", "Where it goes next");

  const items = [
    ["FaCloud", "Always-on hosting", "Deploy single-service build to the cloud with a hosted LLM fallback — no PC required."],
    ["FaPlug", "Real integrations", "Swap simulated workflows for live ServiceNow, Okta, Intune & M365 actions."],
    ["FaVial", "Automated test suite", "Lock in intent, routing and guard behaviour with a pytest regression suite."],
    ["FaCode", "Modular frontend", "Split the single-file UI into components for maintainability and scale."],
  ];
  const cw = 5.9, gx = 0.25, gy = 0.3, x0 = 0.7, y0 = 1.8, ch = 2.1;
  for (let i = 0; i < items.length; i++) {
    const [ic, t, d] = items[i];
    const x = x0 + (i % 2) * (cw + gx), y = y0 + Math.floor(i / 2) * (ch + gy);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: ch, fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.12, h: ch, fill: { color: GOLD } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.4, y: y + 0.55, w: 1.0, h: 1.0, fill: { color: BROWN_DARK } });
    s.addImage({ data: await icon(ic, GOLD), x: x + 0.66, y: y + 0.81, w: 0.48, h: 0.48 });
    s.addText(`0${i + 1}`, { x: x + cw - 1.3, y: y + 0.2, w: 1.1, h: 0.7, fontFace: HFONT, fontSize: 40, bold: true, color: "EFE4D6", align: "right", margin: 0 });
    s.addText(t, { x: x + 1.65, y: y + 0.5, w: cw - 1.9, h: 0.5, fontFace: HFONT, fontSize: 19, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 1.65, y: y + 1.02, w: cw - 1.95, h: 0.9, fontFace: BFONT, fontSize: 13, color: BROWN_MID, lineSpacingMultiple: 1.15, margin: 0 });
  }
  footer(s, 10);
}

// ════════════════════════════════════════════════════════════════════════
// SLIDE 11 — CLOSING
// ════════════════════════════════════════════════════════════════════════
function slideClosing() {
  const s = pres.addSlide();
  s.background = { color: BROWN_DARK };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.18, h: PH, fill: { color: GOLD } });
  s.addShape(pres.shapes.OVAL, { x: -2.6, y: -2.6, w: 6.5, h: 6.5, fill: { color: BROWN }, line: { color: BROWN } });

  logo(s, PW - 3.0, 0.9, 1.5);
  s.addText("THANK YOU", { x: 1.1, y: 2.55, w: 9, h: 0.4, fontFace: BFONT, fontSize: 15, bold: true, color: GOLD, charSpacing: 5, margin: 0 });
  s.addText("TicketAI", { x: 1.05, y: 2.95, w: 10, h: 1.1, fontFace: HFONT, fontSize: 60, bold: true, color: WHITE, margin: 0 });
  s.addText("Smarter triage. Faster resolution. Fully on-prem.",
    { x: 1.1, y: 4.15, w: 10, h: 0.5, fontFace: HFONT, fontSize: 21, italic: true, color: "E7DCCF", margin: 0 });
  s.addShape(pres.shapes.LINE, { x: 1.12, y: 4.95, w: 4.5, h: 0, line: { color: BROWN_MID, width: 1.5 } });
  s.addText("Hybrid AI · DistilBERT + Qwen 2.5 + embeddings  ·  100% local  ·  $0 cloud cost",
    { x: 1.1, y: 5.15, w: 11, h: 0.4, fontFace: BFONT, fontSize: 14, color: "C9BBAC", margin: 0 });
}

(async () => {
  await slideProblem();
  await slideSolution();
  await slideFlow();
  await slideArch();
  await slideFeatures();
  await slideDepartments();
  await slideStack();
  await slideResults();
  await slideRoadmap();
  slideClosing();
  await pres.writeFile({ fileName: path.join(__dirname, "TicketAI.pptx") });
  console.log("written");
})();
