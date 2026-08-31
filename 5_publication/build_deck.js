/* build_deck.js — Seminar deck (30-45 min, Thai + English technical terms)
   Built to the academic-pptx skill: action titles, one exhibit per slide,
   white ground, navy/mid-blue only, citation on every slide, references,
   conclusions last, labelled appendix.
   Run:  node 5_publication/build_deck.js                                  */

const pptxgen = require("pptxgenjs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const FIG  = (n) => path.join(ROOT, "figures", n);
const EQR  = require(path.join(ROOT, "figures", "eq_ratios.json"));

/* place a LaTeX-rendered equation (see render_equations.py).
   Width is given; height follows the image's true aspect ratio. */
function eq(s, name, x, y, w, align) {
  const h = w / EQR[name];
  const xx = align === "center" ? (10 - w) / 2 : x;
  s.addImage({ path: FIG(name + ".png"), x: xx, y, w, h });
  return y + h;
}

/* size by HEIGHT instead — keeps a column of equations on one baseline */
function eqH(s, name, x, y, h) {
  const w = h * EQR[name];
  s.addImage({ path: FIG(name + ".png"), x, y, w, h });
  return x + w;
}
const OUT  = path.join(__dirname, "SEMINAR_TH.pptx");

const C = {
  bg: "FFFFFF", primary: "1F4E79", accent: "2E75B6", body: "2D2D2D",
  muted: "777777", rule: "CCCCCC", hi: "FFF2CC", hiLine: "E6C800",
  hiText: "7A5200", onDark: "FFFFFF", onDarkMuted: "A0BBDD",
  onDarkSoft: "CADCFC", panel: "EBF3FA",
};
const F = "Tahoma";                 // Thai + Greek + real Bold; ships with Office
const M = 0.5;                      // slide margin

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";        // 10 x 5.625 in
pres.author = "TCR_atomic_bayesian";
pres.title  = "Atomic representation for TCR cross-reactivity";

/* ---------- helpers (fresh option objects every call) ------------------- */

function head(s, title, size, lines) {
  const h = lines === 3 ? 1.16 : 0.82;
  s.addText(title, {
    x: M, y: 0.18, w: 9.0, h,
    fontSize: size || 22, fontFace: F, color: C.primary,
    bold: true, valign: "top", align: "left", margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 0.18 + h + 0.03, w: 9.0, h: 0.02,
    fill: { color: C.rule }, line: { color: C.rule },
  });
  return 0.18 + h + 0.15;
}

function cite(s, t) {
  s.addText(t, {
    x: M, y: 5.18, w: 9.0, h: 0.28,
    fontSize: 11, fontFace: F, color: C.muted, align: "left", margin: 0,
  });
}

function bullets(s, items, o) {
  /* pptxgenjs renders ONE bullet for a run array joined by breakLine, because
     that is a single paragraph with line breaks. To get a bullet per item,
     `bullet` has to be set on the run that STARTS each paragraph -- i.e. the
     first run, and every run following one that ended with breakLine. */
  let startsPara = true;
  const runs = items.map((it, i) => {
    const base = (typeof it === "string")
      ? { text: it, options: { breakLine: i < items.length - 1 } }
      : { text: it.text, options: Object.assign({}, it.options) };
    if (startsPara) base.options.bullet = true;
    startsPara = base.options.breakLine === true;
    return base;
  });
  s.addText(runs, Object.assign({
    fontSize: 18, fontFace: F, color: C.body,
    paraSpaceAfter: 10, valign: "top",
  }, o));
}

function colHead(s, t, x, y, w) {
  s.addText(t, {
    x, y, w, h: 0.32, fontSize: 17, fontFace: F,
    color: C.accent, bold: true, margin: 0,
  });
}

function callout(s, t, o) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, Object.assign({
    fill: { color: C.hi }, line: { color: C.hiLine, pt: 1 }, rectRadius: 0.06,
  }, o));
  s.addText(t, Object.assign({
    fontSize: 15, fontFace: F, color: C.hiText, bold: true,
    align: "center", valign: "middle", margin: 0,
  }, o));
}

function panel(s, t, o, fs) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, Object.assign({
    fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
  }, o));
  s.addText(t, Object.assign({
    fontSize: fs || 16, fontFace: F, color: C.primary,
    align: "left", valign: "middle",
  }, o, { margin: 0.14 }));
}

function table(s, rows, o) {
  s.addTable(rows, Object.assign({
    fontFace: F, fontSize: 13, color: C.body,
    border: { type: "solid", pt: 0.5, color: C.rule },
    align: "left", valign: "middle", autoPage: false,
  }, o));
}
const th = (t) => ({ text: t, options: { bold: true, color: C.primary, fill: { color: "F0F4F8" } } });
const tb = (t) => ({ text: t, options: { bold: true } });

/* wide figure centred, with a takeaway line under it */
function figWide(s, file, ratio, y, w, takeaway) {
  const h = w / ratio;
  s.addImage({ path: FIG(file), x: (10 - w) / 2, y, w, h });
  if (takeaway)
    s.addText(takeaway, {
      x: M, y: y + h + 0.08, w: 9.0, h: 0.5,
      fontSize: 15, fontFace: F, color: C.body, align: "left", margin: 0,
    });
  return y + h;
}

function divider(part, title, sub) {
  const s = pres.addSlide();
  s.background = { color: "1A3A5C" };
  s.addText(part, {
    x: M, y: 1.75, w: 9.0, h: 0.4,
    fontSize: 16, fontFace: F, color: "7BAFD4", margin: 0,
  });
  s.addText(title, {
    x: M, y: 2.15, w: 9.0, h: 1.0,
    fontSize: 32, fontFace: F, color: C.onDark, bold: true, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 3.3, w: 2.5, h: 0.06, fill: { color: C.accent }, line: { color: C.accent },
  });
  if (sub)
    s.addText(sub, {
      x: M, y: 3.55, w: 9.0, h: 0.5,
      fontSize: 15, fontFace: F, color: C.onDarkSoft, margin: 0,
    });
  return s;
}

function appendixLabel(s, t) {
  s.addText(t, {
    x: M, y: 0.13, w: 9.0, h: 0.32,
    fontSize: 13, fontFace: F, color: C.muted, italic: true, margin: 0,
  });
}
function appendixHead(s, title) {
  s.addText(title, {
    x: M, y: 0.5, w: 9.0, h: 0.72,
    fontSize: 20, fontFace: F, color: C.primary, bold: true, valign: "top", margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 1.24, w: 9.0, h: 0.02, fill: { color: C.rule }, line: { color: C.rule },
  });
  return 1.36;
}

/* ====================================================================== */
/* 1 — TITLE                                                              */
/* ====================================================================== */
{
  const s = pres.addSlide();
  s.background = { color: C.primary };
  s.addText("แทน substitution matrix ด้วย atomic representation\nใน Bayesian model ทำนาย TCR cross-reactivity", {
    x: 0.7, y: 1.02, w: 8.6, h: 1.85,
    fontSize: 23, fontFace: F, color: C.onDark, bold: true, align: "left", valign: "top", margin: 0,
  });
  s.addText("380 พารามิเตอร์ » 8 พารามิเตอร์ · และสิ่งที่เราค้นพบตอนเปลี่ยน epitope", {
    x: 0.7, y: 3.02, w: 8.6, h: 0.4,
    fontSize: 16, fontFace: F, color: C.onDarkMuted, align: "left", margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.7, y: 3.5, w: 2.0, h: 0.04, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("ชื่อผู้นำเสนอ · สังกัด · วันที่นำเสนอ", {
    x: 0.7, y: 3.62, w: 8.6, h: 0.3,
    fontSize: 15, fontFace: F, color: C.onDarkSoft, align: "left", margin: 0,
  });
  s.addText("Seminar · 30–45 นาที\nข้อมูล: BATCAVE (Banerjee et al., Cell Systems 2025) + Malone et al., Nat Commun 2025\nโค้ดและผลทั้งหมด: TCR_atomic_bayesian/", {
    x: 0.7, y: 3.98, w: 8.6, h: 1.0,
    fontSize: 13, fontFace: F, color: C.onDarkMuted, align: "left", margin: 0,
  });
  s.addNotes("แก้บรรทัด “ชื่อผู้นำเสนอ · สังกัด · วันที่นำเสนอ” ก่อนนำเสนอจริง — เป็นช่องเดียวในเด็คที่ต้องกรอกเอง. เป้าหมายของ talk นี้มีสองอย่าง: (1) อธิบายให้ชัดว่าทำอะไรลงไปบ้างและทำไมต้องทำแบบนั้น (2) ให้ทุกคนกลับไปทำซ้ำได้เอง ทุกตัวเลขบนสไลด์มาจากไฟล์ผลจริงใน results/ ไม่มีตัวเลขสมมติ");
}

/* ====================================================================== */
/* PART 1 — ปัญหาและคำถามวิจัย                                            */
/* ====================================================================== */
divider("ส่วนที่ 1", "ปัญหาและคำถามวิจัย", "ทำไม cross-reactivity ถึงเป็นทั้งความหวังและความเสี่ยง")
  .addNotes("ส่วนนี้ ~6 นาที ปูให้คนที่ไม่ได้อยู่สาย immunology เข้าใจว่าโจทย์คืออะไร");

{ /* 3 — biology */
  const s = pres.addSlide();
  const y = head(s, "TCR หนึ่งตัวจดจำ peptide ได้หลายแบบ — cross-reactivity จึงเป็นทั้ง\nโอกาสของ neoantigen vaccine และความเสี่ยงของ engineered T cell", 20, 3);
  s.addImage({ path: FIG("fig1_overview.png"), x: M, y: y, w: 4.0, h: 4.0 / 1.11 });
  colHead(s, "โจทย์ที่ต้องทำนาย", 4.75, y, 4.75);
  bullets(s, [
    { text: "T cell มองเห็น peptide 9–10 ตัวอักษร ที่ถูก MHC ยื่นออกมา", options: { breakLine: true } },
    { text: "ถ้า peptide กลายพันธุ์ไป 1 ตำแหน่ง — TCR ยังจำได้ไหม", options: { breakLine: true } },
    { text: "ต้องได้ 3 ระดับ: ไม่กระตุ้น / อ่อน / แรง", options: { breakLine: true } },
    { text: "ทดลองจริงครบทุกตัวแปรไม่ไหว » ต้องมีโมเดล", options: {} },
  ], { x: 4.75, y: y + 0.4, w: 4.75, h: 3.2, fontSize: 17 });
  cite(s, "Fig. 1 (งานนี้) · ข้อมูล: BATCAVE, Banerjee et al., Cell Systems 16:101345 (2025)");
  s.addNotes("ประเด็นที่ต้องย้ำ: การจดจำไม่ใช่ on/off แต่เป็นระดับ และเป็น ordinal (ไม่กระตุ้น < อ่อน < แรง) — เป็นเหตุผลที่โมเดลต้องใช้ ordered logistic ไม่ใช่ binary classifier");
}

{ /* 4 — titin case */
  const s = pres.addSlide();
  const y = head(s, "ทำนายผิดมีราคาชีวิต: affinity-enhanced TCR ต่อ MAGE-A3\nไปจับ titin ในหัวใจ ผู้ป่วยเสียชีวิต 2 ราย", 22);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: M, y: y + 0.05, w: 4.3, h: 1.5,
    fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
  });
  s.addText("EVDPIGHLY\nMAGE-A3 (เป้าหมายที่ตั้งใจ)", {
    x: M, y: y + 0.05, w: 4.3, h: 1.5,
    fontSize: 20, fontFace: F, color: C.primary, bold: true, align: "center", valign: "middle", margin: 0,
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.2, y: y + 0.05, w: 4.3, h: 1.5,
    fill: { color: C.hi }, line: { color: C.hiLine, pt: 1.5 }, rectRadius: 0.08,
  });
  s.addText("ESDPIVAQY\ntitin (กล้ามเนื้อหัวใจ) — ต่างกัน 4 ตำแหน่ง", {
    x: 5.2, y: y + 0.05, w: 4.3, h: 1.5,
    fontSize: 20, fontFace: F, color: C.hiText, bold: true, align: "center", valign: "middle", margin: 0,
  });
  bullets(s, [
    { text: "หน้าที่ของโมเดลคือ “จัดอันดับ” peptide อันตรายให้ขึ้นมาก่อนเข้าคลินิก", options: { breakLine: true } },
    { text: "โมเดลของเราจัดอันดับ titin ไว้ที่ 4 จาก 112 peptide ที่ทดสอบ (titin_case.py)", options: { breakLine: true } },
    { text: "แต่ทำนาย “ระดับ” ต่ำไป — เป็นข้อจำกัดของสมมติฐาน additivity (ดู ส่วนที่ 6)", options: {} },
  ], { x: M, y: y + 1.75, w: 9.0, h: 1.9, fontSize: 17 });
  cite(s, "เคส: Linette et al., Blood 122:863 (2013) · การจัดอันดับ: 5_publication/titin_case.py (งานนี้)");
  s.addNotes("เคสนี้คือเหตุผลที่งานสายนี้ต้องแม่นในการ 'จัดอันดับ' มากกว่าการทำนายค่าสัมบูรณ์ และเป็นเหตุผลที่เราวัดผลด้วย AUC ซึ่งเป็น rank-based metric");
}

