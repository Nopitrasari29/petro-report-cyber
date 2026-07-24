"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, getLanguage } from "@/utils/i18n";
import LandingHero from "./components/landing/LandingHero";
import LandingHowItWorks from "./components/landing/LandingHowItWorks";
import LandingModulesList from "./components/landing/LandingModulesList";

export default function LandingPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [lang, setLang] = useState("English");

  // Pengaman Hidrasi (Hydration Guard)
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const tx = (key: string, fallback: string) => mounted ? t(key) : fallback;

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

  return (
    <div className="min-h-screen bg-petro-bg-warm flex flex-col overflow-x-hidden selection:bg-petro-green/10 selection:text-petro-green">

      {/* ── HEADER NAVBAR ── */}
      <header className="w-full px-10 py-4.5 flex items-center justify-between border-b border-white/10 bg-petro-green text-white sticky top-0 z-40 shadow-md">
        <Link href="/" className="flex items-center gap-4 group">
          <div className="bg-white px-3 py-1.5 rounded-xl shadow-sm transition-transform duration-300 group-hover:scale-105">
            <img src="/LOGO_PETRO_DANANTARA.png" alt="Petrokimia Danantara Logo" className="h-9 lg:h-10 w-auto object-contain shrink-0" />
          </div>
          {/* Garis vertikal pembatas tipis */}
          <div className="h-10 w-[1px] bg-white/20 shrink-0 hidden sm:block" />
          <div className="flex flex-col text-left leading-none">
            <span className="font-extrabold text-sm text-white tracking-wide uppercase">{tx("AI Security Reports", "AI Security Reports")}</span>
            <span className="text-[9px] text-petro-yellow font-bold uppercase tracking-widest mt-1.5">{tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}</span>
          </div>
        </Link>

        <nav className="flex items-center gap-4">
          {loadingUser ? (
            <div className="w-24 h-10 bg-white/10 animate-pulse rounded-xl" />
          ) : user ? (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 bg-white/10 border border-white/15 pl-2.5 pr-5 py-2 rounded-xl shadow-sm select-none">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name || user.username} className="w-9 h-9 rounded-lg border border-white/20 object-cover" />
                ) : (
                  <div className="w-9 h-9 rounded-lg bg-petro-yellow flex items-center justify-center font-black text-xs uppercase text-white shrink-0 shadow-inner">
                    {user.full_name ? user.full_name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase() : user.username.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div className="flex flex-col text-left max-w-[180px] hidden sm:flex">
                  <span className="text-xs font-black text-white leading-none truncate">{user.full_name || user.username}</span>
                  <span className="text-[10px] text-white/70 font-semibold mt-1.5 truncate">{user.email}</span>
                </div>
              </div>

              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 text-xs font-bold text-white bg-red-650 hover:bg-red-700 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer shrink-0"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                </svg>
                {tx("Logout", "Logout")}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="px-4 py-2.5 text-xs font-bold text-white/80 hover:text-white transition-colors rounded-xl hover:bg-white/10"
              >
                {tx("Sign In", "Sign In")}
              </Link>
              <Link
                href="/register"
                className="px-4 py-3 text-xs font-extrabold text-white bg-petro-yellow hover:bg-petro-yellow-hover rounded-xl shadow-sm transition-all duration-200"
              >
                {tx("Register", "Register")}
              </Link>
            </div>
          )}
        </nav>
      </header>

      {/* ── HERO BANNER SECTION ── */}
      <LandingHero tx={tx} />

      {/* ── HOW IT WORKS SECTION ── */}
      <LandingHowItWorks tx={tx} />

      {/* ── CHOOSE MODULE / LAUNCH SECTION ── */}
      <LandingModulesList tx={tx} />

      {/* ── BRAND FOOTER SECTION ── */}
      <footer className="border-t border-white/10 bg-petro-green py-12 px-8 text-white mt-auto">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="bg-white px-3 py-1.5 rounded-xl shadow-sm">
              <img src="/LOGO_PETRO_DANANTARA.png" alt="Petrokimia Danantara Logo" className="h-9 lg:h-10 w-auto object-contain shrink-0" />
            </div>
            <div className="flex flex-col text-left leading-none">
              <span className="font-extrabold text-sm text-white tracking-wide">{tx("AI Security Reports", "AI Security Reports")}</span>
              <span className="text-[9px] text-white/60 font-semibold tracking-wider mt-0.5">{tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}</span>
            </div>
          </div>

          <div className="text-center sm:text-right">
            <p className="text-xs font-black text-petro-yellow uppercase tracking-widest">{tx("Internal Use Only", "Internal Use Only")}</p>
            <p className="text-xs text-stone-300 font-semibold mt-1.5">© 2026 PT Petrokimia Gresik. All rights reserved.</p>
          </div>
        </div>

        <div className="max-w-5xl mx-auto mt-6 pt-4 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-stone-300 font-semibold">
          <p>{tx("IT Infrastructure Security Division System — PT Petrokimia Gresik", "IT Infrastructure Security Division System — PT Petrokimia Gresik")}</p>
          <p className="flex items-center gap-1.5 text-xs text-stone-300 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-sm" />
            {tx("System Status: Operational", "System Status: Operational")}
          </p>
        </div>
      </footer>
    </div>
  );
}