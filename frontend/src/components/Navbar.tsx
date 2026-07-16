"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { t, getLanguage } from "@/utils/i18n";

export default function Navbar() {
  const [search, setSearch] = useState("");
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotif, setShowNotif] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
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

  // Page title from path
  const getPageTitle = () => {
    if (pathname?.startsWith("/generate")) return t("Generate Report");
    if (pathname?.startsWith("/history")) return t("Report History");
    if (pathname?.startsWith("/settings")) return t("Settings");
    return t("Dashboard");
  };

  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem("token");
      if (!token) { router.push("/login"); return; }
      try {
        const res = await fetch("http://localhost:8000/api/v1/auth/me", {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Session expired");
        setUser(await res.json());

        // Fetch user settings to sync UI language
        try {
          const settingsRes = await fetch("http://localhost:8000/api/v1/settings/", {
            headers: { "Authorization": `Bearer ${token}` }
          });
          if (settingsRes.ok) {
            const settings = await settingsRes.json();
            const dbLang = settings.ai_language === "Indonesian" ? "Indonesian" : "English";
            const currentLang = localStorage.getItem("ui_language") || "English";
            if (dbLang !== currentLang) {
              localStorage.setItem("ui_language", dbLang);
              window.dispatchEvent(new Event("ui_language_changed"));
            }
          }
        } catch (settingsErr) {
          console.warn("Failed to sync settings language in Navbar:", settingsErr);
        }
      } catch {
        localStorage.removeItem("token");
        router.push("/login");
      }
    };
    fetchUser();

    window.addEventListener("user_profile_updated", fetchUser);
    return () => {
      window.removeEventListener("user_profile_updated", fetchUser);
    };
  }, [router]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setShowUserMenu(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotif(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  const initials = user?.full_name
    ? user.full_name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase()
    : user?.username?.slice(0, 2).toUpperCase() ?? "??";

  return (
    <header className="h-16 border-b border-stone-200/60 bg-white/80 backdrop-blur-xl flex items-center justify-between px-8 sticky top-0 z-20 w-full transition-shadow duration-300">
      {/* Left: Page title breadcrumb */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <span className="text-xs text-stone-400 font-semibold tracking-wide">PT Petrokimia Gresik</span>
          <h1 className="text-sm font-extrabold text-stone-800 leading-none -mt-0.5">{getPageTitle()}</h1>
        </div>
      </div>

      {/* Center: Search */}
      <div className="relative w-80 group">
        <span className="absolute inset-y-0 left-3 flex items-center text-stone-400 transition-colors duration-200 group-focus-within:text-petro-green">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.602 10.602Z" />
          </svg>
        </span>
        <input
          type="text"
          placeholder={t("Search reports, alerts, templates...")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-stone-100/80 border border-stone-200 rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green focus:bg-white transition-all duration-200 placeholder:text-stone-400"
        />
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">

        {/* Notification Bell */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => { setShowNotif(!showNotif); setShowUserMenu(false); }}
            className="relative w-10 h-10 rounded-xl bg-white border border-stone-200 flex items-center justify-center text-stone-500 hover:text-petro-green hover:border-petro-green/30 hover:shadow-sm transition-all duration-200 group"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:scale-110">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
            </svg>
            {/* Ping dot */}
            <span className="absolute top-1.5 right-1.5 w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-75" />
              <span className="relative block w-2 h-2 rounded-full bg-red-500" />
            </span>
          </button>

          {/* Notification dropdown */}
          {showNotif && (
            <div className="absolute right-0 top-12 w-72 bg-white rounded-2xl shadow-xl border border-stone-200/80 z-50 animate-slideDown overflow-hidden">
              <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
                <span className="text-sm font-bold text-stone-880">{t("Notifications")}</span>
                <span className="text-xs text-petro-green font-semibold cursor-pointer hover:underline">{t("Mark all read")}</span>
              </div>
              <div className="divide-y divide-stone-50">
                {[
                  { icon: "✅", title: "Report Generated", sub: "SOC Executive Summary - July 2026", time: "2m ago" },
                  { icon: "⚠️", title: "High Alert Detected", sub: "22 new critical events flagged", time: "18m ago" },
                  { icon: "📄", title: "Export Ready", sub: "VAPT Report Q2 PDF is ready", time: "1h ago" },
                ].map((n, i) => (
                  <div key={i} className="flex gap-3 px-4 py-3 hover:bg-stone-50 cursor-pointer transition-colors duration-150">
                    <span className="text-lg shrink-0">{n.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-stone-800 truncate">{n.title}</p>
                      <p className="text-xs text-stone-500 truncate">{n.sub}</p>
                    </div>
                    <span className="text-[10px] text-stone-400 shrink-0 font-medium">{n.time}</span>
                  </div>
                ))}
              </div>
              <div className="px-4 py-2.5 border-t border-stone-100 text-center">
                <span className="text-xs text-petro-green font-semibold cursor-pointer hover:underline">{t("View all notifications")}</span>
              </div>
            </div>
          )}
        </div>

        {/* User Card */}
        <div className="relative" ref={userMenuRef}>
          {user ? (
            <button
              onClick={() => { setShowUserMenu(!showUserMenu); setShowNotif(false); }}
              className="flex items-center gap-2.5 bg-white border border-stone-200/80 pl-1.5 pr-3 py-1.5 rounded-xl shadow-sm hover:shadow-md hover:border-stone-300 transition-all duration-200 group"
            >
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name || user.username} className="w-8 h-8 rounded-lg border border-stone-200 object-cover" />
              ) : (
                <div className="w-8 h-8 rounded-lg bg-petro-yellow flex items-center justify-center font-extrabold text-xs uppercase text-white shrink-0 shadow-inner transition-transform duration-200 group-hover:scale-105">
                  {initials}
                </div>
              )}
              <div className="flex flex-col text-left max-w-[110px]">
                <span className="text-xs font-bold text-stone-800 leading-none truncate">{user.full_name || user.username}</span>
                <span className="text-[9px] text-stone-400 font-medium mt-0.5 truncate">{user.role || "SOC Analyst"}</span>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-3 h-3 text-stone-400 transition-transform duration-200 ${showUserMenu ? "rotate-180" : ""}`}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          ) : (
            <div className="w-36 h-10 skeleton rounded-xl" />
          )}

          {/* User Dropdown */}
          {showUserMenu && user && (
            <div className="absolute right-0 top-12 w-52 bg-white rounded-2xl shadow-xl border border-stone-200/80 z-50 animate-slideDown overflow-hidden">
              <div className="px-4 py-3 border-b border-stone-100">
                <p className="text-xs font-bold text-stone-800">{user.full_name || user.username}</p>
                <p className="text-[10px] text-stone-400 font-medium truncate">{user.email}</p>
              </div>
              <div className="py-1">
                <Link href="/settings" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-medium">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                  </svg>
                  {t("My Profile")}
                </Link>
                <Link href="/settings" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-medium">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  </svg>
                  {t("Settings")}
                </Link>
              </div>
              <div className="border-t border-stone-100 py-1">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors duration-150 font-semibold"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                  </svg>
                  {t("Sign Out")}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
