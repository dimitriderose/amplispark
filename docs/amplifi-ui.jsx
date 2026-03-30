import { useState, useEffect } from "react";

const A = {
  bg: "#FAFAF8", surface: "#FFFFFF", surfaceAlt: "#F4F4F0",
  border: "#E8E8E4", borderLight: "#F0F0EC",
  text: "#1A1A2E", textSoft: "#64648C", textMuted: "#9898B0",
  indigo: "#5B5FF6", indigoLight: "#EDEDFE", indigoDark: "#4648C8",
  coral: "#FF6B6B", coralLight: "#FFF0F0",
  emerald: "#10B981", emeraldLight: "#ECFDF5",
  amber: "#F59E0B", amberLight: "#FFFBEB",
  violet: "#8B5CF6", violetLight: "#F5F3FF",
};

const PILLARS = {
  Educate: { color: A.indigo, bg: A.indigoLight, icon: "📚" },
  Engage: { color: A.coral, bg: A.coralLight, icon: "💬" },
  Promote: { color: A.amber, bg: A.amberLight, icon: "📣" },
  Connect: { color: A.emerald, bg: A.emeraldLight, icon: "🤝" },
};

const PLATFORMS = {
  Instagram: { color: "#E1306C", icon: "📷" },
  LinkedIn: { color: "#0A66C2", icon: "💼" },
  X: { color: "#1A1A2E", icon: "𝕏" },
  TikTok: { color: "#000000", icon: "🎵" },
  Facebook: { color: "#1877F2", icon: "📘" },
};

const NavBar = ({ screen, setScreen }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 24px", borderBottom: `1px solid ${A.border}`, background: A.surface, position: "sticky", top: 0, zIndex: 50 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 28, height: 28, borderRadius: 7, background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "white", fontWeight: 700 }}>A</div>
      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 17, fontWeight: 700, color: A.text, letterSpacing: -0.3 }}>Amplispark</span>
    </div>
    <div style={{ display: "flex", gap: 2 }}>
      {[["landing","Home"],["onboard","Onboard"],["brand","Brand"],["calendar","Calendar"],["detail","Content"],["video","Video"],["dashboard","Dashboard"]].map(([k,l]) => (
        <button key={k} onClick={() => setScreen(k)} style={{ padding: "5px 12px", borderRadius: 6, background: screen === k ? A.indigoLight : "transparent", border: "none", cursor: "pointer", fontSize: 12, fontFamily: "'IBM Plex Sans', sans-serif", color: screen === k ? A.indigo : A.textSoft, fontWeight: screen === k ? 600 : 400 }}>{l}</button>
      ))}
    </div>
  </div>
);

const PillarTag = ({ pillar, small }) => {
  const p = PILLARS[pillar]; if (!p) return null;
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: small ? "2px 6px" : "3px 10px", borderRadius: 20, background: p.bg, fontSize: small ? 10 : 11, fontFamily: "'JetBrains Mono', monospace", color: p.color, fontWeight: 500 }}><span style={{ fontSize: small ? 9 : 11 }}>{p.icon}</span>{pillar}</span>;
};

const PlatformBadge = ({ platform, small }) => {
  const p = PLATFORMS[platform]; if (!p) return null;
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: small ? "2px 5px" : "3px 8px", borderRadius: 4, background: `${p.color}10`, fontSize: small ? 9 : 11, fontFamily: "'IBM Plex Sans', sans-serif", color: p.color, fontWeight: 500 }}><span style={{ fontSize: small ? 10 : 12 }}>{p.icon}</span>{!small && platform}</span>;
};

const StreamingText = ({ text, speed = 20 }) => {
  const [shown, setShown] = useState(0);
  useEffect(() => { if (shown < text.length) { const t = setTimeout(() => setShown(shown + 1), speed); return () => clearTimeout(t); } }, [shown, text, speed]);
  return <span>{text.slice(0, shown)}{shown < text.length && <span style={{ display: "inline-block", width: 2, height: 14, background: A.indigo, marginLeft: 1, animation: "blink 0.8s step-end infinite" }} />}</span>;
};

// ─── Screen 1: Onboard ───────────────────────────────────────