{ /* 5 — BATMAN architecture */
  const s = pres.addSlide();
  const y = head(s, "BATMAN ให้คะแนนด้วยระยะทางถ่วงน้ำหนักถึง index peptide —\nและระยะนั้นพึ่ง learned matrix M ขนาด 20×20", 21, 3);
  s.addImage({ path: FIG("fig2_architecture.png"), x: M, y: y, w: 4.3, h: 4.3 / 1.21 });
  colHead(s, "โครงสร้างที่รับมาทั้งหมด", 5.05, y, 4.45);
  bullets(s, [
    { text: "w — น้ำหนักรายตำแหน่ง (แต่ละ TCR มองคนละตำแหน่ง)", options: { breakLine: true } },
    { text: "M — ระยะระหว่างกรดอะมิโนคู่หนึ่ง", options: { breakLine: true } },
    { text: "ordered logistic — แปลงระยะเป็น 3 ระดับ", options: { breakLine: true } },
  ], { x: 5.05, y: y + 0.38, w: 4.45, h: 1.9, fontSize: 16 });
  callout(s, "งานนี้เปลี่ยนแค่กล่องเดียว: M\nที่เหลือรับมาทั้งหมดเพื่อให้เทียบกันได้ตรง ๆ",
    { x: 5.05, y: y + 2.4, w: 4.45, h: 1.0 });
  cite(s, "Fig. 2 (งานนี้) · สถาปัตยกรรมจาก Banerjee et al., Cell Systems 16:101345 (2025)");
  s.addNotes("จุดที่ต้องพูดให้ชัด: เราไม่ได้สร้างโมเดลใหม่ทั้งตัว เราทำ controlled substitution — เปลี่ยนเฉพาะ M แล้วให้ทุกอย่างอื่นเหมือนเดิม เพื่อให้ผลที่ต่างกันตีความได้ว่ามาจาก M จริง ๆ");
}

{ /* 6 — research question */
  const s = pres.addSlide();
  const y = head(s, "คำถามวิจัย", 24);
  panel(s, "ถ้าแทน learned matrix M (~380 พารามิเตอร์) ด้วยระยะทางบน\natomic descriptors 8 ตัวที่คำนวณจากโครงสร้างโมเลกุลของ side chain\nจะเสียความแม่นยำเท่าไร และได้ generalisation กลับมาหรือไม่",
    { x: 1.0, y: y + 0.15, w: 8.0, h: 1.55 }, 18);
  table(s, [
    [th("ประเด็น"), th("learned M"), th("atomic")],
    ["จำนวนพารามิเตอร์อิสระ", "~380", tb("8")],
    ["substitution ที่ไม่เคยเห็น", "ตกกลับไปใช้ prior", tb("interpolate ได้")],
    ["กรดอะมิโนนอก 20 ตัวมาตรฐาน (PTM)", "นิยามไม่ได้", tb("คำนวณจาก SMILES ได้")],
  ], { x: M, y: y + 1.95, w: 9.0, colW: [3.4, 2.8, 2.8], rowH: 0.36, fontSize: 14 });
  cite(s, "จำนวนพารามิเตอร์: PROTOCOL.md §3.2 · เปรียบเทียบเชิงคุณสมบัติ, งานนี้");
  s.addNotes("สามแถวนี้คือเหตุผลทั้งหมดที่ทำให้ควรลอง atomic ไม่ใช่แค่ 'พารามิเตอร์น้อยกว่า' แต่คือความสามารถเชิงโครงสร้างที่ matrix ไม่มี — สังเกตว่าเรายังไม่ได้อ้างว่ามันแม่นกว่า");
}

/* ====================================================================== */
/* PART 2 — โมเดลและเหตุผลการออกแบบ                                        */
/* ====================================================================== */
divider("ส่วนที่ 2", "โมเดล และเหตุผลของทุกการตัดสินใจ", "ทำไมต้องเป็น Manhattan · ทำไม θ ต้อง ≥ 0 · ทำไมต้อง freeze")
  .addNotes("ส่วนนี้ ~9 นาที เป็นหัวใจของคำถาม 'ทำไมต้องทำแบบนี้'");

{ /* 8 — the equation */
  const s = pres.addSlide();
  const y = head(s, "โมเดลทั้งตัวคือสองบรรทัด: ระยะทางถ่วงน้ำหนัก แล้วส่งเข้า ordered logistic", 21);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: M, y: y + 0.02, w: 9.0, h: 1.72,
    fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
  });
  eq(s, "eq_core_1", 0, y + 0.14, 3.9, "center");
  eq(s, "eq_core_2", 0, y + 1.22, 6.5, "center");
  colHead(s, "อ่านอย่างไร", M, y + 1.90, 9.0);
  bullets(s, [
    { text: "M บอกว่า “เปลี่ยนกรดอะมิโนคู่นี้ แรงแค่ไหน”", options: { breakLine: true } },
    { text: "w บอกว่า “TCR ตัวนี้สนใจตำแหน่งนั้นไหม” — เรียนแยกรายตัว", options: { breakLine: true } },
    { text: "η ลดลงเมื่อระยะมากขึ้น จึงลดโอกาสกระตุ้น", options: { breakLine: true } },
    { text: "c_1 < c_2 บังคับให้ลำดับ ไม่กระตุ้น < อ่อน < แรง ถูกเสมอ", options: {} },
  ], { x: M, y: y + 2.26, w: 9.0, h: 1.8, fontSize: 16 });
  cite(s, "PROTOCOL.md §3.1 · โครงสร้าง likelihood รับมาจาก Banerjee et al. (2025)");
  s.addNotes("ordered logistic ไม่ใช่การเลือกเชิงเทคนิคเฉย ๆ — มันบังคับ monotonicity ให้ถูกโดยโครงสร้าง ถ้าใช้ multinomial ธรรมดา โมเดลสามารถทำนาย 'ไม่กระตุ้น' และ 'แรง' สูงพร้อมกันโดยข้าม 'อ่อน' ซึ่งขัดกับชีววิทยา");
}

{ /* 8b — what M and w actually look like */
  const s = pres.addSlide();
  const y = head(s, "สองตารางนั้นหน้าตาจริงเป็นแบบนี้ — ค่าจากโมเดลที่ fit แล้ว", 22);

  s.addText("M — ระยะระหว่างกรดอะมิโน (ตัดมา 10 ตัวจาก 20×20)", {
    x: M, y, w: 5.3, h: 0.28, fontSize: 13, fontFace: F, color: C.accent, bold: true, margin: 0 });
  const aa = ["G","A","V","I","L","S","D","K","R","W"];
  const Mrows = [
    [0.0,1.2,5.9,9.5,9.5,8.8,20.7,24.2,31.7,23.9],
    [1.2,0.0,4.8,8.4,8.4,7.7,19.6,23.0,30.6,22.8],
    [5.9,4.8,0.0,3.6,3.6,5.2,14.8,18.3,25.8,18.0],
    [9.5,8.4,3.6,0.0,0.0,8.8,11.2,14.7,22.2,14.4],
    [9.5,8.4,3.6,0.0,0.0,8.8,11.2,14.7,22.2,14.4],
    [8.8,7.7,5.2,8.8,8.8,0.0,11.9,15.4,22.9,18.0],
    [20.7,19.6,14.8,11.2,11.2,11.9,0.0,17.8,20.2,20.4],
    [24.2,23.0,18.3,14.7,14.7,15.4,17.8,0.0,7.5,21.6],
    [31.7,30.6,25.8,22.2,22.2,22.9,20.2,7.5,0.0,24.4],
    [23.9,22.8,18.0,14.4,14.4,18.0,20.4,21.6,24.4,0.0],
  ];
  table(s, [[th("")].concat(aa.map(th))].concat(
    Mrows.map((r, i) => [th(aa[i])].concat(r.map(v => ({
      text: v.toFixed(1),
      options: (i === 3 && (v === 0.0) && true) ? {} : {},
    })))) ),
    { x: M, y: y + 0.32, w: 5.3, colW: [0.44].concat(aa.map(() => 0.486)),
      rowH: 0.228, fontSize: 8, align: "center", margin: 0.02 });
  s.addText("I กับ L ได้ 0.0 — descriptor แยกไม่ออก · ไกลสุด G–R = 31.7 · ใกล้สุด A–G = 1.2", {
    x: M, y: y + 2.92, w: 5.3, h: 0.42, fontSize: 10, fontFace: F, color: C.muted, margin: 0,
  });

  s.addText("w — TCR สนใจตำแหน่งไหน (6 จาก 62)", {
    x: 6.0, y, w: 3.5, h: 0.28, fontSize: 12, fontFace: F, color: C.accent, bold: true, margin: 0 });
  const wrows = [
    ["a3a",   [0.44,0.25,0.40,0.42,0.63,0.01,0.02,0.01,0.10]],
    ["11A10", [0.00,0.42,0.21,0.40,0.54,0.69,0.35,0.10,0.51]],
    ["13A10", [0.08,0.80,0.09,0.75,0.79,0.78,0.45,0.19,0.46]],
    ["14A4",  [0.02,0.65,0.12,0.37,0.67,0.75,0.23,0.33,0.42]],
    ["14D7",  [0.21,0.80,0.24,0.76,0.77,0.76,0.49,0.39,0.67]],
    ["16A11", [0.19,0.81,0.26,0.75,0.78,0.77,0.53,0.39,0.65]],
  ];
  table(s, [[th("TCR")].concat([1,2,3,4,5,6,7,8,9].map(n => th(String(n))))].concat(
    wrows.map(([n, r]) => [th(n)].concat(r.map(v => v.toFixed(2))))),
    { x: 6.0, y: y + 0.32, w: 3.5, colW: [0.62].concat([1,2,3,4,5,6,7,8,9].map(() => 0.32)),
      rowH: 0.29, fontSize: 8, align: "center", margin: 0.02 });
  s.addText("แต่ละแถวคือ TCR หนึ่งตัว · a3a แทบไม่มองตำแหน่ง 6–8 (0.01–0.02) ส่วน 16A11 มองเกือบทุกตำแหน่ง", {
    x: 6.0, y: y + 2.40, w: 3.5, h: 0.62, fontSize: 10, fontFace: F, color: C.muted, margin: 0,
  });

  callout(s, "M มีตารางเดียวใช้ร่วมกันทุก TCR · w มีคนละชุดต่อ TCR — นี่คือเหตุผลที่ TCR สองตัวให้คำตอบต่างกันได้ทั้งที่ M เหมือนกัน",
    { x: M, y: 4.55, w: 9.0, h: 0.52 });
  cite(s, "results/derivation/M_atomic.csv (20×20 เต็ม) · results/derivation/w_per_tcr.csv (62×9 เต็ม) · DERIVATION.md §4");
  s.addNotes("ตรงนี้ให้เวลาผู้ฟังดูตัวเลขจริงสักครู่ ประเด็นที่ต้องชี้: M สมมาตรและมีแนวทแยงเป็นศูนย์ · ช่อง I–L เป็นศูนย์ซึ่งเป็นข้อจำกัดที่เราจะพูดถึงอีกครั้งตอนท้าย · ตาราง w แถวหนึ่งคือ TCR หนึ่งตัว ไม่ใช่ค่าเฉลี่ย");
}

