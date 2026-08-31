"""
build_slides.py
===============
Builds ``SLIDES.html`` -- a self-contained talk deck explaining the project to
a mixed audience (no biology or CS assumed) while keeping the technical terms
a specialist needs to engage with.

Figures are inlined as data URIs because the Artifact CSP blocks external
hosts. Everything else is hand-authored HTML/CSS/SVG.

Usage:  python3 build_slides.py
"""

from __future__ import annotations

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "figures")
OUT = os.path.join(HERE, "SLIDES.html")


def data_uri(name: str) -> str:
    with open(os.path.join(FIG, name), "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()


HTML = r"""<title>เคมีแทนตารางความคล้าย</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;600&family=Noto+Sans+Thai:wght@400;600;700&family=Noto+Serif+Thai:wght@400;600&display=swap">

<style>
/* ============================================================ tokens ==== */
:root{
  --paper:#F7F9F8; --surface:#FFFFFF; --ink:#10171A; --ink-2:#33403D;
  --muted:#6B7B78; --line:#D8E0DD; --line-2:#EAF0EE;
  --atom:#0072B2;      /* atomic model            */
  --signal:#D55E00;    /* learned 20x20 (BATMAN)  */
  --accent:#009E73;    /* frozen hybrid, this work*/
  --prior:#E69F00;     /* Atchley-5, prior art    */
  --null:#CC79A7;      /* learning-free null      */
  --shadow:0 1px 2px rgba(16,23,26,.05),0 8px 24px -12px rgba(16,23,26,.18);
  --figure-bg:#FFFFFF;
  --display:"Archivo","Noto Sans Thai",system-ui,sans-serif;
  --body:"Source Serif 4","Noto Serif Thai",Georgia,serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0E1416; --surface:#161F21; --ink:#EAF2EF; --ink-2:#BCCBC7;
    --muted:#8B9C98; --line:#2A3639; --line-2:#202B2D;
    --atom:#4FA8DC; --signal:#F08A45; --accent:#3FC7A0; --prior:#F0BE55;
    --null:#DB9CC0;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --paper:#0E1416; --surface:#161F21; --ink:#EAF2EF; --ink-2:#BCCBC7;
  --muted:#8B9C98; --line:#2A3639; --line-2:#202B2D;
  --atom:#4FA8DC; --signal:#F08A45; --accent:#3FC7A0; --prior:#F0BE55;
  --null:#DB9CC0;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--body); font-size:17px; line-height:1.62;
  -webkit-font-smoothing:antialiased;
}

/* ============================================================ deck ====== */
.deck{height:100dvh; overflow-y:auto; scroll-snap-type:y mandatory; scroll-behavior:smooth}
.slide{
  min-height:100dvh; scroll-snap-align:start; scroll-snap-stop:always;
  display:flex; align-items:center; justify-content:center;
  padding:clamp(26px,4vw,56px) clamp(20px,5vw,80px) clamp(52px,6vw,76px);
  border-bottom:1px solid var(--line-2);
}
.inner{width:min(1120px,100%); display:flex; flex-direction:column; gap:clamp(14px,1.8vw,26px)}

/* ============================================================ type ====== */
.eyebrow{
  font-family:var(--mono); font-size:11.5px; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  display:flex; align-items:center; gap:10px;
}
.eyebrow::before{content:""; width:26px; height:2px; background:currentColor; opacity:.55}
h1{
  font-family:var(--display); font-weight:800;
  font-size:clamp(38px,6.2vw,80px); line-height:1.02; letter-spacing:-.024em;
  margin:0; text-wrap:balance;
}
h2{
  font-family:var(--display); font-weight:700;
  font-size:clamp(27px,3.5vw,44px); line-height:1.12; letter-spacing:-.018em;
  margin:0; text-wrap:balance;
}
h3{
  font-family:var(--display); font-weight:600; font-size:clamp(15px,1.5vw,18px);
  letter-spacing:-.005em; margin:0;
}
p{margin:0; max-width:68ch}
.lede{font-size:clamp(17px,1.85vw,21px); color:var(--ink-2); line-height:1.58}
.tiny{font-size:13px; color:var(--muted); line-height:1.5}
strong{font-weight:600; color:var(--ink)}
.mono{font-family:var(--mono)}
em.term{
  font-style:normal; font-family:var(--mono); font-size:.86em;
  color:var(--muted); white-space:nowrap;
}

/* ============================================================ bits ====== */
.grid{display:grid; gap:clamp(12px,1.5vw,20px)}
.g2{grid-template-columns:repeat(2,1fr)} .g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
.g2w{grid-template-columns:1.32fr 1fr}
@media(max-width:860px){.g2,.g2w,.g3,.g4{grid-template-columns:1fr}}

.card{
  background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:clamp(14px,1.6vw,20px); display:flex; flex-direction:column; gap:8px;
  box-shadow:var(--shadow);
}
.card .k{font-family:var(--mono); font-size:11px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--muted)}
.card .v{font-family:var(--display); font-weight:700;
  font-size:clamp(22px,2.6vw,32px); line-height:1; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.card p{font-size:14.5px; line-height:1.5; color:var(--ink-2)}

.rail{border-left:3px solid var(--accent); padding-left:16px}
.rail.warn{border-color:var(--signal)} .rail.atom{border-color:var(--atom)}

.chip{
  display:inline-flex; align-items:center; gap:7px; font-family:var(--mono);
  font-size:11.5px; font-weight:600; letter-spacing:.05em; padding:4px 10px;
  border-radius:999px; border:1px solid var(--line); color:var(--ink-2);
  background:var(--surface); white-space:nowrap;
}
.chip::before{content:""; width:8px; height:8px; border-radius:50%;
  background:var(--dot,var(--muted))}
.chips{display:flex; flex-wrap:wrap; gap:8px}

table{border-collapse:collapse; width:100%; font-size:14.5px}
th,td{text-align:left; padding:9px 12px; border-bottom:1px solid var(--line-2)}
th{font-family:var(--mono); font-size:11px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); font-weight:600;
  border-bottom:1px solid var(--line)}
td.num{font-family:var(--mono); font-variant-numeric:tabular-nums; text-align:right}
.tw{overflow-x:auto; -webkit-overflow-scrolling:touch}

/* The figure card is ALWAYS light, because the PNGs it holds have white
   backgrounds. Anything printed on it must therefore take its colour from
   this fixed pair, never from the theme tokens -- otherwise the caption goes
   light-grey-on-white the moment the viewer is in dark mode. */
.figure{
  background:var(--figure-bg); border:1px solid var(--line); border-radius:10px;
  padding:12px; box-shadow:var(--shadow); overflow:hidden;
  --on-figure:#33403D; --on-figure-strong:#10171A;
}
.figure img{
  width:100%; height:auto; display:block; border-radius:4px;
  max-height:var(--fig-max,44vh); object-fit:contain; margin:0 auto;
}
.figure.tall img{--fig-max:40vh}
.figure.mid img{--fig-max:36vh}
.figure.side img{--fig-max:46vh}
figcaption{font-size:12.5px; color:var(--on-figure); line-height:1.5;
  padding:10px 4px 2px; font-family:var(--body)}
figcaption strong{color:var(--on-figure-strong)}

.verdict{display:flex; gap:12px; align-items:flex-start}
.verdict .mark{
  font-family:var(--display); font-weight:800; font-size:15px; line-height:1.35;
  flex:none; width:22px;
}
.verdict p{font-size:14px; line-height:1.5}

.path{display:grid; grid-template-columns:repeat(4,1fr); gap:10px}
@media(max-width:860px){.path{grid-template-columns:1fr}}
.step{
  border:1px solid var(--line); border-left:3px solid var(--signal);
  border-radius:8px; padding:10px 12px; background:var(--surface);
  display:flex; flex-direction:column; gap:4px;
}
.step.ok{border-left-color:var(--accent)}
.step .n{font-family:var(--mono); font-size:10.5px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted)}
.step .t{font-family:var(--mono); font-size:12.5px; color:var(--ink); line-height:1.4}
.step .w{font-size:12px; color:var(--muted); line-height:1.45}
.yes .mark{color:var(--accent)} .no .mark{color:var(--signal)}
.neu .mark{color:var(--muted)}

.eq{
  font-family:var(--mono); font-size:clamp(14px,1.65vw,19px);
  background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:16px 18px; overflow-x:auto; line-height:1.75; color:var(--ink);
}
.eq .hl{color:var(--signal); font-weight:600}
.eq .hl2{color:var(--atom); font-weight:600}
.eq .cmt{color:var(--muted)}

/* ============================================================ nav ======= */
.rail-nav{
  position:fixed; right:clamp(10px,1.6vw,22px); top:50%;
  transform:translateY(-50%); display:flex; flex-direction:column; gap:9px;
  z-index:40;
}
.rail-nav a{
  width:9px; height:9px; border-radius:50%; background:var(--line);
  border:1px solid transparent; transition:background .18s,transform .18s;
}
.rail-nav a:hover{background:var(--muted); transform:scale(1.35)}
.rail-nav a.on{background:var(--accent); transform:scale(1.35)}
.rail-nav a:focus-visible{outline:2px solid var(--accent); outline-offset:3px}
@media(max-width:720px){.rail-nav{display:none}}

.hud{
  position:fixed; left:clamp(14px,2vw,26px); bottom:clamp(12px,1.8vw,22px);
  font-family:var(--mono); font-size:11px; letter-spacing:.12em;
  color:var(--muted); z-index:40; display:flex; gap:14px; align-items:center;
  background:color-mix(in srgb,var(--paper) 86%,transparent);
  padding:5px 11px; border-radius:999px; border:1px solid var(--line);
  font-variant-numeric:tabular-nums;
}
@media(prefers-reduced-motion:reduce){
  .deck{scroll-behavior:auto} *{transition:none!important}
}
</style>

<div class="deck" id="deck">

<!-- ==================================================== 1 · title ====== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">งานวิจัย · Computational Immunology</div>
    <h1>เอา<span style="color:var(--atom)">เคมีจริง</span><br>มาแทนตารางความคล้าย</h1>
    <p class="lede">
      แทนที่ <em class="term">20×20 amino-acid similarity matrix</em> ด้วย
      <strong>atomic peptide representation</strong> ในโมเดล Bayesian
      ที่ทำนายว่า T cell receptor จะยังจับ peptide ที่กลายพันธุ์ได้หรือไม่
    </p>
    <div class="chips" style="margin-top:6px">
      <span class="chip" style="--dot:var(--atom)">151 TCR</span>
      <span class="chip" style="--dot:var(--signal)">22,827 การวัด</span>
      <span class="chip" style="--dot:var(--accent)">8 พารามิเตอร์ แทน 380</span>
      <span class="chip" style="--dot:var(--null)">7 การทดลอง + adversarial review</span>
    </div>
    <p class="tiny" style="margin-top:14px">
      ต่อยอดจาก BATMAN (Banerjee et al., <em>Cell Systems</em> 16, 101345, 2025)
      · เลื่อนลง หรือกดลูกศร ↓ เพื่อดูต่อ
    </p>
  </div>
</section>

<!-- ==================================================== 2 · problem ==== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">01 · โจทย์</div>
    <h2>ถ้าเป้าหมายเปลี่ยนไปนิดเดียว ระบบภูมิคุ้มกันยังจำได้ไหม</h2>
    <p class="lede">
      T cell มีเสาอากาศชื่อ <strong>TCR</strong> คอยตรวจชิ้นส่วนโปรตีนสั้น ๆ
      (<em class="term">peptide</em>, ยาว 8–20 ตัวอักษร) ที่เซลล์ยกมาโชว์บนผิว
      (<em class="term">MHC</em>) — ถ้าตรงกับที่จำได้ ก็สั่งทำลายเซลล์นั้น
    </p>
    <div class="grid g2">
      <div class="rail atom">
        <h3>คำถามคือ</h3>
        <p style="margin-top:6px">
          ถ้า peptide เปลี่ยน<strong>แค่ 1 ตัวอักษร</strong> TCR ยังจับอยู่ไหม
          ความสามารถจับของที่ไม่เหมือนเป๊ะนี้เรียกว่า
          <em class="term">cross-reactivity</em>
        </p>
      </div>
      <div class="rail warn">
        <h3>ทำไมต้องแม่น</h3>
        <p style="margin-top:6px">
          <strong>จับไม่พอ</strong> → วัคซีนมะเร็งเลือก neoantigen ผิด<br>
          <strong>จับเกิน</strong> → TCR therapy ไปโจมตีเนื้อเยื่อปกติ
          (<em class="term">off-target toxicity</em>) ซึ่งเคยทำให้ผู้ป่วยเสียชีวิตมาแล้ว
        </p>
      </div>
    </div>
    <p class="tiny">
      เทียบให้เห็นภาพ: เหมือนระบบจดจำใบหน้า — เปลี่ยนทรงผมนิดเดียวยังจำได้ไหม
      และที่สำคัญกว่า คือมัน<strong>ไม่ควร</strong>จำสลับคนอื่นเป็นคุณ
    </p>
  </div>
</section>

<!-- ==================================================== 2b · biology ==== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">01b · ชีววิทยาและข้อมูล</div>
    <h2>สิ่งที่วัดได้จริงในห้องแล็บ</h2>
    <figure class="figure" style="--fig-max:56vh">
      <img src="__FIGBIO__" alt="TCR reading a peptide in the MHC groove, a complete single-substitution scan, and the scale of the BATCAVE database">
      <figcaption>
        <strong>a</strong> TCR อ่าน peptide ในร่อง MHC ·
        <strong>b</strong> การสแกนจริงของ TCR a3a ต่อ MAGE-A3 — ทุกตำแหน่ง × 19 ตัวเลือก
        (ข้อมูลจริง) · <strong>c</strong> ขยายเป็น BATCAVE
      </figcaption>
    </figure>
  </div>
</section>

<!-- ==================================================== 3 · model ====== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">02 · โมเดลเดิมทำงานยังไง</div>
    <h2>วัดเป็น “ระยะทาง” จาก peptide ต้นแบบ</h2>
    <p class="lede">
      BATMAN ให้คะแนน peptide กลายพันธุ์ด้วยระยะทางไปยัง peptide ต้นแบบ
      (<em class="term">index peptide</em>) แล้วแปลงเป็นระดับการกระตุ้น 3 ขั้น
    </p>
    <div class="eq">
      d(peptide, index) &nbsp;=&nbsp; Σ<sub>j</sub> &nbsp;<span class="hl2">w<sub>j</sub></span>&nbsp; · &nbsp;<span class="hl">M</span>[ a<sub>index,j</sub> , a<sub>peptide,j</sub> ]<br>
      <span class="cmt">        ↑ ตำแหน่งไหนสำคัญ      ↑ เปลี่ยนตัวอักษรนี้ “แพง” แค่ไหน</span><br><br>
      activation ~ OrderedLogistic( d₀ − d , cutpoints )
      <span class="cmt">&nbsp; → non / weak / strong</span>
    </div>
    <div class="grid g2">
      <div class="card" style="border-left:3px solid var(--atom)">
        <div class="k">w · positional weights</div>
        <p>ตำแหน่งไหนใน peptide ที่ TCR สนใจ — <strong>เรียนรู้แยกราย TCR</strong>
        เพราะ TCR แต่ละตัวจ้องคนละจุด</p>
      </div>
      <div class="card" style="border-left:3px solid var(--signal)">
        <div class="k">M · substitution distance</div>
        <p>ตารางเปิดค่า <strong>20×20 ช่อง</strong> บอกว่าเปลี่ยนกรดอะมิโน
        a → b ห่างแค่ไหน — <strong>นี่คือจุดที่งานเราเข้าไปแก้</strong></p>
      </div>
    </div>
  </div>
</section>

<!-- ==================================================== 4 · weakness == -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">03 · จุดอ่อน</div>
    <h2>ตาราง 400 ช่อง มีปัญหาเชิงโครงสร้าง 4 ข้อ</h2>
    <div class="grid g2">
      <div class="card"><div class="k">01 · กินข้อมูล</div>
        <div class="v" style="color:var(--signal)">~380</div>
        <p>พารามิเตอร์อิสระที่ต้องเรียนจากข้อมูล เสี่ยง <em class="term">overfit</em></p></div>
      <div class="card"><div class="k">02 · เดาของใหม่ไม่ได้</div>
        <div class="v" style="color:var(--signal)">0</div>
        <p>การเปลี่ยนแบบที่ไม่เคยเห็นในข้อมูล จะได้แค่ค่า prior —
        เปเปอร์ต้นทางยอมรับข้อนี้เอง</p></div>
      <div class="card"><div class="k">03 · ผูกกับ 20 ตัวเท่านั้น</div>
        <div class="v" style="color:var(--signal)">20/20</div>
        <p>กรดอะมิโนดัดแปลง (<em class="term">PTM</em>) เช่น phospho-Ser,
        citrulline — <strong>ไม่มีช่องให้ใส่เลย</strong></p></div>
      <div class="card"><div class="k">04 · อธิบายไม่ได้</div>
        <div class="v" style="color:var(--signal)">400</div>
        <p>ตัวเลข 400 ช่องบอกว่า <em>อันไหน</em> แพง แต่ไม่เคยบอกว่า
        <strong>ทำไม</strong></p></div>
    </div>
    <p class="lede" style="margin-top:4px">
      คำถามวิจัย: ถ้า <span class="mono">M</span> ไม่ใช่ตารางท่องจำ
      แต่เป็น<strong>ฟังก์ชันของคุณสมบัติทางเคมีจริง</strong> จะยังแม่นเท่าเดิมไหม
    </p>
  </div>
</section>

<!-- ==================================================== 4b · arch ====== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">03b · สถาปัตยกรรมโมเดล</div>
    <h2>ทั้งระบบ และกล่องเดียวที่งานนี้เข้าไปเปลี่ยน</h2>
    <figure class="figure" style="--fig-max:58vh">
      <img src="__FIGARCH__" alt="Model architecture from two peptides to a probability, and the four ways to define the substitution distance">
      <figcaption>
        <strong>a</strong> peptide คู่หนึ่ง → ระยะเคมีรายตำแหน่ง → ถ่วงน้ำหนักตำแหน่ง →
        รวมเป็นระยะ d → ordered logistic → ความน่าจะเป็น 3 ระดับ ·
        <strong>b</strong> ทั้ง 4 โมเดลต่างกัน<strong>เฉพาะกล่องสีส้ม</strong>
        ที่เหลือเหมือนกันหมด — ผลต่างจึงมาจาก representation ล้วน ๆ
      </figcaption>
    </figure>
  </div>
</section>

<!-- ==================================================== 5 · idea ======= -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">04 · ไอเดีย</div>
    <h2>เลิกท่องจำ แล้วหันไป<span style="color:var(--atom)">วัดโมเลกุลจริง</span></h2>
    <div class="eq">
      <span class="hl">M</span>[a,b] &nbsp;=&nbsp; Σ<sub>k</sub> &nbsp;θ<sub>k</sub> · | <span class="hl2">φ<sub>k</sub>(a)</span> − <span class="hl2">φ<sub>k</sub>(b)</span> | &nbsp;&nbsp;<span class="cmt">, θ ≥ 0</span><br>
      <span class="cmt">                ↑ น้ำหนัก    ↑ ค่าคุณสมบัติเคมีของ side chain</span>
    </div>
    <p class="lede">
      แทนที่จะเก็บ 400 ช่อง เราวัดกรดอะมิโนแต่ละตัวด้วย
      <strong>ไม้บรรทัดทางเคมี 8 อัน</strong> แล้วให้ระยะห่างเป็นผลรวมถ่วงน้ำหนัก
      ของความต่าง — คำนวณจากโครงสร้างโมเลกุลจริงด้วย <em class="term">RDKit</em>
      (SMILES → descriptors) แล้วลบค่าของ glycine ออกเพื่อเหลือเฉพาะ side chain
    </p>
    <div class="tw">
      <table>
        <tr><th>ไม้บรรทัด</th><th>วัดอะไร</th><th>สุดขั้ว</th>
            <th>ไม้บรรทัด</th><th>วัดอะไร</th><th>สุดขั้ว</th></tr>
        <tr><td class="mono">heavy</td><td>ขนาด / ความเทอะทะ</td><td class="mono">G=0 · W=10</td>
            <td class="mono">HBD/HBA</td><td>พันธะไฮโดรเจน</td><td class="mono">R: HBD=3</td></tr>
        <tr><td class="mono">polar</td><td>ความมีขั้ว (N+O)</td><td class="mono">L=0 · R=3</td>
            <td class="mono">rotB</td><td>ความยืดหยุ่น</td><td class="mono">G=0 · R=4</td></tr>
        <tr><td class="mono">aromatic</td><td>วงแหวน π-stacking</td><td class="mono">W=9 · F=6</td>
            <td class="mono">charge</td><td>ประจุที่ pH 7</td><td class="mono">D,E=−1 · K,R=+1</td></tr>
        <tr><td class="mono">S</td><td>กำมะถัน</td><td class="mono">เฉพาะ C, M</td>
            <td colspan="3" style="color:var(--muted)">รวม <strong>8 ตัว</strong> → θ 8 ค่า แทน 380</td></tr>
      </table>
    </div>
  </div>
</section>

<!-- ==================================================== 6 · free ======= -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">05 · ได้อะไรฟรีจากรูปแบบนี้</div>
    <h2>คุณสมบัติที่ตารางต้องบังคับ แต่สูตรนี้ได้มาเอง</h2>
    <div class="grid g2">
      <div class="card">
        <div class="k">คณิตศาสตร์แถมมาให้</div>
        <p style="line-height:1.9">
          <span class="mono" style="color:var(--accent)">M[a,a] = 0</span> — ไม่เปลี่ยน = ไม่มีระยะ<br>
          <span class="mono" style="color:var(--accent)">M ≥ 0</span> — เพราะบังคับ θ ≥ 0<br>
          <span class="mono" style="color:var(--accent)">M[a,b] = M[b,a]</span> — สมมาตร<br>
          <span class="mono" style="color:var(--accent)">triangle inequality</span> — เป็น metric จริง
        </p>
        <p class="tiny">ตาราง 20×20 ที่เรียนรู้แบบอิสระ ไม่รับประกันข้อไหนเลย
          ต้องไปบังคับทีหลัง</p>
      </div>
      <div class="card">
        <div class="k">ประโยชน์เชิงปฏิบัติ</div>
        <p style="line-height:1.9">
          <strong style="color:var(--atom)">ตีความได้</strong> — θ บอกตรง ๆ ว่าเคมีแกนไหนสำคัญ<br>
          <strong style="color:var(--atom)">เดาของใหม่ได้</strong> — interpolate ใน feature space<br>
          <strong style="color:var(--atom)">ใส่ residue นอกมาตรฐานได้</strong> — แค่มี SMILES<br>
          <strong style="color:var(--atom)">พังแล้ววินิจฉัยได้</strong> — เช็ค condition number ได้
        </p>
        <p class="tiny">ข้อสุดท้ายเจอจริง: feature ชุดหนึ่งทำ ADVI ระเบิดเป็น NaN
          ตรวจแล้วพบ collinearity (r=0.99) แก้ตรงจุดได้</p>
      </div>
    </div>
    <p class="lede">
      แต่ “สวยเชิงโครงสร้าง” ไม่ได้แปลว่า “ทำนายแม่นกว่า” —
      <strong>ต้องวัดกันจริง</strong> และนั่นคือส่วนที่เหลือของงานนี้
    </p>
  </div>
</section>

<!-- ==================================================== 7 · method ===== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">06 · วิธีวิเคราะห์</div>
    <h2>วัดยังไงไม่ให้หลอกตัวเอง</h2>
    <div class="grid g2">
      <div class="rail atom">
        <h3>หน่วยวัด = 1 TCR ไม่ใช่ 1 แถว</h3>
        <p style="margin-top:6px">คิด <em class="term">mean pairwise AUC</em> แยกราย TCR
        → ได้ 1 ตัวเลขต่อ TCR ทำให้ใช้ <strong>สถิติแบบจับคู่</strong>
        (<em class="term">paired Wilcoxon</em>) ได้ถูกต้อง</p>
      </div>
      <div class="rail warn">
        <h3>กับดักที่เจอจริง</h3>
        <p style="margin-top:6px">ถ้า pool ทุก TCR รวมกันโดยไม่มี intercept ราย TCR
        → AUC ออกมา <strong class="mono">0.31–0.39</strong> <em>แย่กว่าเดาสุ่ม</em>
        ทั้งที่โมเดลไม่ได้ผิด เป็น artifact ล้วน ๆ</p>
      </div>
    </div>
    <div class="grid g3">
      <div class="card"><div class="k">สถานการณ์ที่ 1</div><h3>In-distribution</h3>
        <p><em class="term">5-fold CV</em> — เจอเคมีแบบเดิมที่เคยเห็นแล้ว</p></div>
      <div class="card"><div class="k">สถานการณ์ที่ 2</div><h3>Out-of-distribution</h3>
        <p><em class="term">leave-chemistry-out</em> — ตัดการเปลี่ยนไปเป็นกลุ่มเคมีหนึ่ง
        (aromatic / charged / aliphatic / small) ออกจาก training ทั้งกลุ่ม</p></div>
      <div class="card"><div class="k">กันการหลอกตัวเอง</div><h3>ความเข้มงวด</h3>
        <p>bootstrap CI · รายงาน <strong>effect size</strong> คู่ p เสมอ ·
        แก้ multiplicity <strong>ครั้งเดียวทั้ง 12 การทดสอบ</strong> ·
        เทียบ ADVI กับ NUTS</p></div>
    </div>
    <p class="tiny">
      และมี <strong>null baseline ที่ไม่เรียนรู้อะไรเลย</strong> ไว้เทียบเสมอ:
      Hamming distance = 0.510 · BLOSUM100 น้ำหนักเท่ากัน = 0.559 ·
      โมเดลที่ fit แล้ว = 0.796–0.854 → แปลว่างานนี้เล่นอยู่ในช่วงกำไรที่เหลือเท่านั้น
    </p>
  </div>
</section>

<!-- ==================================================== 8 · bench ====== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">07 · ผลลัพธ์ · ภาพรวม</div>
    <h2>ผลการเทียบทั้ง 5 แบบ บน 151 TCR</h2>
    <figure class="figure">
      <img src="__FIG2__" alt="Benchmark: mean per-TCR AUC in-distribution and out-of-distribution for five representations, with paired effect sizes">
    </figure>
    <div class="grid g3">
      <div class="verdict yes"><div class="mark">✓</div><p>
        <strong>atomic ชนะ fixed BLOSUM100</strong> และชนะ
        <strong>Atchley-5</strong> ซึ่งเป็น prior art โดยตรง (pTEAM ใช้อยู่)</p></div>
      <div class="verdict no"><div class="mark">✕</div><p>
        <strong>atomic แพ้ learned matrix</strong> ในสถานการณ์ปกติ
        ด้วย effect ขนาดใหญ่ (<span class="mono">d=0.83</span>, ชนะ 86% ของ TCR)</p></div>
      <div class="verdict neu"><div class="mark">→</div><p>
        ฝั่ง OOD ทุกโมเดลตกลงมาใกล้กันหมด — <strong>ช่องว่างแคบกว่าที่คิด</strong></p></div>
    </div>
  </div>
</section>

<!-- ==================================================== 9 · refuted === -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">08 · ผลลัพธ์ · สิ่งที่ไม่จริง</div>
    <h2>ข้ออ้างตั้งต้นของเรา <span style="color:var(--signal)">ไม่รอด</span></h2>
    <p class="lede">
      เราตั้งใจจะแสดงว่า atomic representation <strong>แทน</strong> learned matrix ได้
      ข้อมูลบอกว่าไม่ใช่ — และเรารายงานตามนั้น
    </p>
    <div class="grid g2">
      <div class="card" style="border-left:3px solid var(--signal)">
        <div class="k">หลักฐานฝั่งตรงข้ามแข็งกว่า</div>
        <p style="line-height:1.85">
          learned ชนะ in-distribution &nbsp;<span class="mono">d = 0.83</span><br>
          learned ชนะบน TCR ที่ไม่เคยเห็น &nbsp;<span class="mono">0.723 vs 0.696</span><br>
          atomic ชนะ OOD แต่แค่ &nbsp;<span class="mono">d = 0.11</span> · ชนะ 50.9%
        </p>
      </div>
      <div class="card" style="border-left:3px solid var(--signal)">
        <div class="k">แล้ววิเคราะห์ซ้ำช่วยได้ไหม</div>
        <p style="line-height:1.85">
          ต้องใช้ TCR เพื่อยืนยัน <span class="mono">d=0.11–0.18</span>:<br>
          ที่ α=0.05 &nbsp;→&nbsp; <strong class="mono">~243</strong><br>
          หลังแก้ multiplicity &nbsp;→&nbsp; <strong class="mono">~425</strong><br>
          <span style="color:var(--signal)">มีอยู่จริงทั้งวงการ</span> &nbsp;→&nbsp;
          <strong class="mono" style="color:var(--signal)">151</strong>
        </p>
      </div>
    </div>
    <div class="rail warn">
      <p><strong>ไม่มีทางลัด</strong> — effect นี้ทำซ้ำได้จริง (ทดสอบ 5 seed
      ทิศทางไม่เคยกลับ) แต่เล็กเกินกว่าจะยืนยันด้วยข้อมูลที่โลกมีอยู่
      ต้องรอ mutational scan ชุดใหม่เท่านั้น</p>
    </div>
  </div>
</section>

<!-- ==================================================== 10 · hybrid ==== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">09 · ผลลัพธ์ · สิ่งที่ได้จริง</div>
    <h2><span style="color:var(--accent)">Frozen-backbone hybrid</span> — ได้ทั้งสองอย่าง</h2>
    <p class="lede">
      atomic มีวินัยแต่ความจุน้อย · matrix มีความจุแต่เดาของใหม่ไม่ได้ →
      <strong>ตรึงโครงเคมีไว้ แล้วเรียนเฉพาะส่วนต่างที่ถูกบีบให้เล็ก</strong>
    </p>
    <div class="grid g2 g2w" style="align-items:start">
      <figure class="figure">
        <img src="__FIG3__" alt="Pareto plane, per-TCR in-distribution gain, and absence of out-of-distribution cost">
      </figure>
      <div style="display:flex; flex-direction:column; gap:12px">
        <div class="card" style="border-left:3px solid var(--accent)">
          <div class="k">ผลหลักของงานนี้</div>
          <p style="line-height:1.9">
            in-distribution &nbsp;<span class="mono">0.818 → 0.847</span><br>
            ดีขึ้นใน <strong class="mono">88.7%</strong> ของ TCR<br>
            <span class="mono">Cohen's d = 0.93</span> ·
            <span class="mono">p = 8×10⁻²³</span><br>
            OOD เสีย <strong class="mono">−0.0005</strong>
            (<span class="mono">p = 0.70</span> = ไม่ต่าง)
          </p>
          <p class="tiny">รอดทุกการแก้ multiplicity รวม Bonferroni</p>
        </div>
        <div class="rail">
          <h3>ทำไมถึงได้ฟรี</h3>
          <p style="margin-top:6px">พอเจอการเปลี่ยนที่ไม่เคยเห็น ส่วนต่างจะถูกบีบเข้าใกล้ 0
          ระยะทางก็<strong>ยุบกลับไปเท่ากับ atomic เป๊ะ</strong> — AUC เป็นการจัดอันดับ
          จึงตกต่ำกว่าเดิมไม่ได้<strong>โดยโครงสร้าง</strong> ไม่ใช่โดยบังเอิญ</p>
        </div>
      </div>
    </div>
    <p class="tiny">
      ⚠️ แต่ hybrid <strong>ยังไม่ล้ม learned matrix</strong> —
      ยังตามอยู่ <span class="mono">−0.0073</span> in-distribution
      (<span class="mono">p=1.2×10⁻⁴</span>) เราพูดตามนั้น
    </p>
  </div>
</section>

<!-- ==================================================== 11 · freeze ==== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">10 · กลไก</div>
    <h2>“การตรึง” คือหัวใจ ไม่ใช่การจูนพารามิเตอร์</h2>
    <p class="lede">ข้อโต้แย้งที่ต้องตอบ: หรือแค่เลือกค่าบีบ
      <span class="mono">σ</span> ดี ๆ ก็ได้ผลเท่ากัน? — เรากวาด σ ทั้งช่วงเพื่อตอบ</p>
    <figure class="figure mid">
      <img src="__FIG4__" alt="Shrinkage sweep showing the jointly fitted hybrid loses out-of-distribution accuracy at every sigma while the frozen variant does not">
      <figcaption>แบบ <strong>joint</strong> ยิ่งเพิ่ม σ ยิ่งได้ in-distribution
        แต่ <strong>เสีย OOD ทุกค่า</strong> (Spearman ρ = −0.80) ·
        ดาว = แบบ <strong>frozen</strong> ที่ไม่เสียเลย</figcaption>
    </figure>
    <div class="path">
      <div class="step"><span class="n">ล้มครั้งที่ 1</span>
        <span class="t">base × (1+δ)</span>
        <span class="w">ADVI ระเบิด — θ กับ δ non-identifiable</span></div>
      <div class="step"><span class="n">ล้มครั้งที่ 2</span>
        <span class="t">base + δ · joint</span>
        <span class="w">ส่วนต่างดูดสัญญาณจาก θ → OOD ตก</span></div>
      <div class="step"><span class="n">ล้มครั้งที่ 3</span>
        <span class="t">ตรึง θ · ปล่อย w</span>
        <span class="w">w ที่เรียนใหม่ไม่เข้าคู่กับโครงที่ตรึง</span></div>
      <div class="step ok"><span class="n">สำเร็จ</span>
        <span class="t">ตรึง θ และ w</span>
        <span class="w">δ→0 บนเคมีใหม่ → ยุบกลับเป็น atomic</span></div>
    </div>
  </div>
</section>

<!-- ==================================================== 12 · negative == -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">11 · ผลลบ 3 ข้อ</div>
    <h2>สิ่งที่<span style="color:var(--signal)">ไม่ได้ผล</span> — และทำไมถึงต้องรายงาน</h2>
    <div class="grid g3">
      <div class="card">
        <div class="k">01 · pMHC term</div>
        <p>เติมข้อมูลการจับ MHC (NetMHCpan) เข้าโมเดล
        <strong>ไม่ช่วยเลย</strong> <span class="mono">p = 0.91</span></p>
        <p class="tiny">แปลว่า สัญญาณ MHC ถูกดูดซับไปแล้วโดยการวัดเทียบกับ index peptide</p>
      </div>
      <div class="card">
        <div class="k">02 · ระดับโปรตีโอม</div>
        <p>ค้นเป้าหมายจาก <strong>259,312 peptide</strong> ได้ 5 ใน 5 อันดับแรก
        <span class="mono">p = 6×10⁻²⁵</span> — ดูน่าตื่นเต้นมาก</p>
        <p class="tiny" style="color:var(--signal)"><strong>แต่ Hamming distance
        ที่ไม่เรียนรู้อะไรเลย ทำได้เท่ากัน</strong> → โจทย์นี้แยกความสามารถโมเดลไม่ได้</p>
      </div>
      <div class="card">
        <div class="k">03 · การทดสอบเคมีที่ตั้งไว้ล่วงหน้า</div>
        <p>เราประกาศก่อนรันว่า citrulline ควรใกล้ <span class="mono">Q</span> ที่สุด
        → ผลออกมาเป็น <span class="mono" style="color:var(--signal)">R</span></p>
        <p class="tiny"><strong>บันทึกว่า FAIL ตามที่ประกาศไว้</strong>
        (เหตุผล: citrulline isosteric กับ arginine — Q ใกล้สุดเฉพาะเมื่อไม่นับ parent)</p>
      </div>
    </div>
    <div class="rail warn">
      <p><strong>ทำไมข้อ 02 สำคัญที่สุด:</strong> ถ้าไม่รัน null baseline ตัวเลข
      <span class="mono">p = 6×10⁻²⁵</span> ชุดเดียวกัน จะถูกใช้อ้างว่าโมเดลเราเก่ง
      ทั้งที่วิธีนับตำแหน่งที่ต่างกันเฉย ๆ ก็ทำได้เท่ากัน →
      <strong>คอขวดจริงอยู่ที่ MHC presentation ไม่ใช่ substitution model</strong></p>
    </div>
  </div>
</section>

<!-- ==================================================== 13 · ptm ======= -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">12 · ความสามารถที่ตารางทำไม่ได้เลย</div>
    <h2>ให้คะแนนกรดอะมิโนที่โมเดล<span style="color:var(--atom)">ไม่เคยเห็น</span></h2>
    <p class="lede">
      ตาราง 20×20 ไม่มีแถวสำหรับ phospho-Ser — แต่โมเดลเราขอแค่โครงสร้างโมเลกุล
      ก็ให้ระยะได้ทันที <strong>โดยไม่ต้องเทรนใหม่</strong>
    </p>
    <figure class="figure tall">
      <img src="__FIG7__" alt="Distances from twelve modified residues to the canonical twenty, and the chemical cost of each modification">
      <figcaption>
        12 residue ดัดแปลง — phospho-Ser/Thr/Tyr, citrulline, methyl/acetyl-Lys,
        hydroxyproline, nitro-Tyr, selenocysteine ฯลฯ ·
        ○ = ตัวที่ใกล้ที่สุด · ■ = ตัวต้นทาง
      </figcaption>
    </figure>
    <div class="grid g2">
      <div class="verdict neu"><div class="mark">!</div><p>
        <strong>นี่คือการสาธิตความสามารถ ไม่ใช่การพิสูจน์ความแม่น</strong> —
        ยังไม่มี mutational scan ชุดไหนในโลกที่มี residue ดัดแปลง</p></div>
      <div class="verdict yes"><div class="mark">✓</div><p>
        แต่รอบนี้<strong>เจอข้อมูลที่ทดสอบได้แล้ว</strong> — ดูสไลด์ถัดไป</p></div>
    </div>
  </div>
</section>

<!-- ==================================================== 14 · data ====== -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">13 · แหล่งข้อมูลใหม่ · สำรวจ ส.ค. 2026</div>
    <h2>หาข้อมูลเพิ่มได้แค่ไหน</h2>
    <div class="tw">
      <table>
        <tr><th>แหล่ง</th><th>ได้อะไร</th><th>ใช้ได้ไหม</th></tr>
        <tr>
          <td><strong>Malone 2025</strong><br><span class="tiny">Nat Commun · SARS-CoV-2 YLQ</span></td>
          <td>21 TCR × 172 mutant · scan ครบสมบูรณ์<br>
            <span class="tiny">ตรวจแล้ว: <span class="mono">YLQPRTFLL</span> ยังไม่มีใน BATCAVE</span></td>
          <td><span style="color:var(--prior)">◐ ได้ แต่มีเงื่อนไข</span><br>
            <span class="tiny">วัด <strong>binding</strong> ไม่ใช่ activation · ต้อง discretize เอง</span></td>
        </tr>
        <tr>
          <td><strong>Phosphopeptide neoantigen</strong><br><span class="tiny">Nat Commun 2023</span></td>
          <td>134 peptide · มี <strong>phosphomimetics</strong> (D, E) เทียบกับ pSer จริง</td>
          <td><span style="color:var(--accent)">✓ คุ้มที่สุด</span><br>
            <span class="tiny">ทดสอบคำทำนาย pSer↔E/D ของเราได้ <strong>ตรง ๆ</strong></span></td>
        </tr>
        <tr>
          <td><strong>Citrullinated tenascin-C</strong><br><span class="tiny">HLA-DR4</span></td>
          <td>4 peptide variant + SPR/tetramer</td>
          <td><span style="color:var(--muted)">◔ anecdotal</span><br>
            <span class="tiny">n=4 แต่เป็นข้อมูล citrulline ที่ดีที่สุดที่มี</span></td>
        </tr>
        <tr>
          <td><strong>Deep peptide recognition profiling</strong><br><span class="tiny">Nat Biotech 2026</span></td>
          <td>peptide หลายล้านตัวต่อ TCR</td>
          <td><span style="color:var(--signal)">✕ ผิดประเภท</span><br>
            <span class="tiny">yeast display = binding · ไม่ยึด index peptide</span></td>
        </tr>
      </table>
    </div>
    <div class="rail warn">
      <p><strong>ข้อสรุปที่ซื่อสัตย์:</strong> ของใหม่ที่เจอ
      <strong>ไม่ได้แก้ปัญหากำลังทางสถิติ</strong> (151 → 172 ยังห่างจาก 425 มาก)
      แต่<strong>แก้ข้อจำกัดเรื่อง PTM ได้จริง</strong> — เปลี่ยนจาก
      “ข้ออ้างที่ทดสอบไม่ได้” เป็น “ข้ออ้างที่มีข้อมูลรออยู่แล้ว”</p>
    </div>
  </div>
</section>

<!-- ==================================================== 15 · summary === -->
<section class="slide">
  <div class="inner">
    <div class="eyebrow">14 · สรุป</div>
    <h2>งานนี้ได้อะไรมาบ้าง</h2>
    <div class="grid g2">
      <div style="display:flex; flex-direction:column; gap:11px">
        <h3 style="color:var(--accent)">✓ อ้างได้</h3>
        <div class="verdict yes"><div class="mark">1</div><p>
          <strong>frozen-backbone hybrid</strong> ดีกว่า atomic อย่างมาก
          (<span class="mono">d=0.93</span>, 88.7% ของ TCR) <strong>โดยไม่เสีย OOD</strong>
          — รอดทุก correction</p></div>
        <div class="verdict yes"><div class="mark">2</div><p>
          <strong>การตรึง backbone คือกลไกที่จำเป็น</strong> — พิสูจน์ด้วย sweep
          ว่าแบบ joint เสีย OOD ทุกค่า σ</p></div>
        <div class="verdict yes"><div class="mark">3</div><p>
          atomic ชนะ <strong>fixed BLOSUM100</strong> และ <strong>Atchley-5</strong>
          (prior art) แม้ effect เล็ก</p></div>
      </div>
      <div style="display:flex; flex-direction:column; gap:11px">
        <h3 style="color:var(--signal)">✕ อ้างไม่ได้</h3>
        <div class="verdict no"><div class="mark">1</div><p>
          atomic <strong>แทน</strong> learned matrix ไม่ได้ — ถูกหักล้างชัดเจน</p></div>
        <div class="verdict no"><div class="mark">2</div><p>
          “atomic generalize ดีกว่า” — effect จริงแต่เล็กเกินกว่าจะยืนยันที่ n=151</p></div>
        <div class="verdict no"><div class="mark">3</div><p>
          “ใช้กับ PTM ได้” — สาธิต<strong>ความสามารถ</strong>ได้ แต่ยังไม่มี
          <strong>ความแม่น</strong> และการทดสอบที่ตั้งไว้ล่วงหน้าไม่ผ่าน</p></div>
      </div>
    </div>
    <div class="rail">
      <h3>ถ้ามีงบจำกัด ควรลงตรงไหน</h3>
      <p style="margin-top:6px">
        ผลของงานนี้ชี้ว่า <strong>อย่าเสียเวลาปรับ substitution distance ต่อ</strong>
        (ส่วนนั้นอิ่มตัวแล้ว) — ให้ไปที่ <strong>สร้าง mutational scan ชุดใหม่</strong>
        และ <strong>ปรับปรุงการทำนาย MHC-II presentation</strong> ซึ่งเป็นคอขวดจริง
      </p>
    </div>
    <p class="tiny">
      แนวคิด <em>“ตรึงโครงเชิงกลไกที่พารามิเตอร์น้อย แล้วเสริมด้วย residual
      พารามิเตอร์เยอะที่ถูกบีบ”</em> ไม่ผูกกับชีววิทยา TCR เลย —
      น่าจะใช้ได้กับปัญหาอื่นที่มีโครงสร้างแบบเดียวกัน
    </p>
  </div>
</section>

</div>

<nav class="rail-nav" id="rail" aria-label="ไปยังสไลด์"></nav>
<div class="hud"><span id="pos">01</span><span style="opacity:.5">/</span><span id="tot">17</span><span style="opacity:.5">·</span><span>↑ ↓ เลื่อน</span></div>

<script>
(function(){
  var deck   = document.getElementById('deck');
  var slides = Array.prototype.slice.call(deck.querySelectorAll('.slide'));
  var rail   = document.getElementById('rail');
  var pos    = document.getElementById('pos');
  document.getElementById('tot').textContent = String(slides.length).padStart(2,'0');

  slides.forEach(function(s,i){
    s.id = 'slide-'+i;
    var a = document.createElement('a');
    a.href = '#slide-'+i;
    a.setAttribute('aria-label','สไลด์ '+(i+1));
    rail.appendChild(a);
  });
  var dots = Array.prototype.slice.call(rail.children);

  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(!e.isIntersecting) return;
      var i = slides.indexOf(e.target);
      dots.forEach(function(d,j){ d.classList.toggle('on', j===i); });
      pos.textContent = String(i+1).padStart(2,'0');
    });
  },{threshold:.55});
  slides.forEach(function(s){ io.observe(s); });

  function go(dir){
    var i = dots.findIndex(function(d){ return d.classList.contains('on'); });
    var n = Math.min(slides.length-1, Math.max(0, (i<0?0:i)+dir));
    slides[n].scrollIntoView({behavior:'smooth', block:'start'});
  }
  document.addEventListener('keydown', function(e){
    if(e.key==='ArrowDown'||e.key==='PageDown'||e.key===' '){ e.preventDefault(); go(1); }
    if(e.key==='ArrowUp'  ||e.key==='PageUp'){ e.preventDefault(); go(-1); }
    if(e.key==='Home'){ e.preventDefault(); slides[0].scrollIntoView({behavior:'smooth'}); }
    if(e.key==='End'){ e.preventDefault(); slides[slides.length-1].scrollIntoView({behavior:'smooth'}); }
  });
})();
</script>
"""

FIGS = {
    "__FIGBIO__": "fig1_overview.png",
    "__FIGARCH__": "fig2_architecture.png",
    "__FIG2__": "fig4_benchmark.png",
    "__FIG3__": "fig5_hybrid_pareto.png",
    "__FIG4__": "fig6_shrinkage.png",
    "__FIG7__": "fig9_noncanonical.png",
}


def main():
    html = HTML
    for key, name in FIGS.items():
        html = html.replace(key, data_uri(name))
    with open(OUT, "w") as fh:
        fh.write(html)
    kb = os.path.getsize(OUT) / 1024
    print(f"wrote {OUT}  ({kb:,.0f} KB, {len(FIGS)} figures inlined)")
    import re as _re
    left = _re.findall(r"__FIG[A-Z0-9]*__", html)
    assert not left, f"unreplaced placeholders: {sorted(set(left))}"
    print(f"all placeholders replaced ({len(FIGS)} figures)")


if __name__ == "__main__":
    main()
