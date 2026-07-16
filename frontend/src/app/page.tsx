"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";

export default function LandingPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  const [lang, setLang] = useState("English");
  useEffect(() => {
    setLang(getLanguage());
    const handleLangChange = () => {
      setLang(getLanguage());
    };
    window.addEventListener("ui_language_changed", handleLangChange);
    return () => {
      window.removeEventListener("ui_language_changed", handleLangChange);
    };
  }, []);

  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem("token");
      if (!token) {
        setLoadingUser(false);
        return;
      }
      try {
        const res = await fetch("http://localhost:8000/api/v1/auth/me", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) {
          throw new Error("Session expired or invalid");
        }
        const data = await res.json();
        setUser(data);
      } catch (err) {
        console.warn("[LANDING] Session invalid, clearing token.", err);
        localStorage.removeItem("token");
        setUser(null);
      } finally {
        setLoadingUser(false);
      }
    };
    fetchUser();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    setUser(null);
    router.push("/login");
  };

  const steps = [
    {
      number: 1,
      title: t("Upload Data"),
      desc: t("Upload your security evidence files. Supported formats: PDF, CSV, XLSX"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
      ),
    },
    {
      number: 2,
      title: t("Report Settings"),
      desc: t("Set period, template, format, and other preferences for your report"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
        </svg>
      ),
    },
    {
      number: 3,
      title: t("AI Processing"),
      desc: t("Our AI will analyze the data and generate insights, charts, and summary"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-350 group-hover:rotate-12 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
        </svg>
      ),
    },
    {
      number: 4,
      title: t("Preview & Edit"),
      desc: t("Review AI generated content and make any necessary edits"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
        </svg>
      ),
    },
    {
      number: 5,
      title: t("Export Report"),
      desc: t("Export your report to PDF or PowerPoint format"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
      ),
    },
  ];

  const modules = [
    {
      title: t("Generate Report"),
      desc: t("Create monthly SOC reports automatically with AI"),
      href: "/generate",
      color: "text-petro-green",
      bg: "bg-petro-green-light",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-300 group-hover:rotate-6 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      ),
    },
    {
      title: t("Report History"),
      desc: t("View, search, download, and manage previously generated reports"),
      href: "/history",
      color: "text-amber-600",
      bg: "bg-amber-50",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
        </svg>
      ),
    },
    {
      title: t("Settings"),
      desc: t("Manage account preferences and profile settings"),
      href: "/settings",
      color: "text-violet-650",
      bg: "bg-violet-50/70",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-500 group-hover:rotate-90">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-petro-bg-warm flex flex-col overflow-x-hidden selection:bg-petro-green/10 selection:text-petro-green">

      {/* ── HEADER NAVBAR ────────────────────────────────────────── */}
      <header className="w-full px-8 py-3 flex items-center justify-between border-b border-white/10 bg-petro-green text-white sticky top-0 z-40 shadow-md">
        <Link href="/" className="flex items-center gap-3 group">
          <img src="/LOGO_PETRO.png" alt="Petrokimia Logo" className="h-12 lg:h-14 w-auto object-contain shrink-0 -my-2 lg:-my-3 transition-transform duration-300 group-hover:scale-105" />
          <div className="flex flex-col text-left leading-none">
            <span className="font-extrabold text-sm text-white tracking-tight">{t("AI Security Reports")}</span>
            <span className="text-[9px] text-white/70 font-semibold uppercase tracking-widest mt-0.5">{t("PT Petrokimia Gresik")}</span>
          </div>
        </Link>

        <nav className="flex items-center gap-3">
          {loadingUser ? (
            <div className="w-24 h-9 bg-white/10 animate-pulse rounded-xl" />
          ) : user ? (
            <div className="flex items-center gap-3 bg-white/10 border border-white/15 px-3 py-1.5 rounded-xl shadow-sm hover:bg-white/15 transition-all duration-300">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name || user.username} className="w-8 h-8 rounded-lg border border-white/20 object-cover" />
              ) : (
                <div className="w-8 h-8 rounded-lg bg-petro-yellow flex items-center justify-center font-black text-xs uppercase text-white shrink-0 shadow-inner">
                  {user.full_name ? user.full_name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase() : user.username.slice(0, 2).toUpperCase()}
                </div>
              )}
              <div className="flex flex-col text-left max-w-[120px] hidden sm:flex">
                <span className="text-xs font-bold text-white leading-none truncate">{user.full_name || user.username}</span>
                <span className="text-[9px] text-white/60 font-semibold mt-0.5 truncate">{user.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="ml-1.5 text-[10px] uppercase font-bold text-white bg-red-650 hover:bg-red-700 px-3 py-2 rounded-xl hover:shadow transition-all duration-200 cursor-pointer"
              >
                {t("Logout")}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="px-4 py-2 text-xs font-bold text-white/80 hover:text-white transition-colors rounded-xl hover:bg-white/10"
              >
                {t("Sign In")}
              </Link>
              <Link
                href="/register"
                className="px-4 py-2.5 text-xs font-extrabold text-white bg-petro-yellow hover:bg-petro-yellow-hover rounded-xl shadow-sm transition-all duration-200"
              >
                {t("Register")}
              </Link>
            </div>
          )}
        </nav>
      </header>

      {/* ── HERO BANNER SECTION ───────────────────────────────────── */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-6 py-20 md:py-28 relative bg-gradient-to-b from-stone-50/40 to-transparent border-b border-stone-200/40">
        
        {/* Subtle grid pattern background */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,77,37,0.02)_1.5px,transparent_1.5px),linear-gradient(90deg,rgba(0,77,37,0.02)_1.5px,transparent_1.5px)] bg-[size:32px_32px] pointer-events-none opacity-60" />

        <div className="relative z-10 max-w-4xl flex flex-col items-center space-y-6">
          <div className="animate-scaleIn inline-flex items-center gap-2 px-3 py-1 rounded-full bg-petro-yellow-light border border-petro-yellow/30 text-petro-yellow-hover text-[10px] font-extrabold uppercase tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-petro-yellow animate-ping" />
            {t("Local LLM Integrated")}
          </div>
          
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-black text-stone-900 leading-[1.1] tracking-tight max-w-3xl animate-fadeInUp delay-100">
            {t("Automate Your")} <br />
            <span className="text-petro-green">{t("SOC Security Reports")}</span>
          </h1>

          <p className="max-w-xl text-sm md:text-base text-stone-500 font-medium leading-relaxed animate-fadeInUp delay-150">
            {t("Automatically transform network firewall logs, VAPT scans, and email threats into executive summaries using advanced AI models.")}
          </p>

          <div className="pt-2 animate-fadeInUp delay-200">
            <Link
              href="/generate"
              className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs tracking-wider uppercase shadow-lg hover:shadow-xl transition-all duration-300 group cursor-pointer"
            >
              {t("Get Started Wizard")}
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4 transition-transform group-hover:translate-x-1">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>
        </div>

        {/* Feature badge pills */}
        <div className="mt-14 flex flex-wrap items-center justify-center gap-4 max-w-4xl relative z-10 animate-fadeInUp delay-300">
          <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
            <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-650 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
            </div>
            <div className="text-left leading-tight">
              <div className="font-bold text-stone-850 text-xs">{t("Division Compliant")}</div>
              <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{t("PT Petrokimia Gresik")}</div>
            </div>
          </div>

          <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
            <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
              </svg>
            </div>
            <div className="text-left leading-tight">
              <div className="font-bold text-stone-850 text-xs">{t("90% Time Saved")}</div>
              <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{t("Local offline analytics")}</div>
            </div>
          </div>

          <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
            <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </div>
            <div className="text-left leading-tight">
              <div className="font-bold text-stone-850 text-xs">{t("PDF & PPTX Output")}</div>
              <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{t("Multi-format support")}</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS SECTION ──────────────────────────────────── */}
      <section className="relative py-20 px-6 bg-[#f2f4f0] border-b border-stone-200/40 overflow-hidden">
        {/* Subtle sage/dotted pattern background */}
        <div className="absolute inset-0 bg-[radial-gradient(rgba(0,77,37,0.045)_1.2px,transparent_1.2px)] bg-[size:24px_24px] pointer-events-none" />
        
        <ScrollReveal animation="fadeInUp" className="relative z-10 max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-[10px] font-extrabold tracking-widest text-petro-yellow uppercase bg-petro-yellow-light border border-petro-yellow/20 px-3 py-1 rounded-full">{t("Process Flow")}</span>
            <h2 className="text-3xl font-extrabold text-stone-900 mt-3.5">{t("How It Works")}</h2>
            <p className="text-xs text-stone-450 font-bold mt-1.5 max-w-md mx-auto">{t("Transform complex cybersecurity logs into structured reports in five simple phases.")}</p>
          </div>

          {/* Desktop timeline horizontal view */}
          <div className="hidden md:flex items-start justify-center gap-0 w-full">
            {steps.map((step, i) => (
              <div key={step.number} className="flex flex-row items-center flex-1">
                {/* Step Node Card */}
                <div className="flex flex-col items-center text-center flex-1 group premium-card-hover p-4 bg-white border border-stone-200/80 rounded-2xl cursor-default shadow-sm min-h-[195px] justify-between">
                  <div className="relative w-14 h-14 rounded-2xl bg-petro-green-light border border-petro-green/10 flex items-center justify-center text-petro-green transition-transform duration-300 group-hover:scale-105 shrink-0">
                    {step.icon}
                    <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-lg bg-petro-yellow text-white text-[9px] font-extrabold flex items-center justify-center border border-white shadow-sm">
                      {step.number}
                    </span>
                  </div>
                  <div className="mt-4 flex-1 flex flex-col justify-center">
                    <h3 className="font-bold text-stone-850 text-xs tracking-tight group-hover:text-petro-green transition-colors duration-200">{step.title}</h3>
                    <p className="text-[10px] text-stone-400 font-semibold mt-1 leading-relaxed max-w-[140px] mx-auto">{step.desc}</p>
                  </div>
                </div>

                {/* Arrow connector */}
                {i < steps.length - 1 && (
                  <div className="flex items-center justify-center text-stone-300 select-none self-center mx-1 shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Mobile vertical layout list */}
          <div className="md:hidden space-y-4">
            {steps.map((step) => (
              <div key={step.number} className="flex items-start gap-4 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm premium-card-hover">
                <div className="relative w-11 h-11 rounded-xl bg-petro-green-light border border-petro-green/15 flex items-center justify-center text-petro-green shrink-0">
                  <span className="font-extrabold text-sm">{step.number}</span>
                </div>
                <div className="text-left">
                  <h3 className="font-bold text-stone-850 text-xs">{step.title}</h3>
                  <p className="text-[10px] text-stone-450 font-semibold mt-0.5 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </ScrollReveal>
      </section>

      {/* ── CHOOSE MODULE / LAUNCH SECTION ────────────────────────── */}
      <section className="relative py-20 px-6 bg-white/70 overflow-hidden">
        {/* Subtle gold diagonal pinstripe pattern background */}
        <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(217,167,0,0.02)_25%,transparent_25%,transparent_50%,rgba(217,167,0,0.02)_50%,rgba(217,167,0,0.02)_75%,transparent_75%,transparent)] bg-[size:40px_40px] pointer-events-none" />
        
        <ScrollReveal animation="fadeInUp" className="relative z-10 max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <span className="text-[10px] font-extrabold tracking-widest text-petro-yellow uppercase bg-petro-yellow-light border border-petro-yellow/20 px-3 py-1 rounded-full">{t("Launch Centre")}</span>
            <h2 className="text-3xl font-extrabold text-stone-900 mt-3.5">{t("Available Modules")}</h2>
            <p className="text-xs text-stone-455 font-bold mt-1.5 max-w-sm mx-auto">{t("Direct shortcuts to generate reports, view logs, or adjust settings.")}</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {modules.map((mod) => (
              <Link
                key={mod.title}
                href={mod.href}
                className="group bg-white rounded-2xl border border-stone-200/80 p-8 flex flex-col items-center text-center shadow-sm hover:shadow-md transition-all duration-300 premium-card-hover cursor-pointer"
              >
                <div className={`w-14 h-14 rounded-2xl ${mod.bg} flex items-center justify-center ${mod.color} mb-6 transition-transform duration-350`}>
                  {mod.icon}
                </div>
                <h3 className="font-extrabold text-stone-855 text-sm tracking-tight">{mod.title}</h3>
                <p className="text-[10px] text-stone-450 font-semibold mt-2.5 leading-relaxed max-w-[180px]">{mod.desc}</p>
              </Link>
            ))}
          </div>
        </ScrollReveal>
      </section>

      {/* ── BRAND FOOTER SECTION ──────────────────────────────────── */}
      <footer className="border-t border-white/10 bg-petro-green py-12 px-8 text-white mt-auto">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <img src="/LOGO_PETRO.png" alt="Petrokimia Logo" className="h-12 lg:h-14 w-auto object-contain shrink-0 -my-2 lg:-my-3" />
            <div className="flex flex-col text-left leading-none">
              <span className="font-extrabold text-sm text-white tracking-wide">{t("AI Security Reports")}</span>
              <span className="text-[9px] text-white/60 font-semibold tracking-wider mt-0.5">{t("PT Petrokimia Gresik")}</span>
            </div>
          </div>

          <div className="text-center sm:text-right">
            <p className="text-[10px] font-extrabold text-white/80 uppercase tracking-widest">{t("Internal Use Only")}</p>
            <p className="text-[9px] text-white/50 font-medium mt-1">© 2026 PT Petrokimia Gresik. All rights reserved.</p>
          </div>
        </div>

        <div className="max-w-5xl mx-auto mt-6 pt-4 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-2 text-[9px] text-white/40 font-medium">
          <p>{t("IT Infrastructure Security Division System — PT Petrokimia Gresik")}</p>
          <p className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            {t("System Status: Operational")}
          </p>
        </div>
      </footer>
    </div>
  );
}