{ /* 8c — how each table is obtained, and why that way */
  const s = pres.addSlide();
  const y = head(s, "สองตารางนี้หามายังไง — และทำไมต้องหาแบบนี้", 22);

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: M, y: y, w: 4.35, h: 3.32,
    fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
  });
  s.addText("M  (20×20 · ใช้ร่วมกันทุก TCR)", {
    x: M + 0.16, y: y + 0.12, w: 4.05, h: 0.3,
    fontSize: 15, fontFace: F, color: C.primary, bold: true, margin: 0,
  });
  bullets(s, [
    { text: "หามายังไง: ", options: { bold: true, breakLine: false } },
    { text: "φ คำนวณจาก SMILES (คงที่ ไม่เรียน) แล้วคูณด้วย θ 8 ตัวที่เรียนจากข้อมูล", options: { breakLine: true } },
    { text: "ทำไมแบบนี้: ", options: { bold: true, breakLine: false } },
    { text: "θ ≥ 0 บวกกับรูป |·| ทำให้ M ≥ 0 · แนวทแยง 0 · สมมาตร · triangle inequality มาฟรี", options: { breakLine: true } },
    { text: "ทำไมไม่เรียนทั้งตาราง: ", options: { bold: true, breakLine: false } },
    { text: "380 ช่องอิสระจะจำ corpus ที่เทรน และให้คะแนน substitution ที่ไม่เคยเห็นไม่ได้", options: {} },
  ], { x: M + 0.16, y: y + 0.46, w: 4.05, h: 2.7, fontSize: 12.5 });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.15, y: y, w: 4.35, h: 3.32,
    fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
  });
  s.addText("w  (62×9 · คนละชุดต่อ TCR)", {
    x: 5.31, y: y + 0.12, w: 4.05, h: 0.3,
    fontSize: 15, fontFace: F, color: C.primary, bold: true, margin: 0,
  });
  bullets(s, [
    { text: "หามายังไง: ", options: { bold: true, breakLine: false } },
    { text: "ไม่มีสูตร — อนุมานจาก mutant ของ TCR ตัวนั้นเองด้วย ADVI 12,000 รอบ", options: { breakLine: true } },
    { text: "ทำไมรายตัว: ", options: { bold: true, breakLine: false } },
    { text: "TCR แต่ละตัวสัมผัส peptide คนละตำแหน่ง ค่าเฉลี่ยกลุ่มจึงใช้แทนกันไม่ได้", options: { breakLine: true } },
    { text: "ทำไมต้อง Beta(α,β): ", options: { bold: true, breakLine: false } },
    { text: "ข้อมูลตรึงได้แค่ผลคูณ w·M — คูณ θ สองเท่าแล้วหาร w สองเท่าได้ค่าเดิม prior จึงเป็นตัวตรึง", options: {} },
  ], { x: 5.31, y: y + 0.46, w: 4.05, h: 2.7, fontSize: 12.5 });

  callout(s, "φ มาจากเคมี · θ กับ w มาจากข้อมูล — มีแค่ 8 + 558 ตัวเลขเท่านั้นที่โมเดลนี้เรียนจริง ๆ",
    { x: M, y: y + 3.46, w: 9.0, h: 0.5 });
  cite(s, "PROTOCOL.md §3.2–3.4 · batman_atomic.py build_model() · DERIVATION.md §2");
  s.addNotes("สไลด์นี้คือคำตอบของ 'ทำไมต้องทำแบบนี้' สำหรับสองตารางหลัก ประเด็นที่คนมักถามคือทำไมไม่เรียน M ทั้งตาราง คำตอบอยู่บรรทัดสุดท้ายของกล่องซ้าย และเป็นสิ่งที่ผลในส่วนที่ 5 ยืนยันด้วยข้อมูลจริง");
}

{ /* 9 — worked example (the key intuition slide) */
  const s = pres.addSlide();
  const y = head(s, "เปลี่ยนตัวอักษรเดียวแล้วระยะขยับเท่าไร — เดินตัวเลขจริงจาก TCR a3a", 21);
  table(s, [
    [th("การเปลี่ยน"), th("M (ระยะเคมี)"), th("w ของตำแหน่ง"), th("ระยะรวม d"), th("ทำนาย"), th("วัดจริง")],
    ["ตำแหน่ง 5 : I » R", "22.21", "0.625", tb("13.884"), "ไม่กระตุ้น 100%", "ไม่กระตุ้น"],
    ["ตำแหน่ง 6 : G » W", tb("23.92"), tb("0.010"), tb("0.231"), "แรง 53.5%", "อ่อน"],
  ], { x: M, y: y + 0.1, w: 9.0, colW: [2.0, 1.5, 1.5, 1.4, 1.6, 1.0], rowH: 0.42, fontSize: 14 });
  callout(s, "G » W เปลี่ยนเคมี แรงกว่า I » R  (23.92 > 22.21)  แต่ระยะรวม น้อยกว่า 60 เท่า  (0.231 vs 13.884)",
    { x: M, y: y + 1.55, w: 9.0, h: 0.62 });
  bullets(s, [
    { text: "คำถามที่ถูกไม่ใช่ “เปลี่ยนแรงแค่ไหน” แต่คือ “เปลี่ยนแรงแค่ไหน × ตำแหน่งนั้น TCR สนใจไหม”", options: { breakLine: true } },
    { text: "ตำแหน่ง 5 ของ a3a มี w = 0.625 · ตำแหน่ง 6 มี w = 0.010 » แทบมองไม่เห็น", options: { breakLine: true } },
    { text: "นี่คือเหตุผลที่ M เพียงอย่างเดียวไม่พอ และทำไม backbone ถึงสำคัญกว่าที่คิด", options: {} },
  ], { x: M, y: y + 2.22, w: 9.0, h: 1.8, fontSize: 16 });
  cite(s, "ค่าจากโมเดลที่ fit จริง (ไม่ใช่ตัวอย่างสมมติ) · START_HERE.md §3.2b · epitope EVDPIGHLY");
  s.addNotes("สไลด์นี้สำคัญที่สุดสำหรับคนที่เพิ่งเข้าสาย ให้เวลา 2 นาที เดินให้ครบทั้งสองแถว จุดที่คนมักเข้าใจผิดคือคิดว่า matrix คือทุกอย่าง แต่จริง ๆ w ครอบงำผลลัพธ์");
}

{ /* 10 — atomic representation */
  const s = pres.addSlide();
  const y = head(s, "atomic descriptors 8 ตัวคำนวณจาก SMILES ของ side chain —\nไม่ได้เรียนจากข้อมูล TCR แม้แต่ตัวเดียว", 21, 3);
  s.addImage({ path: FIG("fig3_representation.png"), x: M, y: y, w: 5.0, h: 5.0 / 1.42 });
  colHead(s, "ขั้นตอนการสร้าง", 5.7, y, 3.8);
  bullets(s, [
    { text: "SMILES » RDKit » descriptor 8 ตัว", options: { breakLine: true } },
    { text: "ลบ glycine แล้ว z-score (รายละเอียดสไลด์ถัดไป)", options: { breakLine: true } },
    { text: "ประกอบเป็นระยะด้วยสมการเดียว:", options: {} },
  ], { x: 5.7, y: y + 0.38, w: 3.8, h: 1.45, fontSize: 14 });
  eq(s, "eq_atomic", 5.7, y + 1.92, 3.7);
  callout(s, "θ ที่เรียนได้จัดอันดับแกนเคมีเอง:\nrotB · bulk · polar · charge เด่นที่สุด",
    { x: 5.7, y: y + 2.72, w: 3.8, h: 0.72 });
  cite(s, "Fig. 3 (งานนี้) · descriptors: RDKit · เทียบกับ Atchley et al., PNAS 102:6395 (2005)");
  s.addNotes("ย้ำว่า descriptor ทั้งหมดคำนวณจากโครงสร้างโมเลกุลล้วน ๆ ก่อนเห็นข้อมูล — นี่คือเหตุผลที่มันขยายไปยัง PTM ได้ในหลักการ และเป็นเหตุผลที่ r กับ BLOSUM100 มีแค่ 0.39 คือมันไม่ได้ไปสร้าง BLOSUM ขึ้นมาใหม่");
}

{ /* 10b — how phi is built */
  const s = pres.addSlide();
  const y = head(s, "φ สร้างจาก SMILES 3 ขั้น — ไม่แตะข้อมูล TCR แม้แต่แถวเดียว", 22);
  s.addImage({ path: FIG("fig14_phi_construction.png"), x: 1.8, y: y - 0.02, w: 6.4, h: 6.4 / 1.672 });
  cite(s, "Fig. 14 (งานนี้) · results/derivation/phi_1..3.csv · descriptors: RDKit · DERIVATION.md §1");
  s.addNotes("ขั้น 1 นับ 8 อย่างด้วย RDKit · ขั้น 2 ลบ glycine ซึ่งเป็น backbone เปล่า เหลือเฉพาะสิ่งที่ side chain เพิ่ม · ขั้น 3 z-score ไม่งั้น heavy กินช่วง 10 หน่วยแต่ charge กินแค่ 2 แล้ว θ จะถูกบังคับให้ไปแก้หน่วยแทนที่จะบอกความสำคัญ. กรอบสีส้มคือ I กับ L ที่เหมือนกันทุกช่องทุกขั้น ซึ่งเป็นที่มาของ M[I,L] = 0");
}