const OnboardScreen = ({ onNext }) => {
  const [url, setUrl] = useState("");
  const [desc, setDesc] = useState("");
  const [noWeb, setNoWeb] = useState(false);
  const [uploads, setUploads] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [steps, setSteps] = useState([]);

  const allSteps = noWeb
    ? [{l:"Analyzing your description...",i:"📝"},{l:"Inferring brand personality",i:"🎨"},{l:"Identifying target audience",i:"👥"},{l:"Researching your market",i:"🔍"},{l:"Building brand profile",i:"✨"}]
    : [{l:"Crawling website...",i:"🌐"},{l:"Extracting brand colors",i:"🎨"},{l:"Analyzing tone of voice",i:"✍️"},{l:"Identifying target audience",i:"👥"},{l:"Scanning competitors",i:"🔍"},{l:"Building brand profile",i:"✨"}];

  const canGo = noWeb ? (desc.length >= 20) : (!!url && desc.length >= 20);

  const go = () => {
    setAnalyzing(true);
    allSteps.forEach((_, idx) => {
      setTimeout(() => {
        setSteps(p => [...p, allSteps[idx]]);
        setProgress(((idx+1)/allSteps.length)*100);
        if (idx === allSteps.length-1) setTimeout(onNext, 800);
      }, (idx+1)*900);
    });
  };

  if (analyzing) return (
    <div style={{ minHeight: "calc(100vh - 50px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}>
      <div style={{ maxWidth: 520, width: "100%", animation: "fadeUp 0.4s ease" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 22, fontWeight: 700, color: A.text, margin: "0 0 6px" }}>Building your brand profile</h2>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.textSoft, margin: 0 }}>{noWeb ? "Crafting your brand identity..." : `Analyzing ${url}...`}</p>
        </div>
        <div style={{ height: 4, background: A.surfaceAlt, borderRadius: 2, overflow: "hidden", marginBottom: 28 }}>
          <div style={{ height: "100%", width: `${progress}%`, background: `linear-gradient(90deg, ${A.indigo}, ${A.violet})`, borderRadius: 2, transition: "width 0.6s ease" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 8, background: i === steps.length-1 ? A.indigoLight : A.surface, border: `1px solid ${i === steps.length-1 ? A.indigo+"30" : A.borderLight}`, animation: "fadeUp 0.3s ease" }}>
              <span style={{ fontSize: 16 }}>{s.i}</span>
              <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: i === steps.length-1 ? A.indigo : A.textSoft, fontWeight: i === steps.length-1 ? 500 : 400 }}>{s.l}</span>
              {i < steps.length-1 && <span style={{ marginLeft: "auto", color: A.emerald, fontSize: 13 }}>✓</span>}
              {i === steps.length-1 && <span style={{ marginLeft: "auto", width: 14, height: 14, border: `2px solid ${A.indigo}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "calc(100vh - 50px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}>
      <div style={{ maxWidth: 520, width: "100%", animation: "fadeUp 0.5s ease" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{ display: "inline-flex", padding: "6px 14px", borderRadius: 20, background: A.indigoLight, marginBottom: 16 }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: A.indigo, fontWeight: 500 }}>✨ AI Creative Director</span>
          </div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 32, fontWeight: 700, color: A.text, margin: "0 0 8px", letterSpacing: -0.5 }}>What's your business?</h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.textSoft, margin: 0, lineHeight: 1.5 }}>
            {noWeb ? "Tell us about your business and we'll build your brand profile." : "Paste your URL and we'll build your brand profile in under a minute."}
          </p>
        </div>

        {!noWeb && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", gap: 8, padding: "4px 4px 4px 16px", background: A.surface, border: `2px solid ${url ? A.indigo : A.border}`, borderRadius: 12, transition: "border 0.2s", alignItems: "center" }}>
              <span style={{ color: A.textMuted, fontSize: 14 }}>🔗</span>
              <input type="text" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://yourbusiness.com"
                style={{ flex: 1, padding: "12px 0", border: "none", outline: "none", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.text, background: "transparent" }} />
              {url && <button onClick={() => setUrl("")} style={{ background: "none", border: "none", color: A.textMuted, cursor: "pointer", fontSize: 14, padding: "8px" }}>✕</button>}
            </div>
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 8 }}>
            {noWeb ? "Tell Us About Your Business" : "Describe Your Business"}
          </label>
          <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={noWeb ? 4 : 3}
            placeholder={noWeb ? "e.g. I run a mobile dog grooming van in Austin. I specialize in anxious rescue dogs and I'm trying to grow my Instagram to book more clients." : "e.g. Farm-to-table restaurant in Brooklyn. Seasonal menus, weekend brunch, private events."}
            style={{ width: "100%", padding: "13px 14px", background: A.surface, border: `2px solid ${desc ? A.indigo : A.border}`, borderRadius: 10, color: A.text, fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", outline: "none", boxSizing: "border-box", resize: "none", lineHeight: 1.6, transition: "border 0.2s" }} />
          <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textMuted, marginTop: 6, fontStyle: "italic" }}>
            {noWeb ? "Include what you do, who you serve, and what makes you different." : "A sentence or two is plenty. The AI will figure out the rest."}
          </div>
        </div>

        <div style={{ marginBottom: 24 }}>
          <div onClick={() => uploads.length < 3 && setUploads([...uploads, ["brand-guide.pdf","storefront.jpg","logo.png"][uploads.length] || "file.pdf"])}
            style={{ padding: uploads.length > 0 ? "10px 14px" : "16px 14px", borderRadius: 10, border: `1.5px dashed ${uploads.length > 0 ? A.indigo+"40" : A.border}`, background: uploads.length > 0 ? A.indigoLight+"60" : A.surfaceAlt, cursor: "pointer", textAlign: "center" }}>
            {uploads.length === 0 ? (
              <>
                <div style={{ fontSize: 18, marginBottom: 4 }}>📎</div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>Have brand assets? <span style={{ color: A.indigo, fontWeight: 500 }}>Drop photos or docs here</span></div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.textMuted, marginTop: 3 }}>Brand guides, menus, product photos, logos · Optional</div>
              </>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {uploads.map((f, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 6, background: A.surface, border: `1px solid ${A.border}`, textAlign: "left" }}>
                    <span style={{ fontSize: 14 }}>{f.endsWith(".pdf") ? "📄" : "🖼️"}</span>
                    <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, flex: 1 }}>{f}</span>
                    <button onClick={e => { e.stopPropagation(); setUploads(uploads.filter((_,idx) => idx!==i)); }} style={{ background: "none", border: "none", color: A.textMuted, cursor: "pointer", fontSize: 12 }}>✕</button>
                  </div>
                ))}
                {uploads.length < 3 && <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.indigo, marginTop: 2 }}>+ Add more files</div>}
              </div>
            )}
          </div>
        </div>

        <button onClick={go} disabled={!canGo}
          style={{ width: "100%", padding: "14px", background: canGo ? `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})` : A.surfaceAlt, border: "none", borderRadius: 10, cursor: canGo ? "pointer" : "default", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, color: canGo ? "white" : A.textMuted, boxShadow: canGo ? `0 4px 16px ${A.indigo}30` : "none" }}>
          {noWeb ? "Build My Brand Profile →" : "Analyze My Brand →"}
        </button>
        <div style={{ textAlign: "center", marginTop: 12 }}>
          <button onClick={() => { setNoWeb(!noWeb); setUrl(""); }} style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textMuted }}>
            {noWeb ? <>Have a website? <span style={{ color: A.indigo, textDecoration: "underline" }}>Paste your URL instead →</span></> : <>No website? <span style={{ color: A.indigo, textDecoration: "underline" }}>Describe your business instead →</span></>}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Screen 2: Brand Profile ─────────────────────────────────

const BrandProfileScreen = ({ onNext }) => {
  const [dir, setDir] = useState("caption");
  return (
    <div style={{ padding: "28px 24px", maxWidth: 720, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 24, fontWeight: 700, color: A.text, margin: "0 0 4px" }}>Brand Profile</h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.textSoft, margin: 0 }}>Your AI-extracted brand identity. Edit anything.</p>
        </div>
        <button onClick={onNext} style={{ padding: "9px 20px", borderRadius: 8, background: A.indigo, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Generate Calendar →</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>Brand Identity</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <div style={{ width: 48, height: 48, borderRadius: 10, background: "linear-gradient(135deg, #2D5A3D, #D4A853)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>🌿</div>
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 17, fontWeight: 700, color: A.text }}>Verde Kitchen</div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>Farm-to-table restaurant · Brooklyn, NY</div>
              </div>
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textMuted, marginBottom: 6 }}>Brand Colors</div>
              <div style={{ display: "flex", gap: 6 }}>
                {["#2D5A3D","#D4A853","#F5F0E8","#1A1A2E","#8B6F4E"].map((c,i) => <div key={i} style={{ width: 32, height: 32, borderRadius: 6, background: c, border: `1px solid ${A.border}` }} />)}
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textMuted, marginBottom: 6 }}>Voice & Tone</div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {["Warm","Earthy","Knowledgeable","Inviting","Seasonal"].map(v => <span key={v} style={{ padding: "3px 10px", borderRadius: 14, background: A.surfaceAlt, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft, border: `1px solid ${A.borderLight}` }}>{v}</span>)}
              </div>
            </div>
          </div>
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>Target Audience</div>
            {[{l:"Health-conscious foodies",p:40},{l:"Local Brooklyn residents",p:30},{l:"Date-night couples",p:20},{l:"Corporate lunch groups",p:10}].map((a,i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text }}>{a.l}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textMuted }}>{a.p}%</span>
                </div>
                <div style={{ height: 3, background: A.surfaceAlt, borderRadius: 2, overflow: "hidden" }}><div style={{ height: "100%", width: `${a.p}%`, background: A.indigo, borderRadius: 2 }} /></div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ padding: 4, borderRadius: 10, background: A.surfaceAlt, display: "flex", gap: 2 }}>
            {[["caption","✍️ Caption Style"],["image","🎨 Image Style"]].map(([k,l]) => (
              <button key={k} onClick={() => setDir(k)} style={{ flex: 1, padding: 8, borderRadius: 8, background: dir===k ? A.surface : "transparent", border: "none", cursor: "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 500, color: dir===k ? A.text : A.textSoft, boxShadow: dir===k ? `0 1px 4px ${A.border}` : "none" }}>{l}</button>
            ))}
          </div>
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.indigo}20`, flex: 1 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.indigo, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>{dir==="caption" ? "Caption Style Directive" : "Image Style Directive"}</div>
            <div style={{ padding: 14, borderRadius: 8, background: A.surfaceAlt, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12.5, color: A.text, lineHeight: 1.7, marginBottom: 12, border: `1px solid ${A.borderLight}` }}>
              {dir==="caption" ? "Write as a passionate chef and local food advocate. Use warm, conversational language that makes readers feel like insiders. Reference seasonal ingredients by name. Keep captions under 150 words for Instagram, longer storytelling for LinkedIn. Always end with a question or call to action. Use 3-5 relevant hashtags." : "Natural light, overhead and 45° angles. Rustic wooden surfaces with linen textures. Muted earth tones — sage, terracotta, cream. Fresh herbs and raw ingredients as props. Never sterile or overly styled. Mood: morning farmers market meets candlelit dinner."}
            </div>
            {dir==="caption" ? <button style={{ padding: "6px 14px", borderRadius: 6, background: "transparent", border: `1px solid ${A.border}`, cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft }}>✏️ Edit directive</button>
            : <div style={{ display: "flex", gap: 6 }}>{["🌿 Rustic","☀️ Natural light","🍽️ Overhead"].map(s => <span key={s} style={{ padding: "4px 10px", borderRadius: 14, background: A.emeraldLight, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.emerald }}>{s}</span>)}</div>}
          </div>
          <div style={{ padding: "16px 20px", borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>Detected Competitors</div>
            {[{n:"Olmsted",f:"5x/week",d:"Heavy on Reels & Stories"},{n:"Le Crocodile",f:"3x/week",d:"Editorial photography"},{n:"Lilia",f:"4x/week",d:"UGC reposts + events"}].map((c,i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: i<2 ? `1px solid ${A.borderLight}` : "none" }}>
                <div>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, fontWeight: 500 }}>{c.n}</span>
                  <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.textMuted, marginTop: 1 }}>{c.d}</div>
                </div>
                <span style={{ padding: "2px 8px", borderRadius: 10, background: A.surfaceAlt, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textSoft }}>{c.f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Screen 3: Calendar ──────────────────────────────────────

const CalendarScreen = ({ onDetail }) => {
  const [gen, setGen] = useState(true);
  const [vis, setVis] = useState(0);
  const days = [
    {day:"Mon",date:"Feb 23",pillar:"Educate",platform:"Instagram",title:"Behind the Menu: Winter Root Vegetables"},
    {day:"Tue",date:"Feb 24",pillar:"Promote",platform:"Instagram",title:"Valentine's prix fixe — last 3 tables"},
    {day:"Wed",date:"Feb 25",pillar:"Engage",platform:"X",title:"Poll: Butternut squash or sweet potato ravioli?"},
    {day:"Thu",date:"Feb 26",pillar:"Connect",platform:"LinkedIn",title:"Our farmer partners: Hudson Valley Harvest"},
    {day:"Fri",date:"Feb 27",pillar:"Promote",platform:"Instagram",title:"Friday night specials — reserve now"},
    {day:"Sat",date:"Feb 28",pillar:"Engage",platform:"TikTok",title:"60-sec: How we make fresh pasta daily"},
    {day:"Sun",date:"Mar 1",pillar:"Educate",platform:"Facebook",title:"Sunday brunch guide: what to order"},
  ];
  useEffect(() => { if (gen && vis < days.length) { const t = setTimeout(() => setVis(v=>v+1), 600); return () => clearTimeout(t); } if (vis >= days.length) setGen(false); }, [gen, vis]);
  const plats = ["Instagram","LinkedIn","X","TikTok","Facebook"];
  const [sel, setSel] = useState(["Instagram","LinkedIn","X"]);

  return (
    <div style={{ padding: "28px 24px", maxWidth: 760, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 24, fontWeight: 700, color: A.text, margin: "0 0 4px" }}>Content Calendar</h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.textSoft, margin: 0 }}>{gen ? `Generating your week — ${vis} of ${days.length} posts ready` : "Week of Feb 23 – Mar 1 · Verde Kitchen"}</p>
        </div>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: "linear-gradient(135deg, #2D5A3D, #D4A853)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>🌿</div>
      </div>
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4 }}>
          {plats.map(p => <button key={p} onClick={() => setSel(prev => prev.includes(p) ? prev.filter(x=>x!==p) : [...prev,p])} style={{ padding: "5px 10px", borderRadius: 6, background: sel.includes(p) ? `${PLATFORMS[p].color}12` : A.surfaceAlt, border: `1px solid ${sel.includes(p) ? PLATFORMS[p].color+"30" : A.border}`, cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: sel.includes(p) ? PLATFORMS[p].color : A.textMuted, fontWeight: sel.includes(p) ? 500 : 400 }}>{PLATFORMS[p].icon} {p}</button>)}
        </div>
        <div style={{ padding: "5px 12px", borderRadius: 6, background: A.amberLight, border: `1px solid ${A.amber}20`, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.amber }}>📅 Event: Valentine's prix fixe (Tue)</div>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>{Object.keys(PILLARS).map(p => <PillarTag key={p} pillar={p} small />)}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {days.slice(0,vis).map((d,i) => (
          <div key={i} onClick={() => !gen && onDetail(d)} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", background: A.surface, border: `1px solid ${A.border}`, borderRadius: 10, cursor: gen ? "default" : "pointer", animation: "fadeUp 0.3s ease" }}>
            <div style={{ width: 44, textAlign: "center", flexShrink: 0 }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, textTransform: "uppercase" }}>{d.day}</div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: A.text }}>{d.date.split(" ")[1]}</div>
            </div>
            <div style={{ width: 1, height: 32, background: A.border, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 500, color: A.text, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.title}</div>
              <div style={{ display: "flex", gap: 6 }}><PillarTag pillar={d.pillar} small /><PlatformBadge platform={d.platform} small /></div>
            </div>
            <div style={{ padding: "4px 10px", borderRadius: 14, background: A.emeraldLight, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.emerald, fontWeight: 500 }}>Ready</div>
            <span style={{ color: A.textMuted, fontSize: 14 }}>→</span>
          </div>
        ))}
        {gen && <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderRadius: 10, border: `1px dashed ${A.indigo}30`, background: A.indigoLight, animation: "fadeUp 0.3s ease" }}>
          <span style={{ display: "inline-block", width: 16, height: 16, border: `2px solid ${A.indigo}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.indigo }}>Generating {days[vis]?.day || ""}...</span>
          <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textMuted }}>{vis}/{days.length}</span>
        </div>}
      </div>
      {gen && <div style={{ marginTop: 12 }}><div style={{ height: 3, background: A.surfaceAlt, borderRadius: 2, overflow: "hidden" }}><div style={{ height: "100%", width: `${(vis/days.length)*100}%`, background: `linear-gradient(90deg, ${A.indigo}, ${A.violet})`, borderRadius: 2, transition: "width 0.5s ease" }} /></div></div>}
    </div>
  );
};

// ─── Screen 4: Content Detail ────────────────────────────────

const ContentDetailScreen = ({ onBack }) => {
  const [mode, setMode] = useState("ai");
  const [vid, setVid] = useState(false);
  const caption = "There's something honest about a parsnip. No pretense, no flash — just quiet sweetness that deepens with every minute in a hot oven.\n\nThis week we're letting winter roots take center stage. Roasted carrots with carrot-top chimichurri. Celeriac purée under seared scallops. Turnip gratin that'll make you rethink everything.\n\nWhat's the root vegetable you think deserves more love? Tell us below 👇\n\n#FarmToTable #SeasonalCooking #WinterProduce #BrooklynEats #VerdeKitchen";

  return (
    <div style={{ padding: "28px 24px", maxWidth: 720, margin: "0 auto" }}>
      <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 16, background: "none", border: "none", cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>← Back to Calendar</button>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{ width: 44, textAlign: "center" }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, textTransform: "uppercase" }}>Mon</div>
          <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 18, fontWeight: 700, color: A.text }}>23</div>
        </div>
        <div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 20, fontWeight: 700, color: A.text, margin: 0 }}>Behind the Menu: Winter Root Vegetables</h1>
          <div style={{ display: "flex", gap: 6, marginTop: 4 }}><PillarTag pillar="Educate" small /><PlatformBadge platform="Instagram" small /></div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <div style={{ display: "flex", gap: 2, padding: 3, marginBottom: 12, background: A.surfaceAlt, borderRadius: 8 }}>
            {[["ai","AI Generated"],["byop","Your Photo"]].map(([k,l]) => <button key={k} onClick={() => setMode(k)} style={{ flex: 1, padding: 6, borderRadius: 6, background: mode===k ? A.surface : "transparent", border: "none", cursor: "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: 500, color: mode===k ? A.text : A.textSoft, boxShadow: mode===k ? `0 1px 3px ${A.border}` : "none" }}>{l}</button>)}
          </div>
          <div style={{ width: "100%", aspectRatio: "1", borderRadius: 12, background: mode==="ai" ? "linear-gradient(135deg, #2D5A3D20, #D4A85320, #F5F0E840)" : A.surfaceAlt, border: `1px solid ${A.border}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative" }}>
            {mode==="ai" ? <>
              <div style={{ fontSize: 48, marginBottom: 8 }}>🥕</div>
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, textAlign: "center", padding: "0 20px" }}>AI-generated image of winter root vegetables on rustic wooden surface</div>
              <div style={{ position: "absolute", bottom: 12, right: 12, padding: "4px 10px", borderRadius: 6, background: `${A.indigo}15`, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.indigo }}>Gemini Imagen</div>
            </> : <>
              <div style={{ fontSize: 32, marginBottom: 8, color: A.textMuted }}>📷</div>
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textMuted }}>Drop your photo here</div>
              <div style={{ marginTop: 8, padding: "6px 14px", borderRadius: 6, background: A.surface, border: `1px solid ${A.border}`, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft, cursor: "pointer" }}>Browse files</div>
            </>}
          </div>
          <button onClick={() => setVid(!vid)} style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, padding: "8px 14px", borderRadius: 8, width: "100%", background: vid ? A.violetLight : A.surfaceAlt, border: `1px solid ${vid ? A.violet+"30" : A.border}`, cursor: "pointer" }}>
            <span style={{ fontSize: 14 }}>🎬</span>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 500, color: vid ? A.violet : A.textSoft }}>{vid ? "Video generation enabled" : "Generate video with Veo"}</span>
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ padding: 18, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`, flex: 1 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>Caption · Instagram</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.text, lineHeight: 1.7 }}><StreamingText text={caption} speed={12} /></div>
          </div>
          <div style={{ padding: 14, borderRadius: 10, background: A.surfaceAlt, border: `1px solid ${A.borderLight}` }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 8 }}>Also generating for</div>
            <div style={{ display: "flex", gap: 4 }}>{["LinkedIn","X"].map(p => <PlatformBadge key={p} platform={p} />)}</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button style={{ flex: 1, padding: 10, borderRadius: 8, background: A.indigo, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Regenerate Caption</button>
            <button style={{ flex: 1, padding: 10, borderRadius: 8, background: A.surface, border: `1px solid ${A.border}`, fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 500, color: A.text, cursor: "pointer" }}>Edit Manually</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Screen 5: Dashboard ─────────────────────────────────────

const DashboardScreen = ({ onScreen }) => {
  const plans = [{week:"Feb 23 – Mar 1",status:"Active",posts:7,plat:3},{week:"Feb 16 – Feb 22",status:"Published",posts:7,plat:2},{week:"Feb 9 – Feb 15",status:"Published",posts:5,plat:2}];
  return (
    <div style={{ padding: "28px 24px", maxWidth: 760, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 24, fontWeight: 700, color: A.text, margin: "0 0 4px" }}>Dashboard</h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.textSoft, margin: 0 }}>Welcome back, Verde Kitchen</p>
        </div>
        <button onClick={() => onScreen("onboard")} style={{ padding: "10px 20px", borderRadius: 8, background: `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})`, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}><span>⚡</span> Quick Generate</button>
      </div>

      {/* Streak + next post */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1, padding: "14px 18px", borderRadius: 10, background: `linear-gradient(135deg, ${A.indigoLight}, ${A.violetLight})`, border: `1px solid ${A.indigo}15`, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 24 }}>🔥</span>
          <div>
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: A.text }}>3-week streak!</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft }}>You've posted consistently for 3 weeks. Keep it going.</div>
          </div>
        </div>
        <div style={{ padding: "14px 18px", borderRadius: 10, background: A.surface, border: `1px solid ${A.border}`, display: "flex", alignItems: "center", gap: 10, minWidth: 200 }}>
          <span style={{ fontSize: 20 }}>📤</span>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1, textTransform: "uppercase" }}>Next Post</div>
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: A.text }}>Tomorrow, 9:00 AM</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.textSoft }}>Winter Root Vegetables</div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20 }}>
        <div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>Content Plans</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {plans.map((p,i) => (
              <div key={i} onClick={() => onScreen("calendar")} style={{ padding: "16px 18px", borderRadius: 10, background: A.surface, border: `1px solid ${i===0 ? A.indigo+"30" : A.border}`, cursor: "pointer", animation: `fadeUp 0.3s ${i*0.08}s both` }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, color: A.text }}>{p.week}</div>
                  <span style={{ padding: "3px 10px", borderRadius: 14, background: p.status==="Active" ? A.indigoLight : A.emeraldLight, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: p.status==="Active" ? A.indigo : A.emerald, fontWeight: 500 }}>{p.status}</span>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>📝 {p.posts} posts</span>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>📱 {p.plat} platforms</span>
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 16 }}>
            {[{l:"Posts Generated",v:"19",i:"📝"},{l:"Platforms Active",v:"3",i:"📱"},{l:"Weeks Planned",v:"3",i:"📅"}].map((s,i) => (
              <div key={i} style={{ padding: 14, borderRadius: 10, background: A.surface, border: `1px solid ${A.border}`, textAlign: "center" }}>
                <div style={{ fontSize: 18, marginBottom: 4 }}>{s.i}</div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 22, fontWeight: 700, color: A.text }}>{s.v}</div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.textSoft, marginTop: 2 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ padding: 20, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`, textAlign: "center" }}>
            <div style={{ width: 52, height: 52, borderRadius: 12, margin: "0 auto 10px", background: "linear-gradient(135deg, #2D5A3D, #D4A853)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>🌿</div>
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: A.text }}>Verde Kitchen</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft, marginTop: 2 }}>Farm-to-table · Brooklyn</div>
            <div style={{ display: "flex", gap: 3, justifyContent: "center", marginTop: 10 }}>
              {["#2D5A3D","#D4A853","#F5F0E8"].map((c,i) => <div key={i} style={{ width: 16, height: 16, borderRadius: 4, background: c, border: `1px solid ${A.border}` }} />)}
            </div>
            <button onClick={() => onScreen("brand")} style={{ marginTop: 12, padding: "6px 16px", borderRadius: 6, background: "transparent", border: `1px solid ${A.border}`, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft, cursor: "pointer" }}>Edit Profile</button>
          </div>
          <div style={{ padding: 16, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>This Week's Mix</div>
            <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", marginBottom: 10 }}>
              <div style={{ width: "30%", background: A.indigo }} />
              <div style={{ width: "25%", background: A.coral }} />
              <div style={{ width: "30%", background: A.amber }} />
              <div style={{ width: "15%", background: A.emerald }} />
            </div>
            {Object.entries(PILLARS).map(([name,p]) => (
              <div key={name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "3px 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.text }}>{name}</span>
                </div>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textMuted }}>{name==="Connect" ? 1 : 2}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[{l:"Generate next week",i:"📅",a:"calendar"},{l:"Edit brand profile",i:"🎨",a:"brand"},{l:"Export all content",i:"📤",a:null}].map((q,i) => (
              <button key={i} onClick={() => q.a && onScreen(q.a)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 8, background: A.surface, border: `1px solid ${A.border}`, cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, textAlign: "left", width: "100%" }}>
                <span style={{ fontSize: 14 }}>{q.i}</span>{q.l}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Landing Page ────────────────────────────────────────────

const LandingPage = ({ onStart }) => {
  return (
    <div style={{ background: A.bg }}>
      {/* Hero */}
      <div style={{ padding: "80px 24px 60px", textAlign: "center", position: "relative", overflow: "hidden" }}>
        {/* Background gradient orbs */}
        <div style={{ position: "absolute", top: -120, right: -80, width: 400, height: 400, borderRadius: "50%", background: `radial-gradient(circle, ${A.indigo}08, transparent 70%)`, pointerEvents: "none" }} />
        <div style={{ position: "absolute", bottom: -100, left: -60, width: 350, height: 350, borderRadius: "50%", background: `radial-gradient(circle, ${A.violet}06, transparent 70%)`, pointerEvents: "none" }} />

        <div style={{ position: "relative", maxWidth: 640, margin: "0 auto" }}>
          <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: 20, background: A.indigoLight, marginBottom: 20, animation: "fadeUp 0.5s ease" }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: A.indigo, fontWeight: 500 }}>✨ AI-Powered Social Media</span>
          </div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 48, fontWeight: 700, color: A.text, margin: "0 0 16px", letterSpacing: -1.5, lineHeight: 1.1, animation: "fadeUp 0.5s 0.1s both" }}>
            Your entire week of content.
            <br /><span style={{ background: `linear-gradient(135deg, ${A.indigo}, ${A.violet})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>One click.</span>
          </h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 18, color: A.textSoft, margin: "0 0 32px", lineHeight: 1.6, maxWidth: 480, marginLeft: "auto", marginRight: "auto", animation: "fadeUp 0.5s 0.2s both" }}>
            Amplispark is your AI creative director. Paste your URL, get a full week of captions, images, and video — tailored to your brand, across every platform.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", animation: "fadeUp 0.5s 0.3s both" }}>
            <button onClick={onStart} style={{ padding: "14px 32px", borderRadius: 10, background: `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})`, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600, cursor: "pointer", boxShadow: `0 4px 20px ${A.indigo}30`, transition: "transform 0.15s", letterSpacing: 0.2 }}>
              Get Started Free →
            </button>
            <button style={{ padding: "14px 24px", borderRadius: 10, background: A.surface, border: `1px solid ${A.border}`, color: A.text, fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 500, cursor: "pointer" }}>
              Watch Demo
            </button>
          </div>
        </div>

        {/* Product preview */}
        <div style={{ maxWidth: 700, margin: "48px auto 0", padding: "16px", background: A.surface, borderRadius: 16, border: `1px solid ${A.border}`, boxShadow: `0 8px 40px ${A.indigo}08`, animation: "fadeUp 0.6s 0.4s both" }}>
          <div style={{ borderRadius: 10, background: A.surfaceAlt, padding: "20px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={{ width: 24, height: 24, borderRadius: 6, background: "linear-gradient(135deg, #2D5A3D, #D4A853)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11 }}>🌿</div>
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: A.text }}>Verde Kitchen</span>
              <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft }}>· Week of Feb 23</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[
                { day: "Mon", title: "Behind the Menu: Winter Root Vegetables", pillar: "Educate", platform: "Instagram" },
                { day: "Tue", title: "Valentine's prix fixe — last 3 tables", pillar: "Promote", platform: "Instagram" },
                { day: "Wed", title: "Poll: Butternut squash or sweet potato?", pillar: "Engage", platform: "X" },
              ].map((d, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: A.surface, borderRadius: 8, border: `1px solid ${A.borderLight}`, animation: `fadeUp 0.3s ${0.5 + i * 0.1}s both` }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textMuted, width: 28 }}>{d.day}</span>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, flex: 1 }}>{d.title}</span>
                  <PillarTag pillar={d.pillar} small />
                </div>
              ))}
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textMuted, textAlign: "center", padding: "4px 0" }}>+ 4 more days...</div>
            </div>
          </div>
        </div>
      </div>

      {/* How it works */}
      <div style={{ padding: "60px 24px", maxWidth: 760, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 28, fontWeight: 700, color: A.text, margin: "0 0 8px", letterSpacing: -0.5 }}>Three steps. Entire week handled.</h2>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.textSoft, margin: 0 }}>No briefs, no templates, no endless back-and-forth.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
          {[
            { step: "01", icon: "🔗", title: "Paste your URL", desc: "Or describe your business. Amplispark crawls your site, extracts your brand identity, colors, tone, and audience." },
            { step: "02", icon: "🧠", title: "AI builds your brand", desc: "Get an editable brand profile with caption and image style directives. Every piece of content stays on-brand." },
            { step: "03", icon: "📅", title: "Get your week", desc: "A full calendar of platform-specific content streams in live. Captions, images, video — all ready to post." },
          ].map((s, i) => (
            <div key={i} style={{ padding: "28px 24px", borderRadius: 14, background: A.surface, border: `1px solid ${A.border}`, position: "relative", animation: `fadeUp 0.4s ${i * 0.12}s both` }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 32, fontWeight: 700, color: A.indigoLight, position: "absolute", top: 16, right: 20 }}>{s.step}</div>
              <div style={{ fontSize: 28, marginBottom: 12 }}>{s.icon}</div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 16, fontWeight: 600, color: A.text, marginBottom: 6 }}>{s.title}</div>
              <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 13, color: A.textSoft, lineHeight: 1.6 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Features */}
      <div style={{ padding: "40px 24px 60px", maxWidth: 760, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 28, fontWeight: 700, color: A.text, margin: "0 0 8px", letterSpacing: -0.5 }}>Built for real businesses</h2>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.textSoft, margin: 0 }}>Not another generic content tool.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {[
            { icon: "🎨", title: "Brand-aware AI", desc: "Every caption and image matches your actual brand identity — colors, tone, audience." },
            { icon: "📱", title: "Multi-platform", desc: "Instagram, LinkedIn, X, TikTok, Facebook. One idea, adapted for each platform's format." },
            { icon: "📷", title: "Bring your own photos", desc: "Upload your product photos and get AI-written captions tailored specifically to each image." },
            { icon: "🎬", title: "AI video with Veo", desc: "Generate short-form video from your content plan. No filming, no editing, no equipment." },
            { icon: "📚", title: "Smart content pillars", desc: "Educate, Engage, Promote, Connect — automatic content mix so you never post the same type twice." },
            { icon: "📅", title: "Event-aware calendar", desc: "Tell Amplispark about your real events — launches, holidays, promotions — and content adapts around them." },
          ].map((f, i) => (
            <div key={i} style={{ display: "flex", gap: 14, padding: "18px 20px", borderRadius: 12, background: A.surface, border: `1px solid ${A.border}` }}>
              <div style={{ fontSize: 22, flexShrink: 0, marginTop: 2 }}>{f.icon}</div>
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, color: A.text, marginBottom: 3 }}>{f.title}</div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, lineHeight: 1.5 }}>{f.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Social proof placeholder */}
      <div style={{ padding: "40px 24px", maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
        <div style={{ padding: "32px 28px", borderRadius: 14, background: A.surface, border: `1px solid ${A.border}` }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>💬</div>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.text, lineHeight: 1.7, fontStyle: "italic", margin: "0 0 12px" }}>
            "I used to spend 4 hours every Sunday planning social media. Amplispark does it in 2 minutes and the content is better than what I was writing."
          </p>
          <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: A.text }}>Sarah Chen</div>
          <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft }}>Owner, Verde Kitchen · Brooklyn, NY</div>
        </div>
      </div>

      {/* CTA footer */}
      <div style={{ padding: "60px 24px 80px", textAlign: "center" }}>
        <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 28, fontWeight: 700, color: A.text, margin: "0 0 8px", letterSpacing: -0.5 }}>Stop dreading social media.</h2>
        <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 15, color: A.textSoft, margin: "0 0 24px" }}>Your first week of content is free. No credit card required.</p>
        <button onClick={onStart} style={{ padding: "14px 36px", borderRadius: 10, background: `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})`, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600, cursor: "pointer", boxShadow: `0 4px 20px ${A.indigo}30` }}>
          Get Started Free →
        </button>
      </div>
    </div>
  );
};

// ─── Screen 7: Video Repurposing (P2 Sprint 7+, §12.1.12) ──

const VideoRepurposeScreen = ({ onBack }) => {
  const [phase, setPhase] = useState("upload"); // upload | confirm | processing | results
  const [progress, setProgress] = useState(0);
  const [activeClip, setActiveClip] = useState(0);
  const [editingCaption, setEditingCaption] = useState(false);

  const fileInfo = { name: "startup-tips-raw.mp4", size: "287 MB", duration: "4:32", resolution: "1920×1080" };

  const processingSteps = [
    { l: "Uploading video...", i: "📤" },
    { l: "Extracting audio track", i: "🎵" },
    { l: "Transcribing speech", i: "📝" },
    { l: "Analyzing for highlights", i: "🔍" },
    { l: "Extracting clips", i: "✂️" },
    { l: "Adding captions", i: "💬" },
    { l: "Formatting for platforms", i: "📱" },
  ];
  const [steps, setSteps] = useState([]);

  const startProcessing = () => {
    setPhase("processing");
    processingSteps.forEach((_, idx) => {
      setTimeout(() => {
        setSteps(p => [...p, processingSteps[idx]]);
        setProgress(Math.round(((idx + 1) / processingSteps.length) * 100));
      }, (idx + 1) * 800);
    });
    setTimeout(() => setPhase("results"), processingSteps.length * 800 + 600);
  };

  const platformLimits = { "Reels": 2200, "LinkedIn": 3000, "YouTube Shorts": 5000 };

  const clips = [
    { platform: "Reels", platformIcon: "📷", platformColor: "#E1306C", duration: "0:28", aspect: "9:16", hook: "The biggest mistake I see new founders make...", caption: "Stop making this one mistake that's killing your growth. Most founders don't realize it until year two — but by then you've already lost momentum.\n\nHere's what to do instead 👇\n\n#StartupLife #FounderTips #SmallBusiness #GrowthHacks", start: "1:42", end: "2:10" },
    { platform: "LinkedIn", platformIcon: "💼", platformColor: "#0A66C2", duration: "0:45", aspect: "1:1", hook: "Three years ago I almost shut down the business...", caption: "Three years ago, I was ready to close the doors.\n\nNot because of revenue. Not because of competition. Because I was doing everything myself and burning out.\n\nThe turning point? Learning to delegate before I felt ready.\n\nWhat's the hardest lesson you've learned as a founder?", start: "3:15", end: "4:00" },
    { platform: "YouTube Shorts", platformIcon: "▶️", platformColor: "#FF0000", duration: "0:18", aspect: "9:16", hook: "Here's the one metric that actually matters...", caption: "Forget followers. Forget likes. The ONE metric that predicts whether your business survives?\n\nCustomer retention rate.\n\nIf people come back, everything else follows. If they don't, no amount of marketing will save you.", start: "0:22", end: "0:40" },
  ];
  const c = clips[activeClip];
  const charCount = c.caption.length;
  const charLimit = platformLimits[c.platform];

  return (
    <div style={{ padding: "28px 24px", maxWidth: 760, margin: "0 auto" }}>
      <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 16, background: "none", border: "none", cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft }}>← Back to Content</button>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: `linear-gradient(135deg, ${A.violet}20, ${A.indigo}20)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>🎬</div>
        <div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 20, fontWeight: 700, color: A.text, margin: 0 }}>Video Repurposing</h1>
          <p style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, margin: 0 }}>Turn your raw video into platform-ready clips</p>
        </div>
      </div>

      {/* Upload Phase */}
      {phase === "upload" && (
        <div style={{ animation: "fadeUp 0.4s ease both" }}>
          <div onClick={() => setPhase("confirm")} style={{
            padding: "48px 24px", borderRadius: 16, cursor: "pointer", textAlign: "center",
            border: `2px dashed ${A.border}`, background: A.surfaceAlt,
            transition: "border-color 0.2s, background 0.2s",
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = A.indigo; e.currentTarget.style.background = `${A.indigoLight}`; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = A.border; e.currentTarget.style.background = A.surfaceAlt; }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📹</div>
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600, color: A.text, marginBottom: 4 }}>Drop your video here</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, marginBottom: 16 }}>or click to browse · MP4 or MOV · up to 5 min / 500MB</div>
            <div style={{ display: "inline-block", padding: "8px 20px", borderRadius: 8, background: A.indigo, color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600 }}>Choose File</div>
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
            {[{ icon: "✂️", label: "Auto-clips", desc: "AI finds the best moments" }, { icon: "💬", label: "Captions", desc: "Auto-generated subtitles" }, { icon: "📱", label: "Multi-format", desc: "Reels, LinkedIn, Shorts" }].map((f, i) => (
              <div key={i} style={{ flex: 1, padding: "14px", borderRadius: 10, background: A.surface, border: `1px solid ${A.borderLight}`, textAlign: "center" }}>
                <div style={{ fontSize: 20, marginBottom: 6 }}>{f.icon}</div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, color: A.text }}>{f.label}</div>
                <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: A.textSoft, marginTop: 2 }}>{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File Confirmation Phase */}
      {phase === "confirm" && (
        <div style={{ animation: "fadeUp 0.4s ease both" }}>
          <div style={{ padding: "24px", borderRadius: 16, background: A.surface, border: `1px solid ${A.border}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              {/* Thumbnail placeholder */}
              <div style={{ width: 80, height: 56, borderRadius: 8, background: `linear-gradient(135deg, ${A.text}12, ${A.text}06)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, border: `1px solid ${A.borderLight}` }}>
                <span style={{ fontSize: 24 }}>🎞️</span>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, color: A.text }}>{fileInfo.name}</div>
                <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                  {[
                    { l: "Size", v: fileInfo.size },
                    { l: "Duration", v: fileInfo.duration },
                    { l: "Resolution", v: fileInfo.resolution },
                  ].map((m, i) => (
                    <div key={i}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted }}>{m.l}: </span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.text, fontWeight: 500 }}>{m.v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={() => setPhase("upload")} style={{ padding: "4px 10px", borderRadius: 6, background: "none", border: `1px solid ${A.border}`, cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft }}>Change</button>
            </div>
            <div style={{ margin: "16px 0", height: 1, background: A.border }} />
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, marginBottom: 16 }}>Amplispark will extract 2–3 highlight clips, add captions, and format them for Reels, LinkedIn, and YouTube Shorts.</div>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => setPhase("upload")} style={{ flex: 1, padding: "12px", borderRadius: 10, background: A.surface, border: `1px solid ${A.border}`, fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 500, color: A.text, cursor: "pointer" }}>Cancel</button>
              <button onClick={startProcessing} style={{ flex: 2, padding: "12px", borderRadius: 10, background: `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})`, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer", boxShadow: `0 2px 12px ${A.indigo}25` }}>Start Processing →</button>
            </div>
          </div>
        </div>
      )}

      {/* Processing Phase */}
      {phase === "processing" && (
        <div style={{ animation: "fadeUp 0.4s ease both" }}>
          <div style={{ padding: "32px 24px", borderRadius: 16, background: A.surface, border: `1px solid ${A.border}`, textAlign: "center" }}>
            <div style={{ width: 48, height: 48, margin: "0 auto 16px", borderRadius: "50%", border: `3px solid ${A.borderLight}`, borderTopColor: A.indigo, animation: "spin 1s linear infinite" }} />
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 16, fontWeight: 600, color: A.text, marginBottom: 4 }}>Analyzing your video...</div>
            <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.textSoft, marginBottom: 6 }}>{fileInfo.name} · {fileInfo.duration}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: A.indigo, marginBottom: 16 }}>{progress}% complete · ~{Math.max(1, Math.round((100 - progress) * 0.45))}s remaining</div>
            <div style={{ width: "100%", height: 6, borderRadius: 3, background: A.surfaceAlt, marginBottom: 24 }}>
              <div style={{ width: `${progress}%`, height: "100%", borderRadius: 3, background: `linear-gradient(90deg, ${A.indigo}, ${A.violet})`, transition: "width 0.4s ease" }} />
            </div>
            <div style={{ textAlign: "left" }}>
              {steps.map((st, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", animation: `fadeUp 0.3s ${i * 0.05}s both` }}>
                  <span style={{ fontSize: 14 }}>{st.i}</span>
                  <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: i === steps.length - 1 ? A.text : A.textSoft, fontWeight: i === steps.length - 1 ? 500 : 400 }}>{st.l}</span>
                  {i < steps.length - 1 && <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.emerald }}>✓</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Results Phase */}
      {phase === "results" && (
        <div style={{ animation: "fadeUp 0.4s ease both" }}>
          {/* Source info bar */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 14px", borderRadius: 8, background: A.surfaceAlt, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12 }}>🎞️</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: A.text }}>{fileInfo.name}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: A.textSoft }}>· {clips.length} clips extracted</span>
            </div>
            <button onClick={() => { setPhase("upload"); setSteps([]); setProgress(0); }} style={{ padding: "4px 12px", borderRadius: 6, background: A.surface, border: `1px solid ${A.border}`, cursor: "pointer", fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: A.textSoft, display: "flex", alignItems: "center", gap: 4 }}>🔄 Regenerate Clips</button>
          </div>

          {/* Clip selector tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {clips.map((cl, i) => (
              <button key={i} onClick={() => { setActiveClip(i); setEditingCaption(false); }} style={{
                flex: 1, padding: "10px 12px", borderRadius: 10, cursor: "pointer", textAlign: "center",
                background: activeClip === i ? `${cl.platformColor}08` : A.surface,
                border: `1px solid ${activeClip === i ? cl.platformColor + "40" : A.border}`,
                transition: "all 0.2s",
              }}>
                <span style={{ fontSize: 16, display: "block", marginBottom: 4 }}>{cl.platformIcon}</span>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: 600, color: activeClip === i ? cl.platformColor : A.text }}>{cl.platform}</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textSoft, marginTop: 2 }}>{cl.duration} · {cl.aspect}</div>
              </button>
            ))}
          </div>

          {/* Clip detail */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {/* Left: Video preview — richer */}
            <div>
              <div style={{ width: "100%", aspectRatio: c.aspect === "1:1" ? "1/1" : "9/16", borderRadius: 12, background: `linear-gradient(180deg, ${A.text}06 0%, ${A.text}12 30%, ${A.text}08 60%, ${A.text}14 100%)`, border: `1px solid ${A.border}`, position: "relative", overflow: "hidden" }}>
                {/* Simulated frame bands */}
                {[15, 35, 55, 75].map((top, i) => (
                  <div key={i} style={{ position: "absolute", top: `${top}%`, left: 0, right: 0, height: 1, background: `${A.text}06` }} />
                ))}
                {/* Play overlay */}
                <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: 48, height: 48, borderRadius: "50%", background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", backdropFilter: "blur(4px)" }}>
                  <div style={{ width: 0, height: 0, borderLeft: "14px solid white", borderTop: "8px solid transparent", borderBottom: "8px solid transparent", marginLeft: 3 }} />
                </div>
                {/* Platform badge */}
                <div style={{ position: "absolute", top: 10, left: 10, padding: "4px 10px", borderRadius: 6, background: `${c.platformColor}15`, backdropFilter: "blur(4px)", display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontSize: 10 }}>{c.platformIcon}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: c.platformColor, fontWeight: 500 }}>{c.platform}</span>
                </div>
                {/* Duration badge */}
                <div style={{ position: "absolute", top: 10, right: 10, padding: "3px 8px", borderRadius: 4, background: "rgba(0,0,0,0.5)", fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "white" }}>{c.duration}</div>
                {/* Caption overlay — positioned in bottom third */}
                <div style={{ position: "absolute", bottom: 36, left: 10, right: 10, padding: "6px 10px", borderRadius: 4, background: "rgba(0,0,0,0.65)", backdropFilter: "blur(2px)" }}>
                  <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 10, color: "white", textAlign: "center", lineHeight: 1.4 }}>{c.hook}</div>
                </div>
                {/* Scrubber bar */}
                <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 24, background: "linear-gradient(transparent, rgba(0,0,0,0.4))", display: "flex", alignItems: "flex-end", padding: "0 10px 6px" }}>
                  <div style={{ flex: 1, height: 3, borderRadius: 2, background: "rgba(255,255,255,0.3)", position: "relative" }}>
                    <div style={{ width: "35%", height: "100%", borderRadius: 2, background: "white" }} />
                    <div style={{ position: "absolute", top: "-3px", left: "35%", width: 9, height: 9, borderRadius: "50%", background: "white", transform: "translateX(-50%)", boxShadow: "0 0 4px rgba(0,0,0,0.3)" }} />
                  </div>
                </div>
              </div>
              {/* Timecodes */}
              <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
                <div style={{ flex: 1, padding: "6px 8px", borderRadius: 6, background: A.surfaceAlt, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textSoft, textAlign: "center" }}>Start: {c.start}</div>
                <div style={{ flex: 1, padding: "6px 8px", borderRadius: 6, background: A.surfaceAlt, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textSoft, textAlign: "center" }}>End: {c.end}</div>
              </div>
            </div>

            {/* Right: Caption + actions */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* Hook callout */}
              <div style={{ padding: "4px 10px", borderRadius: 6, background: `${c.platformColor}08`, border: `1px solid ${c.platformColor}20`, display: "inline-flex", alignItems: "center", gap: 4, alignSelf: "flex-start" }}>
                <span style={{ fontSize: 10 }}>💡</span>
                <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: c.platformColor, fontWeight: 500 }}>Hook: {c.hook}</span>
              </div>
              {/* Caption card with character count */}
              <div style={{ padding: 16, borderRadius: 12, background: A.surface, border: `1px solid ${A.border}`, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: A.textMuted, letterSpacing: 1.5, textTransform: "uppercase" }}>Caption · {c.platform}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: charCount > charLimit * 0.9 ? "#E53E3E" : A.textMuted }}>{charCount}/{charLimit}</div>
                </div>
                {editingCaption ? (
                  <textarea style={{ width: "100%", minHeight: 120, padding: 10, borderRadius: 8, border: `1px solid ${A.indigo}40`, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, lineHeight: 1.6, resize: "vertical", outline: "none", background: A.surfaceAlt }} defaultValue={c.caption} />
                ) : (
                  <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 12, color: A.text, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{c.caption}</div>
                )}
              </div>
              {/* Actions */}
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={() => setEditingCaption(!editingCaption)} style={{ flex: 1, padding: 10, borderRadius: 8, background: A.surface, border: `1px solid ${A.border}`, fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 500, color: A.text, cursor: "pointer" }}>{editingCaption ? "Save" : "✏️ Edit Caption"}</button>
                <button style={{ flex: 1, padding: 10, borderRadius: 8, background: A.indigo, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>⬇️ Download Clip</button>
              </div>
              <button style={{ padding: 10, borderRadius: 8, background: `linear-gradient(135deg, ${A.indigo}, ${A.indigoDark})`, border: "none", color: "white", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer", boxShadow: `0 2px 12px ${A.indigo}25` }}>📦 Download All Clips (ZIP)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Main ────────────────────────────────────────────────────

export default function AmplisparkApp() {
  const [screen, setScreen] = useState("landing");
  return (
    <div style={{ maxWidth: 960, margin: "0 auto", minHeight: "100vh", background: A.bg }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes blink { 50% { opacity: 0; } }
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        input::placeholder, textarea::placeholder { color: #9898B0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #E8E8E4; border-radius: 4px; }
      `}</style>
      <NavBar screen={screen} setScreen={setScreen} />
      {screen === "landing" && <LandingPage onStart={() => setScreen("onboard")} />}
      {screen === "onboard" && <OnboardScreen onNext={() => setScreen("brand")} />}
      {screen === "brand" && <BrandProfileScreen onNext={() => setScreen("calendar")} />}
      {screen === "calendar" && <CalendarScreen onDetail={() => setScreen("detail")} />}
      {screen === "detail" && <ContentDetailScreen onBack={() => setScreen("calendar")} />}
      {screen === "video" && <VideoRepurposeScreen onBack={() => setScreen("detail")} />}
      {screen === "dashboard" && <DashboardScreen onScreen={setScreen} />}
    </div>
  );
}