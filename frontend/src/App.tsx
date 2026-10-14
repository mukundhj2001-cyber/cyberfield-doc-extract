import { useEffect, useState } from "react";
import { api } from "./api";
import Inbox from "./pages/Inbox";
import Review from "./pages/Review";

export default function App() {
  const [route, setRoute] = useState(location.hash);
  const [mode, setMode] = useState("…");
  useEffect(() => { const f = () => setRoute(location.hash); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  useEffect(() => { api("/api/health").then((h) => setMode(h.mode)).catch(() => {}); }, []);
  const m = route.match(/^#\/review\/(\d+)/);
  return (
    <div className="min-h-screen">
      <header className="border-b border-gold-500/15 bg-black/60 backdrop-blur sticky top-0 z-20">
        <div className="mx-auto max-w-7xl flex items-center gap-4 px-6 py-3">
          <a href="#/" className="flex items-center gap-3">
            <img src="/logo.svg" className="h-9 w-9" alt="Cyberfield AI" />
            <div><div className="font-display text-sm tracking-[0.25em] gold-text font-bold">CYBERFIELD AI</div>
              <div className="text-xs text-zinc-400">Document Data Extraction</div></div>
          </a>
          <nav className="ml-8 text-sm"><a href="#/" className={`px-3 py-1.5 rounded-lg ${!m ? "bg-gold-500 text-black font-semibold" : "text-zinc-300"}`}>Documents</a></nav>
          <span className="ml-auto chip bg-gold-500/10 text-gold-300 border border-gold-500/30" data-testid="mode">
            {mode === "llm" ? "AI mode: LLM live" : "AI mode: demo (local rules + OCR)"}</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{m ? <Review id={+m[1]} /> : <Inbox />}</main>
      <footer className="text-center text-xs text-zinc-500 pb-6">Built by <span className="text-gold-400">Cyberfield AI</span> · sample documents are fictional</footer>
    </div>
  );
}