{ /* 10c — final fitted theta and the M it assembles */
  const s = pres.addSlide();
  const y = head(s, "ค่าที่เทรนได้จริง: θ ทั้ง 8 ตัว และ M ขนาด 20×20 ที่ประกอบขึ้นจากมัน", 21);
  s.addImage({ path: FIG("fig15_theta_and_M.png"), x: M, y: y + 0.05, w: 6.2, h: 6.2 / 1.92 });
  colHead(s, "อ่านตรงไหน", 6.9, y + 0.05, 2.6);
  bullets(s, [
    { text: "rotB 2.87 · heavy 2.82 · polar 2.46 · charge 2.11 เด่นที่สุด", options: { breakLine: true } },
    { text: "HBD 0.038 ± 0.043 แยกจากศูนย์ไม่ได้", options: { breakLine: true } },
    { text: "S แยกได้ (2.7σ) แต่เล็กกว่า rotB 34 เท่า", options: { breakLine: true } },
    { text: "M ได้ metric axioms ครบ ตรวจ 8,000 สามเหลี่ยม", options: {} },
  ], { x: 6.9, y: y + 0.42, w: 2.6, h: 3.0, fontSize: 12 });
  callout(s, "r กับ BLOSUM100 = 0.394 — ไม่ได้ไปสร้าง BLOSUM ขึ้นใหม่ทางอ้อม",
    { x: M, y: y + 3.4, w: 6.2, h: 0.5 });
  cite(s, "Fig. 15 (งานนี้) · results/derivation/theta.csv, M_atomic.csv · DERIVATION.md §4");
  s.addNotes("นี่คือคำตอบของ 'สุดท้ายได้ค่าเท่าไร' สำหรับ M — θ ทั้ง 8 ตัวพร้อม sd และเมทริกซ์ 20×20 เต็มอยู่ใน results/derivation/M_atomic.csv. จุดที่ควรพูด: HBD เป็นตัวเดียวที่แยกจากศูนย์ไม่ได้ ส่วน S แยกได้ (2.7σ) แต่เล็กกว่า rotB 34 เท่า จึงแทบไม่มีผลจริง");
}

{ /* 10d — final fitted w */
  const s = pres.addSlide();
  const y = head(s, "ค่าที่เทรนได้จริง: w ครบ 62 TCR × 9 ตำแหน่ง —\nและ TCR แต่ละตัวมี profile ของตัวเองจริง", 21);
  s.addImage({ path: FIG("fig16_w_profiles.png"), x: M, y: y + 0.05, w: 6.2, h: 6.2 / 2.00 });
  colHead(s, "อ่านตรงไหน", 6.9, y + 0.05, 2.6);
  bullets(s, [
    { text: "ตำแหน่ง 5 ถูกใช้มากสุดโดยเฉลี่ย (0.452)", options: { breakLine: true } },
    { text: "แต่ sd ข้าม TCR = 0.236 ใหญ่กว่าครึ่งของค่าเฉลี่ย", options: { breakLine: true } },
    { text: "a3a ปิดตำแหน่ง 6–8 เกือบสนิท", options: { breakLine: true } },
    { text: "16A11 เปิดกว้างเกือบทุกตำแหน่ง", options: {} },
  ], { x: 6.9, y: y + 0.42, w: 2.6, h: 3.0, fontSize: 12 });
  callout(s, "ค่าเฉลี่ยของกลุ่มบอกอะไรไม่ได้เลยเกี่ยวกับ TCR ตัวใดตัวหนึ่ง",
    { x: M, y: y + 3.3, w: 6.2, h: 0.5 });
  cite(s, "Fig. 16 (งานนี้) · results/derivation/w_per_tcr.csv · DERIVATION.md §4");
  s.addNotes("จุดสำคัญคือ panel b: ถ้า w ลู่เข้าหาค่ากลางร่วมกัน violin จะแคบ แต่มันกว้างมาก แปลว่า partial pooling ไม่ได้กลืน TCR แต่ละตัวหายไป. panel c เทียบสองตัวที่ใช้กลยุทธ์ต่างกันชัดเจน");
}

{ /* 10e — the fitted values, end to end on one measured row */
  const s = pres.addSlide();
  const y = head(s, "เอาค่าที่เทรนได้มาเดินจริงหนึ่งแถว — TCR 16A11 · ตำแหน่ง 2: P » R", 21);
  let yy = y + 0.02;
  const rows = [
    ["eq_step1", "θ เทรนได้ · φ จาก SMILES"],
    ["eq_step2", "w เทรนได้"],
    ["eq_step3", "d_0 เทรนได้"],
    ["eq_step4", "cutpoints เทรนได้"],
  ];
  rows.forEach(([nm, src], i) => {
    s.addText(String(i + 1), {
      x: M, y: yy + 0.02, w: 0.3, h: 0.3, fontSize: 15, fontFace: F,
      color: C.accent, bold: true, margin: 0,
    });
    eqH(s, nm, 0.92, yy, 0.30);
    const b = yy + 0.30;
    s.addText(src, {
      x: 6.75, y: yy + 0.01, w: 2.75, h: 0.3,
      fontSize: 12, fontFace: F, color: C.muted, margin: 0,
    });
    yy = b + 0.50;
  });
  callout(s, "ทำนาย: ไม่กระตุ้น 100%  ·  วัดจริง: ไม่กระตุ้น  ·  ตรงกัน",
    { x: M, y: 4.50, w: 9.0, h: 0.5 });
  cite(s, "รันซ้ำเองได้: python3 5_publication/derive_M_and_w.py (~40 วินาที) · DERIVATION.md §5");
  s.addNotes("สไลด์นี้ปิดวงจรของส่วนที่ 2 คือเอา θ, w, d_0, cutpoints ที่เพิ่งแสดงไป มาเดินจริงกับแถวข้อมูลหนึ่งแถวจนได้ความน่าจะเป็น คอลัมน์ขวาบอกว่าค่าแต่ละตัวมาจากการเทรนหรือมาจากเคมี");
}

{ /* 11 — model table + why HalfNormal */
  const s = pres.addSlide();
  const y = head(s, "ห้าโมเดลใช้โครงเดียวกันทุกอย่าง ต่างกันแค่วิธีประกอบ M", 22);
  const models = [
    ["fixed",          "eq_m_fixed",   "0"],
    ["learned",        "eq_m_learned", "~380"],
    ["atomic",         "eq_m_atomic",  "8"],
    ["hybrid_frozen",  "eq_m_frozen",  "8 ตรึง + 400 บีบ"],
    ["hybrid_feature", "eq_m_feature", "8 ตรึง + 36 บีบ"],
  ];
  s.addText("kind", { x: M, y: y, w: 1.9, h: 0.26, fontSize: 13, fontFace: F, color: C.accent, bold: true, margin: 0 });
  s.addText("M ประกอบอย่างไร", { x: 2.5, y: y, w: 4.4, h: 0.26, fontSize: 13, fontFace: F, color: C.accent, bold: true, margin: 0 });
  s.addText("พารามิเตอร์อิสระ", { x: 7.2, y: y, w: 2.3, h: 0.26, fontSize: 13, fontFace: F, color: C.accent, bold: true, margin: 0 });
  models.forEach(([kind, nm, np], i) => {
    const ry = y + 0.32 + i * 0.50;
    s.addText(kind, { x: M, y: ry + 0.02, w: 1.9, h: 0.3, fontSize: 13, fontFace: F, color: C.body, margin: 0 });
    eqH(s, nm, 2.5, ry, 0.34);
    s.addText(np, { x: 7.2, y: ry + 0.02, w: 2.3, h: 0.3, fontSize: 13, fontFace: F,
                    color: C.body, bold: i >= 2, margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: M, y: ry + 0.42, w: 9.0, h: 0.008,
                                        fill: { color: C.rule }, line: { color: C.rule } });
  });
  callout(s, "ทำไม θ ต้องเป็น HalfNormal (บังคับ θ ≥ 0):  ได้ M ≥ 0 · M[a,a] = 0 · สมมาตร · triangle inequality มาฟรีทั้งหมด\nสำหรับ learned matrix คุณสมบัติเหล่านี้ต้องบังคับเอาเอง และไม่มีอะไรรับประกัน",
    { x: M, y: y + 2.92, w: 9.0, h: 0.88 });
  cite(s, "PROTOCOL.md §3.2–3.3 · โค้ด: batman_atomic.py build_model()");
  s.addNotes("ประเด็น 'ทำไมต้องทำแบบนี้' ที่คมที่สุดอยู่ในกล่องเหลือง: การเลือก Manhattan + non-negative weight ทำให้ metric axioms เป็นผลของโครงสร้าง ไม่ใช่ข้อบังคับที่ต้องไปตรวจทีหลัง");
}

/* ====================================================================== */
/* PART 3 — โปรโตคอล                                                       */
/* ====================================================================== */
divider("ส่วนที่ 3", "โปรโตคอลการเทรนและการวัดผล", "ทุกค่าถูกกำหนดล่วงหน้า · ทำซ้ำได้ทุกตัวเลข")
  .addNotes("ส่วนนี้ ~8 นาที คือส่วนที่ทำให้คนอื่นทำซ้ำได้ ถ้าเวลาไม่พอให้ข้ามสไลด์สถิติ แต่ห้ามข้าม per-TCR AUC");

{ /* 13 — all fitting settings */
  const s = pres.addSlide();
  const y = head(s, "ทุกค่าที่ต้องตั้งถูกกำหนดล่วงหน้าและเขียนไว้ครบ — ไม่มีการปรับตามผล", 21);
  colHead(s, "Prior (เหมือนกันทุกโมเดล)", M, y, 4.3);
  table(s, [
    [th("พารามิเตอร์"), th("prior")],
    ["alpha, beta", "Gamma(2, 2)"],
    ["w", "Beta(alpha, beta)"],
    ["d0", "Normal(0, 2)"],
    ["cut", "Normal(0,2), ordered"],
  ], { x: M, y: y + 0.36, w: 4.3, colW: [1.5, 2.8], rowH: 0.34, fontSize: 12 });
  colHead(s, "Hyperparameter ของ ADVI", 5.2, y, 4.3);
  table(s, [
    [th("ชื่อ"), th("ค่า")],
    ["n_iter", "12,000"],
    ["lr (Adam)", "0.05 » 0.01 » 0.002 (ladder)"],
    ["draws", "300"],
    ["shrinkage σ", "0.25"],
    ["seed", "ตามหมายเลข fold"],
  ], { x: 5.2, y: y + 0.36, w: 4.3, colW: [1.5, 2.8], rowH: 0.29, fontSize: 12 });
  callout(s, "hybrid ต้องเทรน 2 ขั้นเสมอ:  ขั้นที่ 1 fit atomic » ได้ θ และ w  »  ขั้นที่ 2 ตรึง θ, w ไว้ แล้วเรียนเฉพาะ residual\nถ้า fit พร้อมกันในขั้นเดียว ผล out-of-distribution เสียทุกค่า σ (ส่วนที่ 4)",
    { x: M, y: y + 2.4, w: 9.0, h: 0.9 });
  cite(s, "PROTOCOL.md §3.2, §3.4, §4.2 · โค้ด: batman_atomic.py, 1_core_model/hybrid_full.py");
  s.addNotes("ถ้ามีคนถามว่า tune prior ไหม คำตอบคือไม่ — prior ทั้งหมดรับมาจาก BATMAN และ theta เป็น HalfNormal(1) ตั้งแต่แรก เราไม่ได้ค้นหา hyperparameter บนผลลัพธ์");
}

{ /* 14 — ADVI vs NUTS */
  const s = pres.addSlide();
  const y = head(s, "ใช้ ADVI เพราะเร็วกว่า NUTS มาก และค่ากลางตรงกัน r = 0.997 —\nแต่ interval แคบไป 43% เราจึงไม่รายงาน interval จาก ADVI", 21);
  figWide(s, "fig7_advi_nuts.png", 2.25, y, 6.6,
    "ตรวจด้วย NUTS 4 chains × 1,500 draws: max r-hat = 1.0069 · min ESS = 649 » chain converge จริง");
  cite(s, "Fig. 7 (งานนี้) · ADVI: Kucukelbir et al., JMLR 18(14) (2017) · ผล: results/exp6_nuts_vs_advi.csv");
  s.addNotes("นี่คือตัวอย่างของการตัดสินใจที่ต้องอธิบายเหตุผล: เราเลือกวิธีที่เร็วกว่าเพราะต้อง fit หลายพันครั้ง แต่เราไปตรวจว่ามันเชื่อได้แค่ไหน แล้วจำกัดการอ้างของตัวเองให้อยู่ในขอบเขตที่ตรวจแล้ว — point estimate ใช้ได้ interval ใช้ไม่ได้");
}

