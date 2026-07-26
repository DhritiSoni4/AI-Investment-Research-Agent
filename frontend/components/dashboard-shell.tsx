"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, BarChart3, Bell, BookOpen, BriefcaseBusiness, ChevronRight, Search, Settings, Sparkles } from "lucide-react";
import React from "react";
import { useState } from "react";

const nav = [
  [BarChart3, "Research", true], [BookOpen, "Reports", false], [BriefcaseBusiness, "Portfolio", false], [Settings, "Settings", false],
] as const;

const stages = ["Plan research", "Company profile", "Financial analysis", "News & filings", "Investment committee"];

export function DashboardShell() {
  const [query, setQuery] = useState("");
  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#17213d_0%,_#0b1020_55%)] p-4 text-[#e8edf7] md:p-6">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1500px] grid-cols-1 overflow-hidden rounded-2xl border border-[#26324c] bg-[#0e1526]/90 shadow-2xl shadow-black/30 md:grid-cols-[218px_1fr]">
        <aside className="border-b border-[#26324c] p-5 md:border-b-0 md:border-r">
          <div className="mb-10 flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-teal-300 text-[#06201e]"><Sparkles size={19}/></span><span className="text-lg font-semibold tracking-tight">AlphaAgent</span></div>
          <nav className="flex gap-2 md:flex-col">{nav.map(([Icon, label, active]) => <button key={label} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${active ? "bg-teal-300/10 text-teal-200" : "text-[#91a0bb] hover:bg-white/5 hover:text-white"}`}><Icon size={17}/>{label}</button>)}</nav>
          <div className="mt-10 rounded-xl border border-[#26324c] bg-[#11182b] p-4"><p className="text-xs font-medium text-teal-200">RESEARCH MODE</p><p className="mt-2 text-sm text-[#91a0bb]">Institutional-grade analysis with an auditable agent trail.</p></div>
        </aside>
        <section className="p-5 md:p-8">
          <header className="flex items-center justify-between gap-4"><div><p className="text-sm text-[#91a0bb]">Monday, March 9</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Research workspace</h1></div><button aria-label="Notifications" className="rounded-lg border border-[#26324c] p-2.5 text-[#91a0bb]"><Bell size={18}/></button></header>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-8 rounded-2xl border border-teal-300/20 bg-gradient-to-br from-teal-300/10 to-[#11182b] p-6 md:p-8">
            <p className="text-sm font-medium text-teal-200">AUTONOMOUS EQUITY RESEARCH</p><h2 className="mt-3 max-w-2xl text-2xl font-semibold tracking-tight md:text-3xl">Turn a company question into a defensible investment view.</h2>
            <div className="mt-6 flex max-w-3xl items-center rounded-xl border border-[#31415f] bg-[#09101e] p-2"><Search className="ml-2 text-[#91a0bb]" size={19}/><input aria-label="Company research query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Analyze a company — e.g. NVIDIA or NVDA" className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#61708b]"/><button className="rounded-lg bg-teal-300 px-4 py-2 text-sm font-semibold text-[#06201e]">Research</button></div>
            {query && <p className="mt-3 text-xs text-[#91a0bb]">Research sessions will be enabled in Milestone 2.</p>}
          </motion.div>
          <div className="mt-7 grid gap-5 xl:grid-cols-[1.25fr_.75fr]">
            <section className="rounded-xl border border-[#26324c] bg-[#11182b] p-5"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold">How AlphaAgent works</p><p className="mt-1 text-xs text-[#91a0bb]">Transparent execution, never hidden reasoning.</p></div><span className="text-xs text-teal-200">5 agents</span></div><ol className="mt-5 space-y-3">{stages.map((stage, i) => <li key={stage} className="flex items-center gap-3"><span className="grid size-6 place-items-center rounded-full border border-[#3b4c6b] text-xs text-[#91a0bb]">{i + 1}</span><span className="flex-1 text-sm">{stage}</span>{i === 0 && <span className="rounded-full bg-teal-300/10 px-2 py-1 text-[11px] text-teal-200">Ready</span>}</li>)}</ol></section>
            <section className="rounded-xl border border-[#26324c] bg-[#11182b] p-5"><p className="text-sm font-semibold">Platform status</p><div className="mt-5 space-y-4"><Status label="API contract" value="Online"/><Status label="Research agents" value="Coming next"/><Status label="Report memory" value="Planned"/></div></section>
          </div>
          <section className="mt-5 rounded-xl border border-[#26324c] bg-[#11182b] p-5"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold">Recent research</p><p className="mt-1 text-xs text-[#91a0bb]">Your completed, source-backed reports appear here.</p></div><button className="flex items-center gap-1 text-sm text-teal-200">View reports <ChevronRight size={16}/></button></div><div className="mt-5 flex items-center gap-3 rounded-lg border border-dashed border-[#3b4c6b] p-4 text-sm text-[#91a0bb]"><ArrowUpRight size={18} className="text-teal-200"/> No reports yet. Start with a company search above.</div></section>
        </section>
      </div>
    </main>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between text-sm"><span className="text-[#91a0bb]">{label}</span><span className="flex items-center gap-2"><i className="size-1.5 rounded-full bg-teal-300"/>{value}</span></div>;
}
