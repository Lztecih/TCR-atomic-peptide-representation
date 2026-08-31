"""
build_talks.py
==============
Builds two audience-specific talk decks from the same project, each with a
toggleable speaker script under every slide:

    TALK_PUBLIC.html    general audience, no biology or maths assumed (~9 min)
    TALK_CLINICAL.html  clinicians: TCR-T safety, neoantigen selection (~14 min)

The research deck (SLIDES.html) stays as the specialist version.

Usage:  python3 build_talks.py
"""

from __future__ import annotations

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "figures")


def data_uri(name: str) -> str:
    with open(os.path.join(FIG, name), "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()


# ===========================================================================
CSS = r"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;600&family=Noto+Sans+Thai:wght@400;600;700&family=Noto+Serif+Thai:wght@400;600&display=swap">
<style>
:root{
  --paper:#F7F9F8; --surface:#FFFFFF; --ink:#10171A; --ink-2:#33403D;
  --muted:#6B7B78; --line:#D8E0DD; --line-2:#EAF0EE;
  --atom:#0072B2; --signal:#D55E00; --accent:#009E73; --prior:#E69F00;
  --null:#CC79A7; --note-bg:#F1F5F3;
  --shadow:0 1px 2px rgba(16,23,26,.05),0 8px 24px -12px rgba(16,23,26,.18);
  --display:"Archivo","Noto Sans Thai",system-ui,sans-serif;
  --body:"Source Serif 4","Noto Serif Thai",Georgia,serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0E1416; --surface:#161F21; --ink:#EAF2EF; --ink-2:#BCCBC7;
    --muted:#8B9C98; --line:#2A3639; --line-2:#202B2D; --note-bg:#141E20;
    --atom:#4FA8DC; --signal:#F08A45; --accent:#3FC7A0; --prior:#F0BE55;
    --null:#DB9CC0;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --paper:#0E1416; --surface:#161F21; --ink:#EAF2EF; --ink-2:#BCCBC7;
  --muted:#8B9C98; --line:#2A3639; --line-2:#202B2D; --note-bg:#141E20;
  --atom:#4FA8DC; --signal:#F08A45; --accent:#3FC7A0; --prior:#F0BE55;
  --null:#DB9CC0;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--body); font-size:17px; line-height:1.62;
  -webkit-font-smoothing:antialiased}

.deck{height:100dvh; overflow-y:auto; scroll-snap-type:y mandatory; scroll-behavior:smooth}
.slide{min-height:100dvh; scroll-snap-align:start; scroll-snap-stop:always;
  display:flex; align-items:center; justify-content:center;
  padding:clamp(26px,4vw,56px) clamp(20px,5vw,80px) clamp(56px,6vw,80px);
  border-bottom:1px solid var(--line-2)}
.inner{width:min(1080px,100%); display:flex; flex-direction:column;
  gap:clamp(14px,1.8vw,24px)}

/* speaker-script mode: let slides grow, drop the snapping */
body.speaking .deck{scroll-snap-type:none}
body.speaking .slide{min-height:auto; scroll-snap-align:none;
  padding-top:clamp(34px,4vw,56px); padding-bottom:clamp(34px,4vw,56px)}
.notes{display:none}
body.speaking .notes{display:block}
.notes{
  background:var(--note-bg); border-left:3px solid var(--atom);
  border-radius:0 8px 8px 0; padding:14px 18px; margin-top:4px;
}
.notes .lbl{font-family:var(--mono); font-size:10.5px; letter-spacing:.15em;
  text-transform:uppercase; color:var(--muted); display:block; margin-bottom:6px}
.notes p{font-size:15.5px; line-height:1.72; color:var(--ink-2); max-width:78ch}
.notes p + p{margin-top:9px}
.notes .beat{color:var(--muted); font-style:italic}

.eyebrow{font-family:var(--mono); font-size:11.5px; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  display:flex; align-items:center; gap:10px}
.eyebrow::before{content:""; width:26px; height:2px; background:currentColor; opacity:.55}
h1{font-family:var(--display); font-weight:800;
  font-size:clamp(36px,5.6vw,72px); line-height:1.03; letter-spacing:-.024em;
  margin:0; text-wrap:balance}
h2{font-family:var(--display); font-weight:700;
  font-size:clamp(26px,3.4vw,42px); line-height:1.13; letter-spacing:-.018em;
  margin:0; text-wrap:balance}
h3{font-family:var(--display); font-weight:600; font-size:clamp(15px,1.5vw,18px);
  margin:0; letter-spacing:-.005em}
p{margin:0; max-width:68ch}
.lede{font-size:clamp(17px,1.8vw,21px); color:var(--ink-2); line-height:1.58}
.big{font-family:var(--display); font-weight:800;
  font-size:clamp(30px,4.4vw,58px); line-height:1.05; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.tiny{font-size:13px; color:var(--muted); line-height:1.5}
strong{font-weight:600; color:var(--ink)}
.mono{font-family:var(--mono)}
em.term{font-style:normal; font-family:var(--mono); font-size:.86em;
  color:var(--muted); white-space:nowrap}

.grid{display:grid; gap:clamp(12px,1.5vw,20px)}
.g2{grid-template-columns:repeat(2,1fr)} .g3{grid-template-columns:repeat(3,1fr)}
.g2w{grid-template-columns:1.3fr 1fr}
@media(max-width:860px){.g2,.g3,.g2w{grid-template-columns:1fr}}

.card{background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:clamp(14px,1.6vw,20px); display:flex; flex-direction:column; gap:7px;
  box-shadow:var(--shadow)}
.card .k{font-family:var(--mono); font-size:11px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--muted)}
.card .v{font-family:var(--display); font-weight:700;
  font-size:clamp(22px,2.6vw,32px); line-height:1; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.card p{font-size:14.5px; line-height:1.5; color:var(--ink-2)}

.rail{border-left:3px solid var(--accent); padding-left:16px}
.rail.warn{border-color:var(--signal)} .rail.atom{border-color:var(--atom)}
.rail.quiet{border-color:var(--line)}

table{border-collapse:collapse; width:100%; font-size:14.5px}
th,td{text-align:left; padding:9px 12px; border-bottom:1px solid var(--line-2)}
th{font-family:var(--mono); font-size:11px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); font-weight:600;
  border-bottom:1px solid var(--line)}
td.num{font-family:var(--mono); font-variant-numeric:tabular-nums; text-align:right}
.tw{overflow-x:auto}

.figure{background:#FFFFFF; border:1px solid var(--line); border-radius:10px;
  padding:12px; box-shadow:var(--shadow); overflow:hidden;
  --on-figure:#33403D; --on-figure-strong:#10171A}
.figure img{width:100%; height:auto; display:block; border-radius:4px;
  max-height:var(--fig-max,38vh); object-fit:contain; margin:0 auto}
figcaption{font-size:12.5px; color:var(--on-figure); line-height:1.5;
  padding:10px 4px 2px}
figcaption strong{color:var(--on-figure-strong)}
body.speaking .figure img{max-height:none}

/* ---- peptide alignment, built for this subject ------------------------- */
.pep{display:flex; flex-direction:column; gap:10px; font-family:var(--mono)}
.pep .row{display:flex; align-items:center; gap:12px; flex-wrap:wrap}
.pep .lab{font-size:12px; color:var(--muted); width:190px; flex:none;
  line-height:1.35}
.pep .seq{display:flex; gap:5px}
.pep .aa{
  width:clamp(28px,3.1vw,40px); height:clamp(34px,3.6vw,46px);
  display:grid; place-items:center; border-radius:6px;
  border:1px solid var(--line); background:var(--surface);
  font-size:clamp(14px,1.6vw,19px); font-weight:600; color:var(--ink-2);
}
.pep .aa.same{opacity:.45}
.pep .aa.diff{
  background:var(--signal); border-color:var(--signal); color:#fff;
}
.pep .tick{font-size:11px; color:var(--muted); text-align:center;
  width:clamp(28px,3.1vw,40px)}

.rankbar{display:flex; flex-direction:column; gap:9px}
.rb{display:grid; grid-template-columns:132px 1fr 76px; align-items:center; gap:12px}
.rb .n{font-family:var(--mono); font-size:12.5px; color:var(--ink-2)}
.rb .track{display:block; height:12px; background:var(--line-2); border-radius:999px; overflow:hidden}
.rb .fill{display:block; height:100%; border-radius:999px; background:var(--muted)}
.rb .val{font-family:var(--mono); font-size:12.5px; text-align:right;
  font-variant-numeric:tabular-nums; color:var(--ink-2)}

.verdict{display:flex; gap:11px; align-items:flex-start}
.verdict .mark{font-family:var(--display); font-weight:800; font-size:15px;
  line-height:1.4; flex:none; width:22px}
.verdict p{font-size:14.5px; line-height:1.52}
.yes .mark{color:var(--accent)} .no .mark{color:var(--signal)}
.neu .mark{color:var(--muted)}

.rail-nav{position:fixed; right:clamp(10px,1.6vw,22px); top:50%;
  transform:translateY(-50%); display:flex; flex-direction:column; gap:9px; z-index:40}
.rail-nav a{width:9px; height:9px; border-radius:50%; background:var(--line);
  transition:background .18s,transform .18s}
.rail-nav a:hover{background:var(--muted); transform:scale(1.35)}
.rail-nav a.on{background:var(--accent); transform:scale(1.35)}
.rail-nav a:focus-visible{outline:2px solid var(--accent); outline-offset:3px}
@media(max-width:720px){.rail-nav{display:none}}
body.speaking .rail-nav{display:none}

.hud{position:fixed; left:clamp(14px,2vw,26px); bottom:clamp(12px,1.8vw,22px);
  font-family:var(--mono); font-size:11px; letter-spacing:.1em; color:var(--muted);
  z-index:40; display:flex; gap:12px; align-items:center;
  background:color-mix(in srgb,var(--paper) 88%,transparent);
  padding:5px 11px; border-radius:999px; border:1px solid var(--line);
  font-variant-numeric:tabular-nums}
.hud button{
  font:inherit; letter-spacing:.1em; color:var(--ink-2); background:none;
  border:1px solid var(--line); border-radius:999px; padding:3px 10px;
  cursor:pointer; text-transform:uppercase;
}
.hud button:hover{border-color:var(--accent); color:var(--accent)}
.hud button:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
body.speaking .hud button{background:var(--accent); border-color:var(--accent); color:#fff}
@media(prefers-reduced-motion:reduce){.deck{scroll-behavior:auto} *{transition:none!important}}
</style>
"""

JS = r"""
<script>
(function(){
  var deck=document.getElementById('deck');
  var slides=[].slice.call(deck.querySelectorAll('.slide'));
  var rail=document.getElementById('rail'), pos=document.getElementById('pos');
  document.getElementById('tot').textContent=String(slides.length).padStart(2,'0');
  slides.forEach(function(s,i){
    s.id='s'+i;
    var a=document.createElement('a'); a.href='#s'+i;
    a.setAttribute('aria-label','สไลด์ '+(i+1)); rail.appendChild(a);
  });
  var dots=[].slice.call(rail.children);
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(!e.isIntersecting) return;
      var i=slides.indexOf(e.target);
      dots.forEach(function(d,j){d.classList.toggle('on',j===i)});
      pos.textContent=String(i+1).padStart(2,'0');
    });
  },{threshold:.5});
  slides.forEach(function(s){io.observe(s)});

  function go(d){
    var i=dots.findIndex(function(x){return x.classList.contains('on')});
    var n=Math.min(slides.length-1,Math.max(0,(i<0?0:i)+d));
    slides[n].scrollIntoView({behavior:'smooth',block:'start'});
  }
  var btn=document.getElementById('notesBtn');
  function toggle(){
    // Slide heights change when the script panes appear, so remember which
    // slide we were on and restore it -- otherwise the reflow leaves the
    // viewport parked in blank space between slides.
    var i=dots.findIndex(function(x){return x.classList.contains('on')});
    if(i<0) i=0;
    document.body.classList.toggle('speaking');
    btn.setAttribute('aria-pressed',document.body.classList.contains('speaking'));
    requestAnimationFrame(function(){
      slides[i].scrollIntoView({behavior:'auto',block:'start'});
    });
  }
  btn.addEventListener('click',toggle);
  document.addEventListener('keydown',function(e){
    if(e.target.tagName==='BUTTON'&&e.key===' ')return;
    if(e.key==='ArrowDown'||e.key==='PageDown'){e.preventDefault();go(1)}
    if(e.key==='ArrowUp'||e.key==='PageUp'){e.preventDefault();go(-1)}
    if(e.key==='n'||e.key==='N'){e.preventDefault();toggle()}
  });
})();
</script>
"""


def shell(title, body):
    return (f"<title>{title}</title>\n" + CSS +
            '\n<div class="deck" id="deck">\n' + body +
            '\n</div>\n'
            '<nav class="rail-nav" id="rail" aria-label="ไปยังสไลด์"></nav>\n'
            '<div class="hud"><span id="pos">01</span>'
            '<span style="opacity:.5">/</span><span id="tot">00</span>'
            '<span style="opacity:.5">·</span><span>↑ ↓</span>'
            '<button id="notesBtn" aria-pressed="false">สคริปต์พูด · N</button></div>\n'
            + JS)


def note(*paras):
    inner = "".join(f"<p>{p}</p>" for p in paras)
    return f'<div class="notes"><span class="lbl">พูดว่า</span>{inner}</div>'


def slide(eyebrow, body, notes=""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    return f'<section class="slide"><div class="inner">{eb}{body}{notes}</div></section>\n'


# --- the peptide alignment, reused by both decks ---------------------------
MAGE, TITIN = "EVDPIGHLY", "ESDPIVAQY"


def alignment():
    def row(lab, seq, ref):
        cells = "".join(
            f'<span class="aa {"diff" if a != b else "same"}">{a}</span>'
            for a, b in zip(seq, ref))
        return (f'<div class="row"><span class="lab">{lab}</span>'
                f'<span class="seq">{cells}</span></div>')
    ticks = "".join(f'<span class="tick">{i+1}</span>' for i in range(9))
    return (
        '<div class="pep">'
        + row('<strong style="color:var(--accent)">MAGE-A3</strong> 168–176<br>'
              'เป้าหมายที่ตั้งใจ', MAGE, MAGE)
        + row('<strong style="color:var(--signal)">Titin</strong> 394–403<br>'
              'ในกล้ามเนื้อหัวใจ', TITIN, MAGE)
        + f'<div class="row"><span class="lab"></span>'
          f'<span class="seq">{ticks}</span></div>'
        + '</div>')


def rankbar(rows, worst=111):
    """Bar length is the rank itself, so a SHORT bar means the peptide was
    surfaced early. Drawing 1-rank instead makes every bar look nearly full
    (ranks 4-27 out of 111 all map to 76-97%) and hides the differences."""
    out = ['<div class="rankbar">',
           '<div class="rb"><span class="n"></span>'
           '<span class="tiny">← สั้นกว่า = เจอเร็วกว่า (จาก 111 ชิ้น)</span>'
           '<span></span></div>']
    for name, rank, color in rows:
        pct = max(2.5, 100 * rank / worst)
        out.append(
            f'<div class="rb"><span class="n">{name}</span>'
            f'<span class="track"><span class="fill" style="width:{pct:.1f}%;'
            f'background:{color}"></span></span>'
            f'<span class="val">อันดับ {rank}</span></div>')
    out.append('</div>')
    return "".join(out)


RANKS = [("atomic (งานนี้)", 4, "var(--atom)"),
         ("learned matrix", 7, "var(--signal)"),
         ("frozen hybrid", 10, "var(--accent)"),
         ("fixed BLOSUM100", 13, "var(--muted)"),
         ("Hamming (ไม่เรียนรู้)", 27, "var(--null)")]


# ===========================================================================
# DECK A -- general public
# ===========================================================================
def public_deck():
    s = []

    s.append(slide('เวอร์ชันคนทั่วไป · ประมาณ 9 นาที', """
      <h1>ร่างกายคุณมีระบบ<br><span style="color:var(--atom)">จดจำใบหน้า</span><br>ที่แม่นที่สุดในโลก</h1>
      <p class="lede">แล้ววันหนึ่งมันก็จำผิด — จนมีคนเสียชีวิต<br>
        นี่คือเรื่องของความพยายามทำนายความผิดพลาดนั้นล่วงหน้า</p>
      <p class="tiny">กด <strong>N</strong> หรือปุ่มมุมล่างซ้าย เพื่อดูสคริปต์พูด · ลูกศร ↑↓ เลื่อนสไลด์</p>
    """, note(
        "สวัสดีครับ วันนี้ผมจะเล่าเรื่องงานวิจัยที่ผมทำ แต่ขอเริ่มจากเรื่องที่ไม่ต้องรู้ชีววิทยาเลยก่อน",
        "ในร่างกายเรามีระบบจดจำใบหน้าอยู่ระบบหนึ่ง มันแม่นกว่าระบบใด ๆ ที่มนุษย์สร้างได้ ทำงานตลอด 24 ชั่วโมง ตรวจเซลล์เป็นล้าน ๆ ตัวทุกวินาที",
        "<span class='beat'>[เว้นจังหวะ]</span> แต่ปี 2013 มันจำผิด และมีคนตาย — เดี๋ยวผมจะเล่าให้ฟังว่าเกิดอะไรขึ้น")))

    s.append(slide('01 · ระบบยาม', """
      <h2>T cell คือยามที่เดินตรวจทุกเซลล์ในร่างกาย</h2>
      <div class="grid g2">
        <div class="rail atom">
          <h3>เซลล์ทุกตัวต้องยื่นบัตร</h3>
          <p style="margin-top:6px">เซลล์ทุกตัวในร่างกายจะหั่นโปรตีนข้างในตัวเองเป็นชิ้นเล็ก ๆ
          แล้ว<strong>ยกขึ้นมาโชว์บนผิว</strong> เหมือนยื่นบัตรประชาชนให้ยามตรวจ</p>
        </div>
        <div class="rail">
          <h3>ยามจำได้แค่หน้าเดียว</h3>
          <p style="margin-top:6px">T cell แต่ละตัวถูกฝึกให้จำ<strong>ชิ้นเดียว</strong>
          ถ้าเจอชิ้นที่ตรงกับที่จำได้ → สั่งทำลายเซลล์นั้นทันที</p>
        </div>
      </div>
      <p class="lede">นี่คือวิธีที่ร่างกายกำจัดเซลล์ติดเชื้อและเซลล์มะเร็ง —
        โดยไม่ไปยุ่งกับเซลล์ปกติ</p>
    """, note(
        "ระบบทำงานแบบนี้ครับ เซลล์ทุกตัวในร่างกาย ไม่ว่าจะเซลล์ผิวหนัง เซลล์ตับ เซลล์หัวใจ จะหั่นโปรตีนที่อยู่ข้างในตัวเองออกมาเป็นชิ้นเล็ก ๆ แล้วยกขึ้นมาโชว์ไว้บนผิวเซลล์",
        "เหมือนกับว่าทุกเซลล์ต้องยืนถือป้ายบอกว่า 'ข้างในฉันมีอะไรอยู่บ้าง'",
        "แล้ว T cell ก็เดินตรวจ ถ้าเจอป้ายที่ผิดปกติ — เช่นเป็นชิ้นส่วนของไวรัส หรือชิ้นส่วนโปรตีนกลายพันธุ์จากมะเร็ง — มันจะสั่งฆ่าเซลล์นั้นทิ้งทันที",
        "จุดสำคัญคือ T cell แต่ละตัวจำได้แค่ 'หน้าเดียว' เท่านั้น เป็นระบบที่เฉพาะเจาะจงมาก")))

    s.append(slide('02 · ความผิดพลาด 2 แบบ', """
      <h2>ยามพลาดได้สองทาง — และคนละเรื่องกันเลย</h2>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--muted)">
          <div class="k">พลาดแบบที่ 1 · จำไม่ได้</div>
          <div class="v">มะเร็งรอด</div>
          <p>เซลล์มะเร็งเปลี่ยนหน้าไปนิดเดียว ยามจำไม่ได้ ก็ปล่อยผ่าน
          → เนื้องอกโตต่อ</p>
        </div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">พลาดแบบที่ 2 · จำสับ</div>
          <div class="v" style="color:var(--signal)">ทำร้ายตัวเอง</div>
          <p>ยามเห็นเซลล์ปกติแล้วคิดว่าเป็นศัตรู → ฆ่าเนื้อเยื่อดี ๆ ของตัวเอง
          นี่คือกลไกของโรคภูมิแพ้ตัวเอง</p>
        </div>
      </div>
      <p class="lede">ความสามารถ “จำหน้าที่คล้าย ๆ กันได้” คือ<strong>ดาบสองคม</strong> —
        มันคือสิ่งที่ทำให้ระบบภูมิคุ้มกันครอบคลุมพอ และเป็นสิ่งที่ทำให้มันอันตราย</p>
    """, note(
        "ทีนี้ ระบบแบบนี้พลาดได้ 2 แบบ และสองแบบนี้คนละเรื่องกันเลย",
        "แบบแรก คือจำไม่ได้ เซลล์มะเร็งกลายพันธุ์ไปนิดเดียว หน้าเปลี่ยนไปหน่อย ยามจำไม่ออก ก็ปล่อยผ่าน มะเร็งก็โตต่อ",
        "แบบที่สอง อันตรายกว่า คือจำสับ ยามไปเจอเซลล์ปกติที่หน้าคล้าย ๆ กัน แล้วเข้าใจผิดว่าเป็นศัตรู ก็ฆ่าทิ้ง อันนี้คือกลไกของโรคภูมิแพ้ตัวเอง",
        "<span class='beat'>[เน้น]</span> ประเด็นคือ ความสามารถจำหน้าคล้าย ๆ กันได้ มันเป็นดาบสองคม เราต้องการมันเพื่อให้ครอบคลุมเชื้อโรคที่กลายพันธุ์ แต่มันก็คือสาเหตุที่ระบบจะทำร้ายเราเอง")))

    s.append(slide('03 · เรื่องจริง ปี 2013', """
      <h2>ตอนที่เราสั่งให้ยาม<span style="color:var(--signal)">เก่งขึ้น</span> แล้วมันฆ่าคนไข้</h2>
      <p class="lede">แพทย์ดัดแปลง T cell ให้จับโปรตีนมะเร็งชื่อ MAGE-A3
        <strong>ให้แน่นขึ้นกว่าธรรมชาติ</strong> เพื่อรักษามะเร็งผิวหนังและมะเร็งไขกระดูก</p>
      <div class="grid g3">
        <div class="card"><div class="k">ผู้ป่วย 2 คนแรก</div>
          <div class="v" style="color:var(--signal)">เสียชีวิต</div>
          <p>ภายในไม่กี่วันหลังได้รับเซลล์ — หัวใจล้มเหลวเฉียบพลัน</p></div>
        <div class="card"><div class="k">ชันสูตรพบ</div>
          <div class="v">หัวใจ</div>
          <p>T cell บุกเข้าไปทำลายกล้ามเนื้อหัวใจ ทั้งที่หัวใจ<strong>ไม่มี</strong> MAGE-A3 เลย</p></div>
        <div class="card"><div class="k">สาเหตุจริง</div>
          <div class="v" style="color:var(--signal)">จำสับ</div>
          <p>ในหัวใจมีโปรตีนชื่อ <strong>titin</strong> ที่มีชิ้นส่วนหน้าตาคล้ายกัน</p></div>
      </div>
      <div class="rail warn">
        <p><strong>และไม่มีการทดสอบก่อนใช้ในคนตัวไหนจับสัญญาณนี้ได้เลย</strong> —
        นี่คือช่องว่างที่งานวิจัยด้านนี้พยายามอุด</p>
      </div>
    """, note(
        "ปี 2013 มีการทดลองรักษาแบบหนึ่ง แพทย์เอา T cell ของคนไข้ออกมา ดัดแปลงพันธุกรรมให้มันจับโปรตีนมะเร็งชื่อ MAGE-A3 ได้แน่นขึ้นกว่าธรรมชาติ แล้วใส่กลับเข้าไป แนวคิดคือทำให้ยามเก่งขึ้น",
        "ผู้ป่วย 2 คนแรกที่ได้รับ เสียชีวิตภายในไม่กี่วัน ด้วยภาวะหัวใจล้มเหลวเฉียบพลัน",
        "พอชันสูตร พบว่า T cell บุกเข้าไปทำลายกล้ามเนื้อหัวใจ ทั้ง ๆ ที่หัวใจไม่มีโปรตีนมะเร็ง MAGE-A3 อยู่เลยแม้แต่นิดเดียว",
        "สาเหตุจริงคือ ในกล้ามเนื้อหัวใจมีโปรตีนชื่อ titin และมันมีชิ้นส่วนที่หน้าตาคล้ายกับ MAGE-A3 พอเราทำให้ยามเก่งขึ้น เราก็ทำให้มันจำสับง่ายขึ้นด้วย",
        "<span class='beat'>[หยุด]</span> และที่สำคัญที่สุด — ไม่มีการทดสอบก่อนใช้ในคนตัวไหนเลย ที่จับสัญญาณนี้ได้")))

    s.append(slide('04 · โจทย์', """
      <h2>ทำนายล่วงหน้าได้ไหม ว่ายามจะจำสับกับอะไร</h2>
      <div style="margin:6px 0">""" + alignment() + """</div>
      <p class="lede">สองชิ้นนี้ต่างกัน <strong>4 ตำแหน่งจาก 9</strong> —
        เกือบครึ่ง แต่ยามที่ถูกดัดแปลงแล้วมองว่าเหมือนกัน</p>
      <p class="tiny">ตัวอักษรแต่ละตัวคือกรดอะมิโนหนึ่งตัว ซึ่งเป็นชิ้นส่วนย่อยที่สุดของโปรตีน
        · สีส้ม = ตำแหน่งที่ต่างกัน</p>
    """, note(
        "นี่คือหน้าตาของสองชิ้นนั้นครับ แถวบนคือ MAGE-A3 เป้าหมายที่ตั้งใจ แถวล่างคือ titin ในกล้ามเนื้อหัวใจ",
        "ตัวอักษรแต่ละตัวคือกรดอะมิโนหนึ่งตัว เป็นชิ้นส่วนย่อยที่สุดของโปรตีน ชิ้นนี้ยาว 9 ตัว",
        "ช่องสีส้มคือตำแหน่งที่ต่างกัน — ต่างกัน 4 จาก 9 ตำแหน่ง เกือบครึ่งนึง",
        "ถ้าดูด้วยตาเปล่าเราคงบอกว่ามันไม่เหมือนกันเลย แต่ยามที่ถูกดัดแปลงแล้วมองว่าเหมือน",
        "<span class='beat'>[ตั้งคำถาม]</span> คำถามของงานผมคือ เราคำนวณล่วงหน้าได้ไหม ว่าชิ้นไหนบ้างที่ยามตัวนี้จะจำสับ")))

    s.append(slide('05 · วิธีเดิม vs วิธีใหม่', """
      <h2>จากตารางท่องจำ ไปเป็น<span style="color:var(--atom)">การวัดของจริง</span></h2>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">วิธีเดิม</div><h3>ตารางท่องจำ 400 ช่อง</h3>
          <p>มีตารางบอกว่า “เปลี่ยนตัวอักษร A เป็น B ถือว่าต่างกันเท่าไร”
          ทุกคู่ที่เป็นไปได้ = 400 ช่อง</p>
          <p><strong>ปัญหา:</strong> ต้องมีข้อมูลสอนทุกช่อง · เจอตัวอักษรแบบใหม่ที่ไม่เคยเห็นก็จบ ·
          และมันบอกไม่ได้ว่า<em>ทำไม</em></p>
        </div>
        <div class="card" style="border-left:3px solid var(--atom)">
          <div class="k">วิธีที่เราเสนอ</div><h3>ไม้บรรทัดเคมี 8 อัน</h3>
          <p>แทนที่จะท่องจำ เราวัดกรดอะมิโนแต่ละตัวจริง ๆ ว่า
          <strong>ตัวใหญ่แค่ไหน · มีประจุไหม · ชอบน้ำหรือไม่ · ยืดหยุ่นแค่ไหน</strong> — รวม 8 อย่าง</p>
          <p>แล้วบอกว่า “ต่างกัน” = ผลรวมของความต่างในไม้บรรทัดทั้ง 8 อัน</p>
        </div>
      </div>
      <p class="lede">เปรียบเทียบง่าย ๆ: เลิกท่องตารางว่า “ส้มกับมะนาวต่างกัน 7 คะแนน”
        แล้วหันมา<strong>ชั่งน้ำหนัก วัดขนาด ชิมความเปรี้ยว</strong>ของมันจริง ๆ</p>
    """, note(
        "ทีนี้มาถึงส่วนที่เป็นงานผม",
        "วิธีที่ใช้กันอยู่คือมีตารางท่องจำ บอกว่าเปลี่ยนตัวอักษรตัวนี้เป็นตัวนั้น ถือว่าต่างกันกี่คะแนน กรดอะมิโนมี 20 ตัว จับคู่กันได้ 400 คู่ ก็ต้องมีตาราง 400 ช่อง",
        "ปัญหาของตารางท่องจำมี 3 อย่าง หนึ่ง ต้องมีข้อมูลไปสอนมันทุกช่อง สอง ถ้าเจอตัวอักษรแบบใหม่ที่ไม่เคยเห็นมาก่อน มันทำอะไรไม่ได้เลย และสาม มันบอกได้แค่ว่าอะไรต่าง แต่บอกไม่ได้ว่าทำไม",
        "สิ่งที่ผมทำคือ เลิกท่องจำ แล้วหันไปวัดโมเลกุลจริง ๆ ว่าตัวใหญ่แค่ไหน มีประจุไฟฟ้าไหม ชอบน้ำหรือไม่ชอบน้ำ ยืดหยุ่นแค่ไหน รวม 8 อย่าง",
        "เปรียบเทียบง่าย ๆ คือ แทนที่จะท่องตารางว่าส้มกับมะนาวต่างกัน 7 คะแนน เราก็ไปชั่งน้ำหนัก วัดขนาด ชิมความเปรี้ยวมันจริง ๆ แล้วคำนวณเอา")))

    s.append(slide('06 · ทดสอบย้อนหลัง', """
      <h2>แล้วถ้าย้อนกลับไปปี 2013 วิธีนี้จะเตือนไหม</h2>
      <p class="lede">เราให้โมเดลเห็นเฉพาะข้อมูลที่<strong>ทำได้ก่อนใช้ในคน</strong>
        (เปลี่ยนทีละ 1 ตัวอักษร) แล้วให้จัดอันดับชิ้นส่วน 111 ชิ้น
        ว่าอันไหนน่ากลัวที่สุด — โดยไม่เคยเห็น titin มาก่อน</p>
      <div style="margin:4px 0">""" + rankbar(RANKS) + """</div>
      <p class="lede">วิธีของเราจัด titin ไว้ที่ <strong style="color:var(--atom)">อันดับ 4 จาก 111</strong> —
        ส่วนวิธีนับตำแหน่งต่างแบบง่าย ๆ จัดไว้อันดับ 27</p>
    """, note(
        "ทีนี้มาถึงคำถามที่ผมสนใจที่สุด ถ้าย้อนกลับไปปี 2013 วิธีนี้จะเตือนไหม",
        "ผมทำแบบนี้ครับ ผมให้โมเดลเห็นเฉพาะข้อมูลที่หมอทำได้จริงก่อนเอาไปใช้กับคน คือข้อมูลแบบเปลี่ยนทีละ 1 ตัวอักษร",
        "แล้วผมเอาชิ้นส่วน 111 ชิ้นที่เปลี่ยนหลายตำแหน่งพร้อมกัน — ซึ่งมี titin อยู่ในนั้น แต่โมเดลไม่เคยเห็นมาก่อนเลย — มาให้มันจัดอันดับว่าอันไหนน่ากลัวที่สุด",
        "ผลคือ วิธีของเราจัด titin ไว้อันดับ 4 จาก 111 ส่วนวิธีนับตำแหน่งต่างแบบง่าย ๆ จัดไว้อันดับ 27",
        "<span class='beat'>[เว้น แล้วต่อสไลด์หน้าทันที อย่าให้ค้างความรู้สึกว่าชนะ]</span>")))

    s.append(slide('07 · แต่ต้องบอกให้ครบ', """
      <h2>ถ้าผมหยุดเล่าแค่สไลด์ที่แล้ว <span style="color:var(--signal)">ผมกำลังหลอกคุณ</span></h2>
      <div class="grid g3">
        <div class="verdict no"><div class="mark">1</div><p>
          นี่คือ<strong>เปปไทด์เดียว</strong> ไม่ใช่การทดสอบ — ผลที่ได้จากตัวอย่างเดียว
          พิสูจน์อะไรไม่ได้</p></div>
        <div class="verdict no"><div class="mark">2</div><p>
          เรา<strong>รู้คำตอบอยู่แล้ว</strong>ตอนทำ ไม่ใช่การทำนายล่วงหน้าจริง ๆ
          ต้องนับว่าเป็นภาพประกอบ</p></div>
        <div class="verdict no"><div class="mark">3</div><p>
          เมื่อทดสอบเต็มรูปแบบกับ TCR 151 ตัว วิธีของเรา
          <strong>ยังแพ้วิธีเดิม</strong>ในภาพรวม</p></div>
      </div>
      <div class="rail warn">
        <h3>และผลที่ผมชอบที่สุด คือผลที่ทำให้เราแย่ลง</h3>
        <p style="margin-top:6px">ตอนทดสอบค้นหาเป้าหมายจากโปรตีนทั้งจีโนมมนุษย์
          <strong>สองแสนกว่าชิ้น</strong> โมเดลเราหาเจอติดอันดับต้น ๆ ดูน่าประทับใจมาก —
          จนเราลองวิธีที่โง่ที่สุดเท่าที่คิดออก คือ<strong>นับดูว่าต่างกันกี่ตำแหน่ง</strong> จบ
          ไม่ต้องเรียนรู้อะไรเลย</p>
        <p style="margin-top:8px"><strong>มันทำได้ดีเท่ากัน</strong></p>
      </div>
    """, note(
        "ทีนี้ ถ้าผมหยุดเล่าแค่สไลด์ที่แล้ว ผมกำลังหลอกคุณอยู่ ผมเลยต้องเล่าต่อ",
        "ข้อแรก อันดับ 4 นั่นคือเปปไทด์แค่ตัวเดียว ผลจากตัวอย่างเดียวพิสูจน์อะไรไม่ได้เลย",
        "ข้อสอง ผมรู้คำตอบอยู่แล้วตอนที่ทำ มันไม่ใช่การทำนายล่วงหน้าจริง ๆ ต้องนับว่าเป็นแค่ภาพประกอบ",
        "ข้อสาม พอทดสอบเต็มรูปแบบกับ TCR 151 ตัว วิธีของเรายังแพ้วิธีเดิมในภาพรวม",
        "แต่ผลที่ผมชอบที่สุด คือผลที่ทำให้งานเราดูแย่ลง — ตอนที่เราลองค้นหาเป้าหมายจากโปรตีนทั้งจีโนมมนุษย์ สองแสนกว่าชิ้น โมเดลเราหาเจอติดอันดับต้น ๆ ดูน่าประทับใจมาก",
        "จนเราลองวิธีที่โง่ที่สุดเท่าที่คิดออก คือนับเฉย ๆ ว่าต่างกันกี่ตำแหน่ง ไม่ต้องเรียนรู้อะไรเลย <span class='beat'>[หยุด]</span> มันทำได้ดีเท่ากันครับ")))

    s.append(slide('08 · การตั้งข้อสอบดักตัวเอง', """
      <h2>เราตั้งข้อสอบดักตัวเอง แล้วสอบตก</h2>
      <p class="lede">ข้อดีข้อหนึ่งที่เราอ้างคือ วิธีเราใช้กับกรดอะมิโน<strong>แบบพิเศษ</strong>ได้
        ซึ่งตารางท่องจำทำไม่ได้เลย — แต่การอ้างลอย ๆ ไม่มีค่า เราเลยตั้งข้อสอบก่อนรัน</p>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--atom)">
          <div class="k">ข้อสอบที่ประกาศไว้ก่อน</div>
          <p style="font-size:15px">มีกรดอะมิโนตัวหนึ่งชื่อ <strong>citrulline</strong>
          ซึ่งตำราบอกว่าหน้าตาคล้ายตัวที่ชื่อ <strong>Q</strong> มากที่สุด<br><br>
          ถ้าโมเดลเราฉลาดจริง มันต้องตอบว่า <strong>Q</strong></p>
        </div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">คำตอบที่ได้</div>
          <div class="v" style="color:var(--signal)">ตอบผิด</div>
          <p>มันตอบ <strong>R</strong> ไม่ใช่ <strong>Q</strong><br><br>
          เราบันทึกว่า<strong>สอบตก</strong> ตามที่ประกาศไว้
          ไม่ย้ายเส้นชัยไปบอกว่า “จริง ๆ แล้วก็เกือบถูก”</p>
        </div>
      </div>
      <p class="tiny">(พอไปดูเหตุผล มันมีตรรกะของมันอยู่ และ Q เป็นคำตอบอันดับ 2 —
        แต่นั่นเป็นคำอธิบายทีหลัง ไม่ใช่การสอบผ่าน)</p>
    """, note(
        "อีกเรื่องหนึ่งที่ผมอยากเล่า เพราะผมคิดว่ามันสำคัญกว่าตัวผลลัพธ์",
        "ข้อดีข้อหนึ่งที่เราอ้างคือ วิธีเราใช้กับกรดอะมิโนแบบพิเศษได้ ซึ่งตารางท่องจำทำไม่ได้เลย",
        "แต่การอ้างลอย ๆ แบบนั้นไม่มีค่าอะไร เราเลยตั้งข้อสอบดักตัวเองไว้ก่อนรันโปรแกรม",
        "คือมีกรดอะมิโนตัวหนึ่งชื่อ citrulline ตำราบอกว่ามันหน้าตาคล้ายตัวที่ชื่อ Q มากที่สุด เราเลยประกาศไว้ก่อนเลยว่า ถ้าโมเดลเราฉลาดจริง มันต้องตอบ Q",
        "ผลคือมันตอบ R ครับ ตอบผิด",
        "เราก็บันทึกไว้ว่าสอบตก ตามที่ประกาศไว้ ไม่ย้ายเส้นชัยไปบอกว่าจริง ๆ แล้วก็เกือบถูกนะ <span class='beat'>[ยิ้ม]</span> ทั้งที่เขียนแบบนั้นก็ได้ และคงไม่มีใครจับได้")))

    s.append(slide('09 · สรุป', """
      <h2>สิ่งที่ผมอยากให้กลับบ้านไปด้วย</h2>
      <div class="grid g3">
        <div class="card"><div class="k">01</div>
          <h3 style="color:var(--atom)">ปัญหานี้มีอยู่จริง</h3>
          <p>การรักษามะเร็งด้วยการดัดแปลง T cell กำลังมาแรง
          และความปลอดภัยของมันขึ้นกับการทำนายว่ามันจะจำสับกับอะไร</p></div>
        <div class="card"><div class="k">02</div>
          <h3 style="color:var(--atom)">วัดของจริงดีกว่าท่องจำ (บางเรื่อง)</h3>
          <p>วิธีของเราใช้ตัวเลขแค่ 8 ตัวแทน 380 ตัว
          และใช้กับของที่ไม่เคยเห็นได้ — แต่ยังไม่ชนะทุกด้าน</p></div>
        <div class="card" style="border-left:3px solid var(--accent)"><div class="k">03 · สำคัญที่สุด</div>
          <h3 style="color:var(--accent)">งานที่เชื่อถือได้ ต้องเล่าตอนที่ตัวเองแพ้ด้วย</h3>
          <p>ผลที่มีค่าที่สุดในงานนี้ คือผลที่บอกว่า
          <strong>วิธีง่าย ๆ ก็ทำได้เท่ากัน</strong></p></div>
      </div>
      <div class="rail">
        <p style="font-size:16px">ถ้าเราเล่าแต่สไลด์อันดับ 4 งานนี้จะดูดีกว่านี้มาก
        <strong>และจะมีประโยชน์น้อยกว่านี้มาก</strong> เพราะคนอ่านจะเอาไปใช้ผิด
        และคนที่ทำต่อจะเสียเวลาไปกับทางที่เรารู้อยู่แล้วว่าตัน</p>
      </div>
      <p class="tiny">ขอบคุณครับ · ยินดีรับคำถาม</p>
    """, note(
        "สรุปสามข้อที่อยากให้กลับบ้านไปด้วยครับ",
        "ข้อแรก ปัญหานี้มีอยู่จริง การรักษามะเร็งด้วยการดัดแปลง T cell กำลังมาแรงมาก และความปลอดภัยของมันขึ้นอยู่กับว่าเราทำนายได้แม่นแค่ไหนว่ามันจะไปจำสับกับอะไร",
        "ข้อสอง การวัดของจริงดีกว่าการท่องจำในหลายด้าน เราใช้ตัวเลขแค่ 8 ตัวแทน 380 ตัว และใช้กับของที่ไม่เคยเห็นมาก่อนได้ แต่ยังไม่ชนะทุกด้าน",
        "ข้อสาม และเป็นข้อที่ผมอยากให้จำที่สุด งานวิจัยที่เชื่อถือได้ต้องเล่าตอนที่ตัวเองแพ้ด้วย",
        "ถ้าผมเล่าแต่สไลด์อันดับ 4 งานนี้จะดูดีกว่านี้เยอะ และจะมีประโยชน์น้อยกว่านี้เยอะ เพราะคนอ่านจะเอาไปใช้ผิด และคนที่ทำต่อจะเสียเวลาไปกับทางที่เรารู้อยู่แล้วว่าตัน",
        "ขอบคุณครับ")))

    return shell("ยามที่จำผิด", "".join(s))


# ===========================================================================
# DECK B -- clinicians
# ===========================================================================
def clinical_deck():
    s = []

    s.append(slide('เวอร์ชันแพทย์ · ประมาณ 14 นาที', """
      <h1>ทำนาย <span style="color:var(--signal)">off-target</span><br>ของ TCR-T ก่อนถึงคนไข้</h1>
      <p class="lede">ประเมินว่าโมเดลคำนวณช่วยคัดกรอง cross-reactivity ได้จริงแค่ไหน —
        พร้อมข้อจำกัดที่ต้องรู้ก่อนเอาไปอ้างอิงทางคลินิก</p>
      <div class="tw" style="margin-top:6px">
        <table>
          <tr><th>TCR ในชุดข้อมูลนี้</th><th>เป้าหมาย</th><th>HLA</th><th>บริบททางคลินิก</th></tr>
          <tr><td class="mono">a3a</td><td class="mono">EVDPIGHLY · MAGE-A3</td><td class="mono">A*01:01</td>
            <td style="color:var(--signal)">เสียชีวิต 2 ราย · titin cross-reactivity</td></tr>
          <tr><td class="mono">c259</td><td class="mono">SLLMWITQC · NY-ESO-1</td><td class="mono">A*02:01</td>
            <td>TCR-T ระยะคลินิก</td></tr>
          <tr><td class="mono">TCR-1E6</td><td class="mono">ALWGPDPAAA · preproinsulin</td><td class="mono">A*02:01</td>
            <td>autoreactive · เบาหวานชนิดที่ 1</td></tr>
          <tr><td class="mono">MBP-TCR</td><td class="mono">ASQKRPSQRSK · myelin</td><td class="mono">I-A<sup>u</sup></td>
            <td>โมเดล demyelinating disease</td></tr>
        </table>
      </div>
      <p class="tiny">กด <strong>N</strong> เพื่อดูสคริปต์พูด · ลูกศร ↑↓ เลื่อนสไลด์</p>
    """, note(
        "สวัสดีครับ วันนี้ผมจะเล่างานที่เกี่ยวกับความปลอดภัยของ TCR-T therapy โดยเฉพาะเรื่องการทำนาย off-target ล่วงหน้า",
        "ผมขอเริ่มจากตารางนี้ก่อน เพราะอยากให้เห็นว่าชุดข้อมูลที่ผมใช้ไม่ใช่ข้อมูลสังเคราะห์ แต่เป็น TCR จริงจากงานคลินิก",
        "แถวแรก a3a คือ affinity-enhanced MAGE-A3 TCR ตัวที่ทำให้ผู้ป่วยเสียชีวิต 2 ราย จาก titin cross-reactivity",
        "c259 คือ NY-ESO-1 TCR ที่อยู่ในระยะคลินิก ส่วน 1E6 กับ MBP เป็น autoreactive TCR จากเบาหวานชนิดที่ 1 และโรค demyelinating",
        "ประเด็นคือ ถ้าเครื่องมือนี้จะมีประโยชน์ มันต้องทำงานกับ TCR พวกนี้ได้")))

    s.append(slide('01 · โจทย์ทางคลินิก', """
      <h2>สองโหมดความล้มเหลวที่ต้องประเมินคนละแบบ</h2>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--muted)">
          <div class="k">Efficacy failure</div><h3>คัด neoantigen ผิด</h3>
          <p>เลือก epitope ที่ TCR จริง ๆ ไม่ตอบสนอง → วัคซีน/เซลล์บำบัดไม่ได้ผล
          ประเมินได้จากผลการรักษา ยัง<strong>แก้ตัวได้</strong></p>
        </div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">Safety failure</div><h3>Off-target toxicity</h3>
          <p>TCR ไปจับ self-peptide ในเนื้อเยื่อปกติ → ความเสียหายอาจ
          <strong>เฉียบพลันและถึงชีวิต</strong> โดยไม่มีสัญญาณเตือนล่วงหน้า</p>
        </div>
      </div>
      <div class="rail warn">
        <p><strong>ประเด็นสำคัญ:</strong> การเพิ่ม affinity เพื่อ efficacy
        <strong>เพิ่มความเสี่ยง off-target ไปพร้อมกัน</strong> —
        ทั้งสองโหมดนี้ไม่ได้แยกจากกัน และนี่คือเหตุผลที่การทำนาย cross-reactivity
        ไม่ใช่เรื่อง optional</p>
      </div>
    """, note(
        "โจทย์ทางคลินิกมีสองโหมดความล้มเหลว และต้องประเมินคนละแบบ",
        "โหมดแรก efficacy failure คือเราคัด neoantigen ผิด เลือก epitope ที่ TCR ไม่ตอบสนองจริง วัคซีนหรือเซลล์บำบัดก็ไม่ได้ผล อันนี้เห็นจากผลการรักษา และยังแก้ตัวได้",
        "โหมดที่สอง safety failure คือ off-target toxicity TCR ไปจับ self-peptide ในเนื้อเยื่อปกติ ความเสียหายอาจเฉียบพลันและถึงชีวิต โดยไม่มีสัญญาณเตือน",
        "ประเด็นที่ผมอยากเน้นคือ สองโหมดนี้ไม่ได้แยกจากกัน การเพิ่ม affinity เพื่อให้ได้ efficacy มันเพิ่มความเสี่ยง off-target ไปพร้อมกันเสมอ",
        "เพราะฉะนั้นการทำนาย cross-reactivity ไม่ใช่เรื่อง optional มันอยู่บน critical path ของการพัฒนา")))

    s.append(slide('02 · Index case', """
      <h2>MAGE-A3 a3a — สิ่งที่ preclinical ทั้งชุด<span style="color:var(--signal)">จับไม่ได้</span></h2>
      <div style="margin:4px 0">""" + alignment() + """</div>
      <div class="grid g3">
        <div class="card"><div class="k">Presentation</div>
          <p>ผู้ป่วย 2 รายแรก · <strong>cardiogenic shock</strong> ภายในไม่กี่วันหลัง infusion</p></div>
        <div class="card"><div class="k">Autopsy</div>
          <p>Myocardial damage + T-cell infiltration · <strong>ตรวจไม่พบ MAGE-A3</strong>
          ในเนื้อเยื่อหัวใจ</p></div>
        <div class="card"><div class="k">Mechanism</div>
          <p>Molecular mimicry กับ <strong>titin ESDPIVAQY</strong> ใน beating cardiomyocytes
          — ต่างกัน 4/9 ตำแหน่ง</p></div>
      </div>
      <p class="tiny">Linette et al., <em>Blood</em> 122:863 (2013) ·
        Cameron et al., <em>Sci Transl Med</em> (2013) ·
        native TCR ไม่จับ titin — <strong>affinity enhancement คือสิ่งที่สร้าง cross-reactivity นี้ขึ้นมา</strong></p>
    """, note(
        "นี่คือ index case ที่เป็นจุดตั้งต้นของงานนี้",
        "affinity-enhanced MAGE-A3 TCR ผู้ป่วย 2 รายแรกเกิด cardiogenic shock ภายในไม่กี่วันหลัง infusion และเสียชีวิตทั้งคู่",
        "ชันสูตรพบ myocardial damage ร่วมกับ T-cell infiltration แต่ตรวจไม่พบ MAGE-A3 ในเนื้อเยื่อหัวใจเลย",
        "กลไกจริงคือ molecular mimicry กับเปปไทด์จาก titin ที่แสดงออกใน beating cardiomyocytes ต่างกัน 4 จาก 9 ตำแหน่ง อย่างที่เห็นในภาพ",
        "จุดที่ผมอยากเน้นสำหรับที่นี่คือ native TCR ไม่จับ titin ครับ การทำ affinity enhancement คือสิ่งที่สร้าง cross-reactivity ตัวนี้ขึ้นมาเอง",
        "และไม่มี preclinical assay ตัวไหนในตอนนั้นจับสัญญาณนี้ได้")))

    s.append(slide('03 · ทำไมถึงยาก', """
      <h2>Sequence identity ทำนาย cross-reactivity ไม่ได้</h2>
      <p class="lede">ถ้า cross-reactivity เป็นสัดส่วนกับความเหมือนของลำดับ
        การคัดกรองก็จบไปนานแล้ว — แต่มันไม่ใช่</p>
      <div class="grid g2">
        <div class="rail warn">
          <h3>ต่างกัน 4/9 แต่กระตุ้นเต็มที่</h3>
          <p style="margin-top:6px">titin ต่างจาก MAGE-A3 เกือบครึ่งเปปไทด์
          แต่กระตุ้น TCR ได้ระดับ <strong>strong</strong></p>
        </div>
        <div class="rail quiet">
          <h3>ต่างกัน 1 ตำแหน่งแต่เงียบสนิท</h3>
          <p style="margin-top:6px">การเปลี่ยนกรดอะมิโนเพียงตัวเดียวที่ตำแหน่ง contact
          ก็ทำให้ activation หายไปหมดได้</p>
        </div>
      </div>
      <p class="lede">สิ่งที่กำหนดผลจริง ๆ คือ <strong>ตำแหน่งไหน</strong> ที่เปลี่ยน
        และ <strong>เปลี่ยนเป็นเคมีแบบไหน</strong> — ไม่ใช่จำนวนตำแหน่งที่เปลี่ยน</p>
      <p class="tiny">นี่คือเหตุผลที่ต้องมีโมเดล ไม่ใช่แค่ BLAST หา homology</p>
    """, note(
        "ทำไมถึงยาก",
        "ถ้า cross-reactivity มันเป็นสัดส่วนกับ sequence identity เรื่องนี้จบไปนานแล้ว เราแค่ BLAST หา homolog ในโปรตีโอมก็พอ",
        "แต่ข้อมูลบอกว่าไม่ใช่ titin ต่างจาก MAGE-A3 เกือบครึ่งเปปไทด์ แต่กระตุ้นได้ระดับ strong",
        "ขณะเดียวกัน การเปลี่ยนกรดอะมิโนแค่ตัวเดียวที่ตำแหน่ง contact ก็ทำให้ activation หายไปหมดได้",
        "สิ่งที่กำหนดผลจริง ๆ คือตำแหน่งไหนที่เปลี่ยน และเปลี่ยนไปเป็นเคมีแบบไหน ไม่ใช่จำนวนตำแหน่ง",
        "นี่คือเหตุผลที่เราต้องมีโมเดล ไม่ใช่แค่หา homology")))

    s.append(slide('04 · โมเดลและสิ่งที่เราเปลี่ยน', """
      <h2>วัดระยะเคมีจาก index peptide</h2>
      <p class="lede">โมเดลอ้างอิงในสาขานี้ (BATMAN) ให้คะแนน mutant peptide จาก
        <strong>ระยะทางถ่วงน้ำหนักไปยัง index peptide</strong>
        แล้วแปลงเป็น activation 3 ระดับด้วย ordered logistic regression</p>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">เดิม · substitution matrix</div>
          <p>ตาราง 20×20 เรียนจากข้อมูล — <strong>~380 พารามิเตอร์อิสระ</strong></p>
          <p>ข้อจำกัด: substitution ที่ไม่เคยเห็นได้แค่ค่า prior ·
          ใช้กับ <em class="term">PTM</em> ไม่ได้ · ตีความไม่ได้</p>
        </div>
        <div class="card" style="border-left:3px solid var(--atom)">
          <div class="k">งานนี้ · atomic representation</div>
          <p>คำนวณ <strong>คุณสมบัติเชิงเคมี 8 ตัว</strong> ของ side chain จากโครงสร้างโมเลกุลจริง
          (ขนาด · ประจุ · polarity · H-bond · aromaticity · ความยืดหยุ่น)</p>
          <p>ระยะ = ผลรวมถ่วงน้ำหนักของความต่าง → <strong>8 พารามิเตอร์</strong></p>
        </div>
      </div>
      <p class="tiny">แนวคิดใช้ physicochemical encoding ไม่ใช่ของใหม่ (pTEAM ใช้ Atchley factors)
        — สิ่งที่ต่างคือ descriptor มาจากโครงสร้างโมเลกุลจริง และเราเทียบกับ prior art ตัวนั้นตรง ๆ</p>
    """, note(
        "อธิบายโมเดลสั้น ๆ ครับ",
        "โมเดลอ้างอิงในสาขานี้ชื่อ BATMAN ให้คะแนน mutant peptide จากระยะทางถ่วงน้ำหนักไปยัง index peptide แล้วแปลงเป็น activation 3 ระดับ คือ non weak strong ด้วย ordered logistic regression",
        "หัวใจของมันคือตาราง substitution matrix ขนาด 20 คูณ 20 ที่เรียนจากข้อมูล มีพารามิเตอร์อิสระประมาณ 380 ตัว",
        "ข้อจำกัดของตารางคือ substitution ที่ไม่เคยเห็นในข้อมูลจะได้แค่ค่า prior ใช้กับ post-translational modification ไม่ได้เลย และตีความไม่ได้",
        "สิ่งที่เราเปลี่ยนคือ แทนตารางด้วยคุณสมบัติเชิงเคมี 8 ตัวของ side chain ที่คำนวณจากโครงสร้างโมเลกุลจริง เหลือ 8 พารามิเตอร์",
        "ผมขอออกตัวว่าแนวคิดใช้ physicochemical encoding ไม่ใช่ของใหม่ pTEAM ใช้ Atchley factors อยู่แล้ว สิ่งที่เราต่างคือ descriptor มาจากโครงสร้างจริง และเราเทียบกับ prior art ตัวนั้นตรง ๆ ไม่เลี่ยง")))

    s.append(slide('05 · Retrospective', """
      <h2>ย้อนกลับไปที่ index case</h2>
      <p class="lede">ให้โมเดลเห็นเฉพาะ <strong>single-substitution scan</strong> ของ a3a
        — ข้อมูลระดับที่ทำได้ก่อน first-in-human — แล้วให้จัดอันดับ
        multi-substitution peptide 111 ตัวที่ไม่เคยเห็น ซึ่งมี titin อยู่ในนั้น</p>
      <div style="margin:4px 0">""" + rankbar(RANKS) + """</div>
      <div class="grid g2">
        <div class="card" style="border-left:3px solid var(--atom)">
          <div class="k">ผลรวมของ strong activators ทั้ง 8 ตัว</div>
          <p style="line-height:1.9">atomic · median rank <strong>5.5</strong><br>
            Hamming · median rank <strong style="color:var(--signal)">35.5</strong></p>
          <p class="tiny">สัญญาณกว้างกว่าเคสเดียว — แต่ก็ยังแค่ 8 ตัวใน TCR เดียว</p>
        </div>
        <div class="rail warn">
          <h3>⚠️ อย่าอ่านเกินกว่านี้</h3>
          <p style="margin-top:6px">titin คือ <strong>n = 1</strong> ·
            เรารู้คำตอบอยู่แล้ว จึงไม่ใช่ prospective ·
            และการทดสอบ multi-substitution เต็มรูปแบบ (6 TCR)
            พบว่า<strong>ทุกโมเดลเสมอกัน</strong></p>
        </div>
      </div>
    """, note(
        "ทีนี้ผมย้อนกลับไปที่ index case",
        "ผมให้โมเดลเห็นเฉพาะ single-substitution scan ของ a3a ซึ่งเป็นข้อมูลระดับที่ทำได้จริงก่อน first-in-human",
        "แล้วให้จัดอันดับ multi-substitution peptide 111 ตัวที่โมเดลไม่เคยเห็น ซึ่งมี titin อยู่ในนั้น",
        "atomic model จัด titin ไว้อันดับ 4 จาก 111 ส่วน Hamming distance จัดไว้อันดับ 27",
        "ถ้าดูภาพรวมของ strong activator ทั้ง 8 ตัว atomic ได้ median rank 5.5 เทียบกับ Hamming ที่ 35.5 อันนี้เป็นสัญญาณที่กว้างกว่าเคสเดียว",
        "<span class='beat'>[เน้นให้ชัด]</span> แต่ผมขอเน้นว่าอย่าอ่านเกินกว่านี้ครับ titin คือ n เท่ากับ 1 เรารู้คำตอบอยู่แล้วตอนวิเคราะห์ จึงไม่ใช่ prospective test และการทดสอบ multi-substitution เต็มรูปแบบที่มี 6 TCR พบว่าทุกโมเดลเสมอกันหมด",
        "ผมเอาสไลด์นี้มาให้ดูเพราะมันเป็นภาพที่ชัดว่าโจทย์คืออะไร ไม่ใช่เพราะมันเป็นหลักฐาน")))

    s.append(slide('06 · หลักฐานเต็มรูปแบบ', """
      <h2>Benchmark บน 151 TCR</h2>
      <p class="lede">AUC ในที่นี้ตีความเหมือน ROC ที่คุ้นเคย:
        <strong>หยิบ peptide ที่กระตุ้นจริงมา 1 ตัว กับที่ไม่กระตุ้นมา 1 ตัว
        โมเดลจัดอันดับถูกกี่เปอร์เซ็นต์</strong> · คิดแยกราย TCR แล้วจับคู่ทดสอบ</p>
      <figure class="figure">
        <img src="__FIG2__" alt="Benchmark of five representations across 151 TCRs, in-distribution and out-of-distribution, with paired effect sizes">
      </figure>
      <div class="grid g3">
        <div class="verdict yes"><div class="mark">✓</div><p>ดีกว่า fixed BLOSUM100 และดีกว่า
          prior art (Atchley-5) อย่างมีนัยสำคัญ</p></div>
        <div class="verdict no"><div class="mark">✕</div><p>แต่<strong>แพ้ learned matrix</strong>
          ในสถานการณ์ปกติ ด้วย effect ขนาดใหญ่</p></div>
        <div class="verdict neu"><div class="mark">→</div><p>ช่องว่างระหว่างทุกวิธี
          <strong>แคบกว่าที่คาด</strong> โดยเฉพาะฝั่ง out-of-distribution</p></div>
      </div>
    """, note(
        "ทีนี้มาดูหลักฐานเต็มรูปแบบครับ benchmark บน TCR 151 ตัว",
        "ก่อนอื่นขออธิบาย AUC ในสไลด์นี้ ตีความเหมือน ROC ที่ทุกท่านคุ้นเคยเลยครับ คือหยิบ peptide ที่กระตุ้นจริงมาหนึ่งตัว กับที่ไม่กระตุ้นมาหนึ่งตัว แล้วถามว่าโมเดลจัดอันดับถูกกี่เปอร์เซ็นต์ ค่า 0.85 ก็คือถูก 85 เปอร์เซ็นต์ของคู่",
        "สิ่งที่ผมทำต่างจากงานทั่วไปคือ ผมคิด AUC แยกราย TCR ไม่ได้รวมทุก TCR เข้าด้วยกัน เพราะถ้ารวม ค่าจะเพี้ยนจาก base rate ที่ต่างกันมาก",
        "ผลคือ วิธีของเราดีกว่า fixed BLOSUM100 และดีกว่า prior art อย่างมีนัยสำคัญ",
        "แต่แพ้ learned matrix ในสถานการณ์ปกติ ด้วย effect size ขนาดใหญ่ อันนี้ต้องพูดตรง ๆ",
        "และข้อสังเกตที่ผมคิดว่าสำคัญสำหรับคนที่จะเอาไปใช้คือ ช่องว่างระหว่างทุกวิธีมันแคบกว่าที่คาด โดยเฉพาะฝั่งขวาที่เป็น out-of-distribution")))

    s.append(slide('07 · คุณภาพหลักฐาน', """
      <h2>งานนี้ <span style="color:var(--signal)">underpowered</span> สำหรับคำถามหลัก</h2>
      <p class="lede">ข้อได้เปรียบที่เราอยากอ้าง มี effect size เล็ก
        (<span class="mono">d ≈ 0.11–0.18</span>) — ทำซ้ำได้จริงและทิศทางไม่เคยกลับ
        แต่เล็กเกินกว่าจะยืนยันด้วยข้อมูลที่มีอยู่</p>
      <div class="grid g3">
        <div class="card"><div class="k">ต้องการที่ α = 0.05</div>
          <div class="v">~243</div><p>TCR</p></div>
        <div class="card"><div class="k">หลังแก้ multiple comparison</div>
          <div class="v">~425</div><p>TCR</p></div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">มีอยู่จริงทั้งวงการ</div>
          <div class="v" style="color:var(--signal)">151</div><p>TCR</p></div>
      </div>
      <div class="rail warn">
        <p>นี่ไม่ใช่ปัญหาที่แก้ด้วยการวิเคราะห์ซ้ำหรือเปลี่ยนสถิติ —
        ต้องมี <strong>mutational scan ชุดใหม่</strong> เท่านั้น
        เหมือน underpowered trial ที่ต้องเพิ่ม n ไม่ใช่เปลี่ยนวิธีวิเคราะห์</p>
      </div>
    """, note(
        "สไลด์นี้เป็นเรื่องคุณภาพหลักฐาน ซึ่งผมคิดว่าท่านน่าจะประเมินได้ดีกว่าผมด้วยซ้ำ",
        "ข้อได้เปรียบที่เราอยากอ้าง มี effect size เล็กมาก Cohen's d ประมาณ 0.11 ถึง 0.18",
        "ผมตรวจแล้วว่ามันทำซ้ำได้จริง รัน 5 seed ทิศทางไม่เคยกลับ มันไม่ใช่ noise",
        "แต่มันเล็กเกินกว่าจะยืนยันด้วยข้อมูลที่มีอยู่ ถ้าคำนวณ power ที่ alpha 0.05 ต้องใช้ TCR ประมาณ 243 ตัว ถ้าแก้ multiple comparison ด้วยต้องใช้ประมาณ 425 ตัว",
        "ทั้งวงการมีอยู่ 151 ตัว",
        "อันนี้เหมือน underpowered trial ครับ มันแก้ด้วยการเปลี่ยนวิธีวิเคราะห์ไม่ได้ ต้องเพิ่ม n อย่างเดียว")))

    s.append(slide('08 · Proteome-scale screening', """
      <h2>คัดกรอง off-target ทั้งโปรตีโอม — ได้ผล แต่ไม่ต้องใช้โมเดล</h2>
      <div class="grid g2w" style="align-items:start">
        <div class="card">
          <div class="k">การทดสอบ</div>
          <p style="font-size:15px">สแกนหา target ของ TCR จาก peptide
          <strong>259,312 ชิ้น</strong> ทั้งจีโนมมนุษย์ (TScan-II screen)</p>
          <p style="font-size:15px; margin-top:6px">ผล: hit ที่ยืนยันแล้ว
          <strong>5 ใน 5 อันดับแรก</strong> · hypergeometric
          <span class="mono">p = 6×10⁻²⁵</span> · ทำซ้ำได้ใน 3 screens</p>
        </div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">แต่เมื่อเทียบกับ null</div>
          <p style="font-size:15px"><strong>Hamming distance</strong> ที่ไม่เรียนรู้อะไรเลย
          <strong>ทำได้เท่ากันทุก screen</strong></p>
          <p class="tiny" style="margin-top:6px">โมเดลที่ fit แล้วทั้ง 4 แบบ
          แยกกันแทบไม่ออก</p>
        </div>
      </div>
      <div class="rail warn">
        <h3>ข้อสรุปที่ใช้ได้จริงทางคลินิก</h3>
        <p style="margin-top:6px">ที่ระดับโปรตีโอม <strong>คอขวดไม่ใช่ substitution model
        แต่คือ MHC presentation</strong> — decoy ที่ลำดับคล้ายมากแต่ไม่กระตุ้น
        แยกออกได้ด้วยข้อมูล MHC binding ไม่ใช่ด้วยการจำลอง TCR contact</p>
        <p class="tiny" style="margin-top:8px">ทดสอบแล้วบน DRB1*11:01 — MHC score
        เพียงอย่างเดียวดีกว่า TCR distance และ fusion ยก precision@10 จาก 0.60 เป็น 0.70 ·
        แต่บน DRB1*04:01 ตัว predictor เองยังทำนายไม่ได้ จึงไม่ช่วย</p>
      </div>
    """, note(
        "สไลด์นี้เป็นผลที่ผมคิดว่ามีประโยชน์ทางคลินิกมากที่สุด แม้ว่ามันจะทำให้งานผมดูแย่ลงก็ตาม",
        "เราลองใช้โมเดลคัดกรอง off-target จริง ๆ คือสแกนหา target ของ TCR จาก peptide สองแสนห้าหมื่นกว่าชิ้นทั้งจีโนมมนุษย์",
        "ผลออกมาดูดีมาก hit ที่ยืนยันด้วยการทดลองแล้ว ติด 5 ใน 5 อันดับแรก p value 6 คูณสิบยกกำลังลบ 25 และทำซ้ำได้ใน 3 screens",
        "แต่พอเราเอา Hamming distance ที่ไม่เรียนรู้อะไรเลยมาเทียบ มันทำได้เท่ากันทุก screen ครับ และโมเดลที่ fit แล้วทั้ง 4 แบบก็แยกกันแทบไม่ออก",
        "ข้อสรุปที่ผมคิดว่าเอาไปใช้ได้จริงคือ ที่ระดับโปรตีโอม คอขวดไม่ใช่ substitution model แต่คือ MHC presentation",
        "เราทดสอบสมมติฐานนี้แล้ว บน DRB1 11:01 ตัว MHC score อย่างเดียวดีกว่า TCR distance และ fusion ยก precision at 10 จาก 0.6 เป็น 0.7 แต่บน DRB1 04:01 ตัว predictor เองยังทำนายไม่ได้เลย จึงไม่ช่วย",
        "แปลว่าถ้าใครจะลงทุนพัฒนาเครื่องมือคัดกรอง off-target ควรลงที่ MHC class II prediction ก่อน ไม่ใช่ที่ substitution model")))

    s.append(slide('09 · Autoimmunity / PTM', """
      <h2>Post-translational modification — จุดที่ตาราง 20×20 ทำไม่ได้เลย</h2>
      <p class="lede">Citrullination ใน RA, phosphopeptide neoantigen ในมะเร็ง —
        residue เหล่านี้<strong>ไม่มีช่องในเมทริกซ์ 20×20</strong> จึงคำนวณไม่ได้ตั้งแต่ต้น
        แต่ atomic representation ขอแค่โครงสร้างโมเลกุล</p>
      <figure class="figure" style="--fig-max:32vh">
        <img src="__FIG7__" alt="Distances from twelve modified residues to the canonical twenty">
        <figcaption>12 modified residues — phospho-Ser/Thr/Tyr, citrulline,
          methyl/acetyl-Lys, hydroxyproline, nitro-Tyr, selenocysteine ·
          <strong>ไม่ต้องเทรนใหม่</strong></figcaption>
      </figure>
      <div class="grid g2">
        <div class="verdict neu"><div class="mark">!</div><p>
          เป็นการสาธิต<strong>ความสามารถ</strong> ไม่ใช่<strong>ความแม่น</strong> —
          ยังไม่มี mutational scan ชุดใดที่มี modified residue</p></div>
        <div class="verdict no"><div class="mark">✕</div><p>
          และการทดสอบเชิงเคมีที่เราประกาศไว้ล่วงหน้า (citrulline ควรใกล้ Q)
          <strong>ไม่ผ่าน</strong> — เราบันทึกตามนั้น</p></div>
      </div>
    """, note(
        "สไลด์นี้เกี่ยวกับ post-translational modification ซึ่งผมคิดว่าน่าสนใจสำหรับท่านที่ดูแลผู้ป่วยโรคภูมิแพ้ตัวเอง",
        "citrullination ใน rheumatoid arthritis หรือ phosphopeptide neoantigen ในมะเร็ง residue พวกนี้ไม่มีช่องในเมทริกซ์ 20 คูณ 20 เลย เพราะเมทริกซ์มีแค่กรดอะมิโนมาตรฐาน 20 ตัว",
        "แปลว่าวิธีเดิมคำนวณไม่ได้ตั้งแต่ต้น ไม่ใช่คำนวณแล้วผิด",
        "ส่วนวิธีของเราขอแค่โครงสร้างโมเลกุล ก็ให้ระยะได้ทันทีโดยไม่ต้องเทรนใหม่ ในรูปนี้คือ 12 residue ที่ดัดแปลงแล้ว",
        "แต่ผมต้องเน้นสองข้อครับ",
        "ข้อแรก นี่เป็นการสาธิตความสามารถ ไม่ใช่ความแม่น เพราะยังไม่มี mutational scan ชุดใดในโลกที่มี modified residue ให้เทียบ",
        "ข้อสอง เราตั้งการทดสอบเชิงเคมีไว้ล่วงหน้าว่า citrulline ควรใกล้ Q ที่สุด แล้วผลไม่ผ่าน เราบันทึกว่าไม่ผ่านตามนั้น")))

    s.append(slide('10 · Bottom line', """
      <h2>สรุปสำหรับการใช้งานจริง</h2>
      <div class="grid g3">
        <div class="card" style="border-left:3px solid var(--accent)">
          <div class="k">ใช้ได้ตอนนี้</div>
          <p style="font-size:14.5px">จัดลำดับความเสี่ยงของ candidate peptide
          เพื่อ<strong>เลือกว่าจะเอาอะไรไปทดลองต่อ</strong> — โมเดลจัด strong activator
          ขึ้นมาอยู่หัวตารางได้จริง</p>
        </div>
        <div class="card" style="border-left:3px solid var(--signal)">
          <div class="k">อย่าใช้ทำสิ่งนี้</div>
          <p style="font-size:14.5px"><strong>อย่าใช้ตัดสินความปลอดภัยเพื่อ clear
          การเข้าคน</strong> — คุณภาพหลักฐานยังไม่พอ และที่ระดับโปรตีโอม
          วิธีง่าย ๆ ก็ให้ผลเท่ากัน</p>
        </div>
        <div class="card" style="border-left:3px solid var(--atom)">
          <div class="k">ต้องการอะไรต่อ</div>
          <p style="font-size:14.5px">① mutational scan ชุดใหม่ (ต้องการ ~425 TCR)<br>
          ② <strong>MHC class II predictor ที่ดีขึ้น</strong> — คอขวดตัวจริง<br>
          ③ ข้อมูล PTM ที่วัด activation จริง</p>
        </div>
      </div>
      <div class="rail">
        <p style="font-size:16px">ข้อความที่ผมอยากฝากไว้: การคัดกรอง off-target ด้วยคอมพิวเตอร์
        <strong>ยังไม่อยู่ในจุดที่แทนการทดลองได้</strong> —
        แต่มันบอกได้แล้วว่า<strong>ควรเอาอะไรไปทดลองก่อน</strong>
        และบอกได้ว่า<strong>ควรลงทุนพัฒนาตรงไหน</strong></p>
      </div>
      <p class="tiny">ขอบคุณครับ · ยินดีรับคำถาม</p>
    """, note(
        "สรุปสำหรับการใช้งานจริงครับ ผมแบ่งเป็น 3 ช่อง",
        "ช่องแรก ใช้ได้ตอนนี้ คือใช้จัดลำดับความเสี่ยงของ candidate peptide เพื่อเลือกว่าจะเอาอะไรไปทดลองต่อ ตรงนี้โมเดลทำได้จริง มันจัด strong activator ขึ้นมาอยู่หัวตารางได้",
        "ช่องที่สอง อย่าใช้ทำสิ่งนี้ คืออย่าใช้ตัดสินความปลอดภัยเพื่อ clear การเข้าคน คุณภาพหลักฐานยังไม่พอ และที่ระดับโปรตีโอม วิธีง่าย ๆ ก็ให้ผลเท่ากัน",
        "ช่องที่สาม สิ่งที่ต้องการต่อ หนึ่งคือ mutational scan ชุดใหม่ สองคือ MHC class II predictor ที่ดีขึ้น ซึ่งเป็นคอขวดตัวจริง และสามคือข้อมูล PTM ที่วัด activation จริง",
        "ข้อความที่ผมอยากฝากไว้คือ การคัดกรอง off-target ด้วยคอมพิวเตอร์ยังไม่อยู่ในจุดที่แทนการทดลองได้ครับ แต่มันบอกได้แล้วว่าควรเอาอะไรไปทดลองก่อน และบอกได้ว่าควรลงทุนพัฒนาตรงไหน",
        "ขอบคุณครับ")))

    return shell("คัดกรอง off-target ก่อนถึงคนไข้", "".join(s))


# ===========================================================================
def main():
    fig2, fig7 = data_uri("fig4_benchmark.png"), data_uri("fig9_noncanonical.png")

    pub = public_deck()
    clin = clinical_deck().replace("__FIG2__", fig2).replace("__FIG7__", fig7)

    for name, html in (("TALK_PUBLIC.html", pub), ("TALK_CLINICAL.html", clin)):
        assert "__FIG" not in html, f"unreplaced placeholder in {name}"
        path = os.path.join(HERE, name)
        with open(path, "w") as fh:
            fh.write(html)
        n = html.count('<section class="slide">')
        print(f"wrote {name}  ({os.path.getsize(path)/1024:,.0f} KB, {n} slides)")


if __name__ == "__main__":
    main()