{ /* 15 — per-TCR vs pooled */
  const s = pres.addSlide();
  const y = head(s, "ต้องวัดด้วย per-TCR AUC ไม่ใช่ pooled — pooled ให้ 0.31–0.39\nซึ่งแย่กว่าการเดาสุ่ม ทั้งที่โมเดลทำงานได้ดี", 21);
  s.addChart(pres.charts.BAR, [{
    name: "AUC",
    labels: ["pooled (ผิด)", "per-TCR (ถูก)"],
    values: [0.35, 0.847],
  }], {
    x: M, y: y + 0.05, w: 5.0, h: 3.5,
    barDir: "col", chartColors: [C.accent],
    chartArea: { fill: { color: C.bg } },
    catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
    catAxisLabelFontFace: F, valAxisLabelFontFace: F,
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.body,
    dataLabelFontFace: F, dataLabelFontSize: 13, dataLabelFormatCode: "0.00",
    showLegend: false, valAxisMaxVal: 1.0, valAxisMinVal: 0,
  });
  colHead(s, "ทำไมถึงกลับด้าน", 5.9, y, 3.6);
  bullets(s, [
    { text: "EWW-TCR: 89% ไม่กระตุ้น", options: { breakLine: true } },
    { text: "TCR-1E6: 87% กระตุ้น", options: { breakLine: true } },
    { text: "base rate ตรงข้ามกัน พอ pool รวม อันดับพลิกทั้งชุด", options: { breakLine: true } },
    { text: "หน่วยวิเคราะห์จึงต้องเป็น “หนึ่ง TCR” เสมอ", options: {} },
  ], { x: 5.9, y: y + 0.38, w: 3.6, h: 3.0, fontSize: 16 });
  cite(s, "MANUSCRIPT §2.6 (งานนี้) · เกณฑ์วินิจฉัยอยู่ใน PROTOCOL.md §4.4");
  s.addNotes("นี่คือกับดักที่คนทำซ้ำจะเจอแน่ ถ้าใครได้ AUC ต่ำกว่า 0.5 แปลว่าเผลอ pool TCR รวมกัน ไม่ใช่โมเดลพัง — เราเขียนไว้ใน PROTOCOL.md ตารางวินิจฉัยแล้ว");
}

{ /* 16 — four generalisation axes */
  const s = pres.addSlide();
  const y = head(s, "generalisation ถูกทดสอบ 4 แกน ไม่ใช่แกนเดียว — และคำตอบต่างกันตามแกน", 21);
  const boxes = [
    ["1 · in-distribution", "5-fold CV บน TCR ทั้งหมด", "เห็นทั้ง epitope และ TCR ตอนเทรน"],
    ["2 · leave-chemistry-out", "ตัด substitution ที่ไป\nยังกลุ่มเคมีหนึ่งออกทั้งหมด", "matrix ต้องถอยไปใช้ prior"],
    ["3 · leave-one-epitope-out", "ตัด epitope และ TCR ของมัน\nออกทั้งชุด (23 epitope)", "แกนที่งานเดิมไม่เคยวัด"],
    ["4 · external dataset", "Malone 2025 — TCR ใหม่\nepitope ใหม่ assay คนละแบบ", "ไม่ได้ train บนข้อมูลนี้เลย"],
  ];
  boxes.forEach((b, i) => {
    const x = M + (i % 2) * 4.65;
    const yy = y + 0.05 + Math.floor(i / 2) * 1.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: yy, w: 4.35, h: 1.65,
      fill: { color: i >= 2 ? C.hi : C.panel },
      line: { color: i >= 2 ? C.hiLine : C.accent, pt: 1 }, rectRadius: 0.06,
    });
    s.addText(b[0], {
      x: x + 0.15, y: yy + 0.1, w: 4.05, h: 0.3,
      fontSize: 15, fontFace: F, bold: true,
      color: i >= 2 ? C.hiText : C.primary, margin: 0,
    });
    s.addText(b[1], {
      x: x + 0.15, y: yy + 0.42, w: 4.05, h: 0.66,
      fontSize: 13, fontFace: F, color: C.body, margin: 0,
    });
    s.addText(b[2], {
      x: x + 0.15, y: yy + 1.14, w: 4.05, h: 0.4,
      fontSize: 12, fontFace: F, color: C.muted, italic: true, margin: 0,
    });
  });
  cite(s, "แกน 1–2: MANUSCRIPT §2.6 · แกน 3: §2.9 · แกน 4: §2.8 (งานนี้) · สถิติ: paired Wilcoxon + bootstrap 10,000");
  s.addNotes("กล่องสีเหลืองสองอันคือสิ่งที่งานนี้เพิ่มเข้าไปในสาขา งานเดิมวัดแค่แกน 1 กับ 2 และข้อสรุปที่ได้จากสองแกนแรกจะกลับด้านเมื่อไปแกน 3 และ 4 ซึ่งเป็นเนื้อหาส่วนที่ 5");
}

/* ====================================================================== */
/* PART 4 — ผล in-distribution                                             */
/* ====================================================================== */
divider("ส่วนที่ 4", "ผลลัพธ์ in-distribution", "151 TCR · 22,827 mutant ที่วัดจริง")
  .addNotes("ส่วนนี้ ~8 นาที เป็นผลที่ 'เข้าข้างเรา' — แต่ต้องบอกขอบเขตให้ชัดว่าอยู่ใน epitope ชุดเดิม");

{ /* 18 — backbone does the work */
  const s = pres.addSlide();
  const y = head(s, "ความแม่นส่วนใหญ่มาจาก backbone ไม่ใช่จาก M —\nงานนี้ทั้งหมดเล่นอยู่ในช่องว่างที่เหลือ", 22);
  s.addChart(pres.charts.BAR, [{
    name: "mean per-TCR AUC",
    labels: ["Hamming", "BLOSUM100\n(w สม่ำเสมอ)", "ตำแหน่งที่กลาย\nเท่านั้น", "โมเดลที่ fit แล้ว"],
    values: [0.510, 0.559, 0.577, 0.847],
  }], {
    x: M, y: y + 0.05, w: 5.6, h: 3.5,
    barDir: "col", chartColors: [C.accent],
    chartArea: { fill: { color: C.bg } },
    catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
    catAxisLabelFontFace: F, valAxisLabelFontFace: F, catAxisLabelFontSize: 10,
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.body,
    dataLabelFontFace: F, dataLabelFontSize: 12, dataLabelFormatCode: "0.000",
    showLegend: false, valAxisMaxVal: 1.0, valAxisMinVal: 0.4,
  });
  colHead(s, "อ่านอย่างไร", 6.35, y, 3.15);
  bullets(s, [
    { text: "positional weights + ordered logistic ทำงานหลัก", options: { breakLine: true } },
    { text: "การเลือก M ขยับผลในช่วง 0.796–0.854 เท่านั้น", options: { breakLine: true } },
    { text: "เราพูดตรง ๆ แทนที่จะให้ AUC สูงพากันเข้าใจผิด", options: {} },
  ], { x: 6.35, y: y + 0.38, w: 3.15, h: 3.0, fontSize: 15 });
  cite(s, "MANUSCRIPT §3.1, Table 3 (งานนี้) · learning-free baselines: 5_publication/null_baselines.py");
  s.addNotes("การเปิดด้วยสไลด์นี้เป็นการตั้งกรอบความคาดหวังอย่างซื่อสัตย์ ถ้าไม่พูด คนจะคิดว่า AUC 0.85 มาจาก representation ที่เราเสนอ ซึ่งไม่จริง");
}

{ /* 19 — atomic beats fixed and Atchley */
  const s = pres.addSlide();
  const y = head(s, "atomic (8 พารามิเตอร์) ชนะทั้ง BLOSUM100 แบบตรึง และ Atchley-5 ที่เป็น prior art", 21);
  figWide(s, "fig4_benchmark.png", 1.90, y, 6.4,
    "เทียบกับ Atchley-5: ชนะทั้งสองแกน แต่ margin เล็ก (d = 0.18 in-dist, 0.15 OOD) — เรานับว่าเป็น incremental");
  cite(s, "Fig. 4 (งานนี้) · 151 TCR, 22,827 mutant · Atchley et al., PNAS 102:6395 (2005)");
  s.addNotes("ต้องระวังไม่ขายเกินจริง margin เหนือ Atchley เล็ก สิ่งที่การเทียบนี้แยกออกมาได้คือ descriptor ที่มาจากโครงสร้างโมเลกุล ดีกว่า descriptor ที่มาจาก factor analysis ของ property tables — แต่ดีกว่าไม่มาก");
}

{ /* 20 — atomic loses in-distribution */
  const s = pres.addSlide();
  const y = head(s, "แต่ atomic ไม่ได้แทนที่ learned matrix ได้ — in-distribution ยังแพ้ชัดเจน\nนี่คือข้ออ้างที่เราตั้งไว้แล้วไม่รอด", 21, 3);
  table(s, [
    [th("การเปรียบเทียบ"), th("ผล"), th("ตีความ")],
    ["learned vs atomic (in-distribution)", "d = 0.83 · ชนะ 86% ของ TCR", "learned ชนะชัด"],
    ["learned vs atomic (TCR ที่ไม่เคยเห็น)", "0.723 vs 0.696", "learned ชนะเช่นกัน"],
    ["atomic vs learned (out-of-distribution)", "Δ = +0.008 ถึง +0.010 · d = 0.11", tb("จริงแต่เล็กมาก")],
  ], { x: M, y: y + 0.05, w: 9.0, colW: [3.6, 3.0, 2.4], rowH: 0.4, fontSize: 13 });
  callout(s, "power analysis: ยืนยัน d = 0.18 ที่ α = 0.05 ต้องใช้ ~243 TCR (และ ~425 หลังแก้ Bonferroni)\nทั้งโลกมี 151 TCR — ไม่มีการวิเคราะห์ซ้ำแบบไหนปิดช่องว่างนี้ได้ ต้องมี mutational scan ใหม่",
    { x: M, y: y + 1.85, w: 9.0, h: 0.95 });
  bullets(s, [
    { text: "ทำซ้ำได้ข้าม 5 ADVI seed ไม่เคยกลับด้าน (SD = 0.0009) — ผ่าน BH-FDR แต่ไม่ผ่าน Bonferroni", options: {} },
  ], { x: M, y: y + 2.88, w: 9.0, h: 0.8, fontSize: 15 });
  cite(s, "MANUSCRIPT §3.3, Table 2 (งานนี้) · 151 TCR คือจำนวนที่มี mutational scan ครบในวรรณกรรมทั้งหมด");
  s.addNotes("การรายงานผลที่ไม่เข้าข้างตัวเองพร้อม power analysis เป็นสิ่งที่ reviewer มองหา ตัวเลข 151 คือเพดานของทั้งสาขา ไม่ใช่ข้อจำกัดของเราคนเดียว");
}

{ /* 21 — Pareto */
  const s = pres.addSlide();
  const y = head(s, "frozen-backbone hybrid ดึงความแม่นกลับมาได้เกือบหมด (0.847 vs 0.854)\nโดยไม่เสีย out-of-distribution เลย (Δ = −0.0005, p = 0.70)", 20, 3);
  figWide(s, "fig5_hybrid_pareto.png", 2.21, y + 0.05, 6.4,
    "เทียบกับ atomic: d = 0.93 · ดีขึ้นใน 88.7% ของ 150 TCR · p = 7.7e−23 — ผลที่แข็งที่สุดของงาน และผ่าน Bonferroni ทั้ง family");
  cite(s, "Fig. 5 (งานนี้) · results/hybrid_frozen_s025.csv · ขอบเขต: ภายใน epitope ชุดเดิม (ดูส่วนที่ 5)");
  s.addNotes("ต้องพูดคำว่า 'ภายใน epitope ชุดเดิม' ตรงนี้เลย ห้ามรอไปพูดตอนหลัง เพราะส่วนที่ 5 จะแสดงว่าผลนี้ไม่รอดเมื่อเปลี่ยน epitope");
}

{ /* 22 — freezing is necessary */
  const s = pres.addSlide();
  const y = head(s, "การ freeze จำเป็นจริง ไม่ใช่บังเอิญ — residual ที่ fit พร้อมกัน\nเสีย out-of-distribution ที่ทุกค่า σ ที่ทดสอบ", 21);
  figWide(s, "fig6_shrinkage.png", 1.81, y + 0.05, 6.2,
    "ข้อโต้แย้งที่ชัดที่สุดคือ “มันแค่เลือก shrinkage ได้ดี” — การกวาด σ ตอบข้อนี้โดยตรง และคำตอบคือไม่ใช่");
  cite(s, "Fig. 6 (งานนี้) · 2_adversarial_review/hybrid_sweep.py · MANUSCRIPT §3.5");
  s.addNotes("นี่คือ adversarial check ที่เราตั้งขึ้นเพื่อจะหักล้างตัวเอง ถ้าผลออกมาว่า joint fit ก็ได้เท่ากัน ข้ออ้างเรื่อง freezing จะตกทันที");
}

/* ====================================================================== */
/* PART 5 — การกลับด้าน                                                    */
/* ====================================================================== */
divider("ส่วนที่ 5", "เปลี่ยน epitope แล้วทุกอย่างกลับด้าน", "ส่วนที่สำคัญที่สุดของงานนี้")
  .addNotes("ส่วนนี้ ~10 นาที คือ contribution ที่แท้จริงต่อสาขา ให้เวลาเยอะที่สุด");

{ /* 24 — Malone external */
  const s = pres.addSlide();
  const y = head(s, "บนข้อมูลอิสระ (Malone 2025) ลำดับกลับด้าน:\nlearned matrix ตกจากที่ 1 ไปที่ 4 จาก 5", 21);
  s.addImage({ path: FIG("fig10_external_validation.png"), x: M, y: y, w: 5.3, h: 5.3 / 2.03 });
  table(s, [
    [th("โมเดล"), th("Spearman ρ")],
    ["fixed BLOSUM100", "0.532"],
    ["learned 20×20 (BATMAN)", "0.592"],
    ["atomic", tb("0.664")],
    ["frozen hybrid", tb("0.699")],
  ], { x: M, y: y + 2.75, w: 5.3, colW: [3.3, 2.0], rowH: 0.25, fontSize: 12 });
  colHead(s, "สามอย่างต่างพร้อมกัน", 6.2, y, 3.3);
  bullets(s, [
    { text: "TCR ไม่เคยเห็น (20 clone)", options: { breakLine: true } },
    { text: "epitope ไม่เคยเห็น (YLQPRTFLL)", options: { breakLine: true } },
    { text: "วัดคนละอย่าง: tetramer binding ไม่ใช่ activation", options: {} },
  ], { x: 6.2, y: y + 0.35, w: 3.3, h: 1.7, fontSize: 14 });
  callout(s, "pseudo-replication:\n20 TCR ดู epitope เดียวกัน\nสหสัมพันธ์กัน ρ = 0.77\n» n_eff ≈ 1.3\nจึง bootstrap ที่ระดับ peptide\n(168 ตัว) แทน",
    { x: 6.2, y: y + 2.2, w: 3.3, h: 1.6 });
  cite(s, "Fig. 10 (งานนี้) · Malone et al., Nat Commun (2025) · 168/171 single substitution · null (BLOSUM100 uniform) ρ = 0.108");
  s.addNotes("ต้องพูดเรื่อง pseudo-replication ให้ชัด ถ้าใช้ paired test ข้าม TCR จะได้ p < 1e-4 ซึ่งเป็นค่าที่พองเกินจริง เราทิ้งค่าเหล่านั้นแล้วเปลี่ยนหน่วย resample เป็น peptide");
}

{ /* 25 — LOEO */
  const s = pres.addSlide();
  const y = head(s, "leave-one-epitope-out บน 23 epitope ยืนยันซ้ำ — และไปโดน hybrid ด้วย", 21);
  s.addImage({ path: FIG("fig11_leave_one_epitope_out.png"), x: M, y: y, w: 5.6, h: 5.6 / 1.92 });
  table(s, [
    [th("การเปรียบเทียบ"), th("Δ AUC"), th("d"), th("p")],
    ["atomic − learned", tb("+0.040"), "0.65", "0.003"],
    ["hybrid − atomic", tb("−0.028"), "−0.69", "0.005"],
  ], { x: M, y: y + 3.05, w: 5.6, colW: [2.6, 1.1, 0.9, 1.0], rowH: 0.3, fontSize: 12 });
  colHead(s, "สองข้อสรุปที่กลับด้าน", 6.3, y, 3.2);
  bullets(s, [
    { text: "atomic ชนะ learned — ตรงข้ามกับ in-distribution", options: { breakLine: true } },
    { text: "hybrid ตกต่ำกว่า atomic ที่มันถูกสร้างมาเพื่อปรับปรุง", options: { breakLine: true } },
    { text: "ครั้งนี้มี 23 epitope เป็น replication จริง ไม่ใช่ epitope เดียว", options: {} },
  ], { x: 6.3, y: y + 0.35, w: 3.2, h: 2.6, fontSize: 14 });
  cite(s, "Fig. 11 (งานนี้) · 6_external_validation/leave_one_epitope_out.py · MANUSCRIPT §3.11");
  s.addNotes("นี่คือจุดที่ผลของเราเองถูกหักล้างบางส่วน hybrid ที่เป็น headline ในส่วนที่ 4 กลับแย่กว่า atomic บน epitope ใหม่ เราเลือกรายงานแทนที่จะเก็บไว้");
}

{ /* 26 — sigma sweep mechanism */
  const s = pres.addSlide();
  const y = head(s, "σ sweep พิสูจน์กลไก: ความเสียหาย monotone ใน σ (Spearman ρ = −1.00)", 21);
  s.addImage({ path: FIG("fig12_residual_transfer.png"), x: M, y: y, w: 4.9, h: 4.9 / 1.52 });
  table(s, [
    [th("σ"), th("AUC (epitope ใหม่)"), th("Δ vs atomic"), th("p")],
    ["0.02", "0.6796", "−0.0056", "0.33"],
    ["0.05", "0.6733", "−0.0118", "0.30"],
    ["0.10", "0.6663", "−0.0189", "0.070"],
    ["0.25", "0.6569", tb("−0.0283"), tb("0.006")],
  ], { x: 5.6, y: y + 0.1, w: 3.9, colW: [0.55, 1.65, 1.05, 0.65], rowH: 0.32, fontSize: 11.5 });
  callout(s, "คำทำนายที่ตั้งไว้ก่อนรัน: ถ้าความเสียหายมาจาก residual จำ context\nของ epitope ที่เทรน การบีบ σ แรงขึ้นต้องลดความเสียหาย\nและที่ σ เข้าใกล้ 0 ต้องเท่ากับ atomic » เกิดขึ้นตรงตามนั้นทุกข้อ",
    { x: 5.6, y: y + 1.65, w: 3.9, h: 1.9 });
  cite(s, "Fig. 12 (งานนี้) · 6_external_validation/loeo_shrinkage.py · MANUSCRIPT §3.12");
  s.addNotes("ความต่างระหว่าง 'ข้อสังเกต' กับ 'กลไก' อยู่ตรงนี้ เราตั้งคำทำนายเชิงปริมาณที่หักล้างได้ก่อน แล้วรัน ถ้า hybrid แย่เท่ากันทุก σ คำอธิบายของเราจะผิดทันที");
}

{ /* 27 — the mirror stat */
  const s = pres.addSlide();
  const y = head(s, "โมเดลเดียวกัน ค่า σ เดียวกัน วัดสองแบบ — ได้ตัวเลขที่เป็นภาพสะท้อนกันพอดี", 21);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.8, y: y + 0.35, w: 3.8, h: 2.1,
    fill: { color: C.panel }, line: { color: C.accent, pt: 1.5 }, rectRadius: 0.1,
  });
  s.addText("+0.028", {
    x: 0.8, y: y + 0.5, w: 3.8, h: 1.0,
    fontSize: 54, fontFace: F, color: C.primary, bold: true, align: "center", margin: 0,
  });
  s.addText("AUC ที่ได้เพิ่ม\nบน epitope ที่เทรนด้วย", {
    x: 0.8, y: y + 1.55, w: 3.8, h: 0.75,
    fontSize: 15, fontFace: F, color: C.body, align: "center", margin: 0,
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.4, y: y + 0.35, w: 3.8, h: 2.1,
    fill: { color: C.hi }, line: { color: C.hiLine, pt: 1.5 }, rectRadius: 0.1,
  });
  s.addText("−0.028", {
    x: 5.4, y: y + 0.5, w: 3.8, h: 1.0,
    fontSize: 54, fontFace: F, color: C.hiText, bold: true, align: "center", margin: 0,
  });
  s.addText("AUC ที่เสียไป\nบน epitope ที่ไม่เคยเห็น", {
    x: 5.4, y: y + 1.55, w: 3.8, h: 0.75,
    fontSize: 15, fontFace: F, color: C.hiText, align: "center", margin: 0,
  });
  s.addText("residual ไม่ได้เรียนคุณสมบัติของกรดอะมิโน — มันจำ epitope ที่ใช้เทรน\nและความจำนั้นกลับเครื่องหมายทันทีที่เปลี่ยน epitope", {
    x: M, y: y + 2.7, w: 9.0, h: 0.9,
    fontSize: 17, fontFace: F, color: C.body, align: "center", bold: true, margin: 0,
  });
  cite(s, "MANUSCRIPT §3.12 (งานนี้) · เทียบ §3.4 (in-distribution) กับ Fig. 12 (held-out epitope) ที่ σ = 0.25");
  s.addNotes("ถ้าผู้ฟังจำได้แค่สไลด์เดียวจาก talk นี้ ขอให้เป็นสไลด์นี้ ตัวเลขบวกลบเท่ากันพอดีเป็นเรื่องบังเอิญ แต่มันสื่อสารได้คมมากว่า capacity ที่ fit กับ corpus ไม่ได้แปลว่าเข้าใจเคมี");
}

{ /* 28 — feature-tied residual */
  const s = pres.addSlide();
  const y = head(s, "ผูก residual กับ feature (36 พารามิเตอร์) ลบ penalty ได้ 87%\nและไม่ต่างจาก atomic บน epitope ใหม่อีกต่อไป (p = 0.21)", 21);
  s.addImage({ path: FIG("fig13_residual_design.png"), x: M, y: y, w: 4.3, h: 4.3 / 1.31 });
  table(s, [
    [th("Residual"), th("จำนวน"), th("in-dist Δ"), th("epitope ใหม่")],
    ["per-cell δ_ab", "400", "+0.0277", tb("−0.0282")],
    ["feature-tied Λ", tb("36"), "+0.0077", tb("−0.0037")],
  ], { x: 5.0, y: y + 0.15, w: 4.5, colW: [1.4, 0.75, 1.05, 1.3], rowH: 0.38, fontSize: 11 });
  bullets(s, [
    { text: "per-cell ยังแย่กว่า atomic บน epitope ใหม่อย่างมีนัยสำคัญ (p = 0.004) · feature-tied ไม่ต่างแล้ว (p = 0.21)", options: { breakLine: true } },
    { text: "feature-tied แลก 2:1 ในทางที่ดีกว่า", options: { breakLine: true } },
    { text: "ปัญหาอยู่ที่ residual ถูก index ด้วยอะไร ไม่ใช่ที่การเพิ่ม capacity", options: {} },
  ], { x: 5.0, y: y + 1.5, w: 4.5, h: 2.2, fontSize: 14 });
  cite(s, "Fig. 13 (งานนี้) · 6_external_validation/loeo_feature_residual.py · MANUSCRIPT §3.13");
  s.addNotes("ต้องพูดตรง ๆ ว่านี่ไม่ใช่โมเดลที่ดีที่สุด กำไรสัมบูรณ์เล็ก และมันไม่ได้ชนะ atomic บน epitope ใหม่ มันแค่ 'เลิกทำร้าย' สิ่งที่มันพิสูจน์คือกลไก ไม่ใช่ประสิทธิภาพ");
}

/* ====================================================================== */
/* PART 6 — ผลลบ ข้อจำกัด ทำซ้ำ                                            */
/* ====================================================================== */
divider("ส่วนที่ 6", "ผลลบ ข้อจำกัด และการทำซ้ำ", "สิ่งที่ไม่ได้ผล มีค่าพอ ๆ กับสิ่งที่ได้ผล")
  .addNotes("ส่วนนี้ ~7 นาที คนมักข้าม แต่เป็นส่วนที่ reviewer ให้ค่ามากที่สุด");

{ /* 30 — three negative results */
  const s = pres.addSlide();
  const y = head(s, "ผลลบสามข้อที่ประหยัดเวลาให้คนอื่นในสาขา", 22);
  const negs = [
    ["pMHC term ไม่ช่วย", "เพิ่มพจน์ pMHC-binding\nเข้าไปตรง ๆ ไม่ทำให้ดีขึ้น", "MANUSCRIPT §3.7"],
    ["ที่ระดับ proteome\nโมเดลไม่สำคัญ", "Hamming distance ที่ไม่ต้อง\nเรียนอะไรเลย ดึง target ที่ยืนยันแล้ว\nได้พอ ๆ กับโมเดลที่ fit แล้ว", "MANUSCRIPT §3.8"],
    ["falsification test\nที่ตั้งไว้ ไม่ผ่าน", "citrulline ควรใกล้ Q ที่สุด\nแต่โมเดลบอกว่าใกล้ R", "MANUSCRIPT §3.9"],
  ];
  negs.forEach((n, i) => {
    const x = M + i * 3.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: y + 0.15, w: 2.85, h: 2.9,
      fill: { color: C.panel }, line: { color: C.accent, pt: 1 }, rectRadius: 0.08,
    });
    s.addText(n[0], {
      x: x + 0.15, y: y + 0.3, w: 2.55, h: 0.8,
      fontSize: 16, fontFace: F, color: C.primary, bold: true, align: "left", margin: 0,
    });
    s.addText(n[1], {
      x: x + 0.15, y: y + 1.15, w: 2.55, h: 1.5,
      fontSize: 13, fontFace: F, color: C.body, align: "left", margin: 0,
    });
    s.addText(n[2], {
      x: x + 0.15, y: y + 2.65, w: 2.55, h: 0.3,
      fontSize: 11, fontFace: F, color: C.muted, italic: true, margin: 0,
    });
  });
  cite(s, "ทั้งสามข้อเป็นผลของงานนี้ · proteome null: 5_publication/null_baselines.py · PTM: 5_publication/noncanonical.py");
  s.addNotes("ผลลบข้อที่สองสำคัญมากในทางปฏิบัติ: ถ้าจะสแกน proteome ทั้งตัวเพื่อหา off-target อย่าเพิ่งไปลงทุนกับโมเดลซับซ้อน คอขวดอยู่ที่อื่น");
}

{ /* 31 — falsification failed */
  const s = pres.addSlide();
  const y = head(s, "เราลงทะเบียนบททดสอบที่จะหักล้างตัวเองไว้ล่วงหน้า — และมันไม่ผ่าน", 21);
  figWide(s, "fig9_noncanonical.png", 1.96, y + 0.05, 6.4,
    "แยกทีละ feature พบว่าระยะ R » citrulline เกือบทั้งหมดมาจากพจน์ charge อย่างเดียว — descriptor set ปัจจุบันยังไม่พอสำหรับ PTM");
  cite(s, "Fig. 9 (งานนี้) · เกณฑ์ตั้งไว้ก่อนรัน: citrulline ต้องใกล้ Q ที่สุด · ผลจริง: ใกล้ R");
  s.addNotes("การขยายไปยังกรดอะมิโนนอก 20 ตัวเป็นข้ออ้างที่เราชอบที่สุด เราจึงตั้งเกณฑ์หักล้างไว้ก่อน แล้วรายงานตอนมันไม่ผ่าน ข้ออ้างเรื่อง PTM ยังใช้ไม่ได้จนกว่าจะปรับ descriptor");
}

{ /* 32 — limitations */
  const s = pres.addSlide();
  const y = head(s, "ข้อจำกัดที่ต้องพูดตรง ๆ ก่อนใครถาม", 22);
  table(s, [
    [th("ข้อจำกัด"), th("ผลต่อการตีความ"), th("แก้ได้อย่างไร")],
    ["ADVI ให้ interval แคบไป 43%", "รายงานได้เฉพาะ point estimate", "รัน NUTS ในรอบสุดท้าย"],
    ["external set มี epitope เดียว", "n_eff ≈ 1.3 ไม่ใช่ 20", "ต้องหา epitope อิสระเพิ่ม 2–3 ตัว"],
    ["สมมติฐาน additivity ข้ามตำแหน่ง", "ทำนาย multi-mutant ต่ำไป (เช่น titin)", "ต้องมีพจน์ interaction"],
    ["ทั้งสาขามี 151 TCR", "power ไม่พอยืนยัน effect เล็ก", "ต้องมี mutational scan ใหม่"],
    ["ข้อมูลหลักมาจากการ curate ชุดเดียว", "assay convention ร่วมกันหมด", "ทำซ้ำบนฐานข้อมูลอื่น"],
  ], { x: M, y: y + 0.1, w: 9.0, colW: [3.1, 3.1, 2.8], rowH: 0.42, fontSize: 13 });
  cite(s, "ASSESSMENT.md §2.1 (งานนี้) · MANUSCRIPT §5");
  s.addNotes("แถวที่สามคือข้อจำกัดร่วมของทุกโมเดลในสาขานี้ ไม่ใช่เฉพาะของเรา แต่มันอธิบายว่าทำไมเคส titin ถึงทำนายระดับต่ำไปทั้งที่จัดอันดับได้ถูก");
}

{ /* 33 — reproduce */
  const s = pres.addSlide();
  const y = head(s, "ทำซ้ำได้ทั้งหมด — ข้อมูลตรงกับต้นฉบับระดับ byte และทุกผลมีสคริปต์กำกับ", 21);
  colHead(s, "ลำดับคำสั่ง", M, y, 5.4);
  panel(s, "python3 5_publication/verify_setup.py        # ตรวจ hash และ dependency\n\nfor e in exp1 exp2 exp3 exp4 exp5 exp6 exp7; do\n    OMP_NUM_THREADS=1 python3 1_core_model/run_one.py $e &\ndone; wait                                   # ~20 นาที/ตัว ขนานได้\n\npython3 5_publication/harmonized_protocol.py 0.25   # ~49 นาที\npython3 6_external_validation/run_validation.py\npython3 6_external_validation/leave_one_epitope_out.py",
    { x: M, y: y + 0.36, w: 5.4, h: 2.6 }, 11);
  colHead(s, "สิ่งที่ตรวจแล้ว", 6.1, y, 3.4);
  bullets(s, [
    { text: "train_test_data_folds.xlsx ตรงกับต้นฉบับ byte ต่อ byte (SHA-256)", options: { breakLine: true } },
    { text: "BLOSUM100 ที่เขียนใหม่ ต่างจากของเดิม 0.0", options: { breakLine: true } },
    { text: "ทุกตัวเลขในสไลด์นี้อ่านจาก results/*.csv ที่ commit ไว้", options: { breakLine: true } },
    { text: "ทุกรูปสร้างใหม่ได้จาก figures.py และสคริปต์ที่กำกับไว้", options: {} },
  ], { x: 6.1, y: y + 0.36, w: 3.4, h: 2.7, fontSize: 13 });
  cite(s, "PROTOCOL.md ส่วนที่ 5 · REPRODUCE.ipynb (43 cell รันผ่านทั้งหมด) · MANUSCRIPT §2.7");
  s.addNotes("ถ้ามีคนอยากทำซ้ำจริง ให้เริ่มที่ REPRODUCE.ipynb ก่อน มันรันครบและใช้ผลที่ cache ไว้ ไม่ต้องรอ 3 ชั่วโมง จากนั้นค่อยรันสคริปต์เต็มถ้าต้องการสร้างผลใหม่เอง");
}

/* ====================================================================== */
/* CONCLUSIONS / REFERENCES                                                */
/* ====================================================================== */
{
  const s = pres.addSlide();
  s.background = { color: C.primary };
  s.addText("สรุป", {
    x: M, y: 0.22, w: 9.0, h: 0.4,
    fontSize: 19, fontFace: F, color: C.onDarkMuted, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 0.66, w: 9.0, h: 0.04, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText([
    { text: "1. แทน matrix 380 พารามิเตอร์ด้วย descriptor เชิงเคมี 8 ตัวได้ ", options: { bold: true, breakLine: false } },
    { text: "โดยได้ metric axioms มาฟรี และขยายไปนอก 20 กรดอะมิโนได้ในหลักการ", options: { breakLine: true } },
    { text: "2. in-distribution: frozen hybrid เป็น Pareto improvement ", options: { bold: true, breakLine: false } },
    { text: "0.847 vs 0.854, d = 0.93, ชนะ 88.7% ของ TCR — แต่ขอบเขตคือ epitope ชุดเดิมเท่านั้น", options: { breakLine: true } },
    { text: "3. เปลี่ยน epitope แล้วข้อสรุปกลับด้าน ", options: { bold: true, breakLine: false } },
    { text: "capacity ที่ fit กับ corpus ไม่ transfer · น้ำหนักเชิงเคมี 8 ตัว transfer ได้", options: { breakLine: true } },
    { text: "4. สิ่งที่ residual ถูก index ด้วย สำคัญกว่าจำนวนพารามิเตอร์ ", options: { bold: true, breakLine: false } },
    { text: "ผูกกับ feature (36) แทนคู่กรดอะมิโน (400) ลบ transfer penalty ได้ 87%", options: {} },
  ], {
    x: M, y: 0.85, w: 9.0, h: 3.8,
    fontSize: 17, fontFace: F, color: C.onDark, paraSpaceAfter: 18, valign: "top",
  });
  s.addText("โค้ด ผลลัพธ์ และรูปทั้งหมด: TCR_atomic_bayesian/  ·  เริ่มอ่านที่ START_HERE.md และ REPRODUCE.ipynb", {
    x: M, y: 4.75, w: 9.0, h: 0.4,
    fontSize: 13, fontFace: F, color: C.onDarkMuted, margin: 0,
  });
  s.addNotes("สไลด์นี้ต้องค้างอยู่บนจอตลอดช่วง Q&A ข้อ 3 และ 4 คือ contribution ที่แท้จริง ข้อ 1 และ 2 เป็นทางที่เดินมาถึงตรงนั้น");
}

{
  const s = pres.addSlide();
  s.addText("References", {
    x: M, y: 0.2, w: 9.0, h: 0.5,
    fontSize: 24, fontFace: F, color: C.primary, bold: true, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 0.74, w: 9.0, h: 0.02, fill: { color: C.rule }, line: { color: C.rule },
  });
  const refs = [
    "Banerjee A., Pattinson D.J., Wincek C.L., Bunk P., Axhemi A., Chapin S.R., Navlakha S., Meyer H.V. (2025). T cell receptor cross-reactivity prediction improved by a comprehensive mutational scan database. Cell Systems 16, 101345. doi:10.1016/j.cels.2025.101345",
    "Malone M.J., Huang C., Zhang Y., Qi Y., Williams L., Su L.F., Lou J., Jiang N. (2026). Resistance potential of the HLA-A2-restricted immunodominant SARS-CoV-2-specific CD8+ T cell receptor repertoire to antigenic drift. Nature Communications 17, 686. doi:10.1038/s41467-025-67336-w  [external validation set]",
    "Dorigatti E. et al. (2024). Predicting T cell receptor functionality against mutant epitopes. Cell Genomics 4, 100634.",
    "Atchley W.R., Zhao J., Fernandes A.D., Drüke T. (2005). Solving the protein sequence metric problem. PNAS 102, 6395–6400.",
    "Kucukelbir A., Tran D., Ranganath R., Gelman A., Blei D.M. (2017). Automatic differentiation variational inference. JMLR 18(14), 1–45.",
    "Linette G.P. et al. (2013). Cardiovascular toxicity and titin cross-reactivity of affinity-enhanced T cells in myeloma and melanoma. Blood 122, 863–871.",
    "Kula T. et al. (2019). T-Scan: a genome-wide method for the systematic discovery of T cell epitopes. Cell 178, 1016–1028.",
    "RDKit: Open-source cheminformatics. https://www.rdkit.org",
  ];
  s.addText(refs.map((r, i) => ({ text: r, options: { breakLine: i < refs.length - 1 } })), {
    x: M, y: 0.88, w: 9.0, h: 4.4,
    fontSize: 11.5, fontFace: F, color: C.body, paraSpaceAfter: 7, valign: "top",
  });
  s.addNotes("Malone et al. 2025 คือ external validation set — DOI ยืนยันจาก URL ที่ malone2025.py ใช้ดาวน์โหลด supplementary จริง (41467_2025_67336) ข้อมูลชุดนี้อยู่ที่ GEO GSE246491 และ ImmPort SDY3323 ด้วย. ระวัง: DOI ขึ้นต้น 025 (ปีที่ตอบรับ) แต่ citation จริงคือ Nat Commun 17, 686 (2026) — เอกสารในโปรเจกต์เรียก “Malone 2025” ซึ่งเป็นปีที่ตอบรับ ไม่ใช่ปีตีพิมพ์");
}

/* ====================================================================== */
/* APPENDIX                                                                */
/* ====================================================================== */
{
  const s = pres.addSlide();
  appendixLabel(s, "Appendix A — โครงสร้างไฟล์ในโปรเจกต์");
  const y = appendixHead(s, "ไฟล์ไหนทำอะไร — สำหรับคนที่จะเปิดโค้ดจริง");
  table(s, [
    [th("ที่อยู่"), th("หน้าที่")],
    ["batman_atomic.py", "ไลบรารีหลัก: build_model(), fit(), posterior_distance(), per_tcr_auc()"],
    ["1_core_model/", "การทดลอง exp1–exp7 และ hybrid_full.py"],
    ["2_adversarial_review/", "การตรวจที่ตั้งใจหักล้างตัวเอง (hybrid_sweep, review_checks)"],
    ["4_pathB_proteome/", "การสแกนระดับ proteome และ null baseline"],
    ["5_publication/", "MANUSCRIPT.md, TABLES.md, REPRODUCE.ipynb, figures.py, สคริปต์สร้างสไลด์"],
    ["6_external_validation/", "Malone 2025, leave-one-epitope-out, σ sweep, feature-tied residual"],
    ["results/", "ผลที่ cache ไว้ทั้งหมด — ทุกตัวเลขในสไลด์อ่านจากที่นี่"],
    ["figures/", "รูปที่ 1–13 ทั้ง PNG 300dpi และ PDF"],
  ], { x: M, y, w: 9.0, colW: [2.6, 6.4], rowH: 0.33, fontSize: 12 });
  s.addNotes("ใช้ตอบคำถามว่า 'โค้ดอยู่ตรงไหน' ระหว่าง Q&A");
}

{
  const s = pres.addSlide();
  appendixLabel(s, "Appendix B — เวลาที่ใช้รันจริง");
  const y = appendixHead(s, "งบเวลาสำหรับคนที่จะรันซ้ำ (เครื่อง 1 คอร์ต่อ 1 งาน)");
  table(s, [
    [th("งาน"), th("เวลา"), th("หมายเหตุ")],
    ["exp1–exp7 (ขนานกันได้)", "~20 นาที / ตัว", "ตั้ง OMP_NUM_THREADS=1 แล้วรันพร้อมกัน"],
    ["hybrid_full.py 0.25", "~26 นาที", "เทรน 2 ขั้น"],
    ["harmonized_protocol.py 0.25", "~49 นาที", "5,352 แถว ทั้งสอง setting"],
    ["review_checks.py", "~14 นาที", "การตรวจเชิงวิพากษ์"],
    ["hybrid_sweep.py", "~19 นาที", "σ sweep in-distribution"],
    ["leave_one_epitope_out.py", "ยาวที่สุด", "23 epitope × 5 โมเดล"],
    ["REPRODUCE.ipynb", "ไม่กี่นาที", "ใช้ผลที่ cache ไว้ — เริ่มที่นี่"],
  ], { x: M, y, w: 9.0, colW: [3.2, 1.8, 4.0], rowH: 0.36, fontSize: 12 });
  s.addNotes("เวลาทั้งหมดมาจาก log จริงที่บันทึกไว้ ไม่ใช่การประมาณ");
}

{
  const s = pres.addSlide();
  appendixLabel(s, "Appendix C — เกณฑ์คัดข้อมูลของ Malone 2025");
  const y = appendixHead(s, "การตัดสินใจสามข้อ ทำก่อนรันโมเดลใด ๆ");
  bullets(s, [
    { text: "จาก 172 แถว: 3 แถวเป็น wild type และ 1 แถวเป็นความคลาดเคลื่อนในการถอดความ (YLQSPTFLL ต่างจาก wild type 2 ตำแหน่ง) » ตัดออก เหลือ 168 จาก 171 single substitution ที่เป็นไปได้ (98%)", options: { breakLine: true } },
    { text: "แถว wild type ไม่นำมาให้คะแนน เพราะระยะเป็นศูนย์ในทุกโมเดลอยู่แล้ว", options: { breakLine: true } },
    { text: "ใช้เฉพาะ TCR ที่ YLQPRTFLL เป็น index peptide จริง ๆ ตามเกณฑ์ที่ตั้งไว้ก่อนว่า wild type ต้องติดอันดับ 10% แรกของ binding profile ของ TCR นั้น » ผ่าน 20 จาก 23 (อันดับ 1–8) ตก 3 ตัว (อันดับ 36, 80, 81) ตรงกับที่ paper ต้นทางรายงาน", options: {} },
  ], { x: M, y: y + 0.08, w: 9.0, h: 2.85, fontSize: 14 });
  callout(s, "กับดักที่เจอตอนเขียนโค้ด: แถวแรกของไฟล์เขียนว่า “YLQPRTFLL wild type” (ยาว 19 ตัวอักษร)\nถ้าไม่ตัดคำก่อน hamming() จะคืนค่า −1 และแถวนั้นจะถูกจัดกลุ่มผิด",
    { x: M, y: y + 2.92, w: 9.0, h: 0.8 });
  s.addNotes("เกณฑ์ทั้งสามข้อถูกตั้งจากไฟล์ข้อมูลอย่างเดียว ก่อนเห็นผลของโมเดล เพื่อไม่ให้เป็นการเลือกเกณฑ์ตามผล");
}

{
  const s = pres.addSlide();
  appendixLabel(s, "Appendix D — บทเรียนเชิงวิศวกรรม: ทำไม hybrid_feature ต้อง normalize");
  const y = appendixHead(s, "ADVI ระเบิดเป็น NaN ทุก learning rate จนกว่าจะหาร feature_scale");
  table(s, [
    [th("สภาพ"), th("ค่าเฉลี่ยของพจน์ quadratic"), th("ค่าสูงสุด"), th("ผล")],
    ["ไม่ normalize", "57", "232", "exp() overflow » NaN ทุก lr"],
    ["หารด้วย feature_scale (s = 3.69)", "4.19", "17", tb("fit ผ่านปกติ")],
  ], { x: M, y, w: 9.0, colW: [2.7, 2.5, 1.35, 2.45], rowH: 0.4, fontSize: 12 });
  bullets(s, [
    { text: "พจน์ base (atomic ที่ตรึงไว้) มีค่าเฉลี่ย 12 — พจน์ quadratic ที่ 57 จึงกลบมันหมด", options: { breakLine: true } },
    { text: "feature_scale = sqrt( mean( Σ Δφ² บนตำแหน่งที่เปลี่ยน ) )", options: { breakLine: true } },
    { text: "ต้องคำนวณจาก training array เท่านั้น แล้วใช้ค่าเดิมกับ test — ไม่งั้นข้อมูลรั่ว", options: {} },
  ], { x: M, y: y + 1.35, w: 9.0, h: 2.2, fontSize: 15 });
  s.addNotes("เขียนไว้เพราะใครก็ตามที่ลองทำ quadratic form บนโมเดลนี้จะเจอปัญหาเดียวกัน และอาการมันดูเหมือนโมเดลผิด ทั้งที่เป็นเรื่องสเกลล้วน ๆ");
}

{
  const s = pres.addSlide();
  appendixLabel(s, "Appendix E — คำถามที่คาดว่าจะโดนถาม");
  const y = appendixHead(s, "คำถามที่เตรียมคำตอบไว้แล้ว");
  table(s, [
    [th("คำถาม"), th("คำตอบสั้น")],
    ["ทำไมไม่ใช้ deep learning ไปเลย", "ข้อมูลมี 151 TCR ทั้งสาขา และผลของเราแสดงว่าการเพิ่ม capacity ทำให้ transfer แย่ลง"],
    ["8 descriptor พอจริงหรือ", "ไม่พอสำหรับ PTM — บททดสอบ citrulline ไม่ผ่าน เรารายงานไว้แล้ว"],
    ["ทำไม hybrid ถึงแย่กว่า atomic บน epitope ใหม่", "residual จำ context ของตำแหน่งใน epitope ที่เทรน · σ sweep ยืนยัน (ρ = −1.00)"],
    ["ผลบน Malone มี 20 TCR ทำไมบอก n = 1.3", "ทุกตัวดู epitope เดียวกัน สหสัมพันธ์ 0.77 จึงเป็น pseudo-replication"],
    ["ทำไมไม่ใช้ NUTS ทั้งหมด", "ต้อง fit หลายพันครั้ง · ตรวจแล้วว่า point estimate ตรงกัน r = 0.997"],
    ["เอาไปใช้กับ TCR ตัวใหม่ได้ไหม", "ได้ด้วย pan_tcr mode แต่ AUC ตกจาก ~0.85 เหลือ ~0.70"],
  ], { x: M, y, w: 9.0, colW: [3.3, 5.7], rowH: 0.5, fontSize: 12 });
  s.addNotes("เปิดสไลด์นี้ระหว่าง Q&A ได้ทันที");
}

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT));
