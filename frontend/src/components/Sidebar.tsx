"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { t, getLanguage } from "@/utils/i18n";

const menuItems = [
  {
    name: "Generate Report",
    path: "/generate",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:scale-110 group-hover:rotate-6">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
  },
  {
    name: "Report History",
    path: "/history",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:scale-110">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
      </svg>
    ),
  },
];

const generalItems = [
  {
    name: "Settings",
    path: "/settings?tab=general",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-500 group-hover:rotate-45">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [lang, setLang] = useState("English");

  // ==========================================
  // EFFECT 1: Pengaman Hidrasi (Hydration Guard)
  // ==========================================
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Fungsi pembantu untuk menerjemahkan teks secara aman setelah hidrasi selesai
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

  const checkActive = (path: string) => pathname === path || pathname?.startsWith(path);

  return (
    <aside className="w-64 h-screen bg-petro-green text-white flex flex-col fixed left-0 top-0 border-r border-white/10 z-30 shrink-0 shadow-xl">
      {/* Brand Header */}
      <Link
        href="/"
        className="py-5 px-6 border-b border-white/10 flex items-center gap-3 hover:bg-white/5 transition-all duration-300 group animate-fadeIn"
      >
        <div className="w-9 h-9 rounded-xl bg-petro-yellow flex items-center justify-center shadow-lg transition-transform duration-300 group-hover:scale-105 shrink-0">
          <span className="font-extrabold text-white text-sm">P</span>
        </div>
        <div className="flex flex-col text-left leading-none">
          <span className="font-extrabold text-sm tracking-tight text-white leading-snug">
            {tx("AI Security Reports", "AI Security Reports")}
          </span>
          <span className="text-[9px] text-white/60 font-semibold tracking-widest uppercase mt-0.5">
            PT Petrokimia Gresik
          </span>
        </div>
      </Link>

      {/* Nav Menu */}
      <nav className="flex-1 py-6 px-3 space-y-6 overflow-y-auto">
        <div>
          <span className="text-[9px] font-extrabold text-white/35 tracking-[0.15em] uppercase px-3 block mb-2 animate-fadeIn delay-100">
            {tx("Menu", "Menu")}
          </span>
          <ul className="space-y-1">
            {menuItems.map((item, i) => {
              const active = checkActive(item.path);
              return (
                <li
                  key={item.name}
                  className="animate-slideInLeft"
                  style={{ animationDelay: `${120 + i * 60}ms` }}
                >
                  <Link
                    href={item.path}
                    className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 overflow-hidden ${active
                      ? "bg-white/15 text-white"
                      : "text-white/70 hover:text-white"
                      }`}
                  >
                    <span
                      className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full bg-petro-yellow transition-all duration-300 ${active ? "h-6 opacity-100" : "h-0 opacity-0"
                        }`}
                    />
                    <span className="absolute inset-0 rounded-xl bg-white/0 group-hover:bg-white/5 transition-colors duration-200" />
                    <span className="relative z-10">{item.icon}</span>
                    {/* Menggunakan 'tx' agar bebas dari Hydration Mismatch pada pemetaan item menu */}
                    <span className="relative z-10">{tx(item.name, item.name)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <span className="text-[9px] font-extrabold text-white/35 tracking-[0.15em] uppercase px-3 block mb-2 animate-fadeIn delay-300">
            {tx("General", "General")}
          </span>
          <ul className="space-y-1">
            {generalItems.map((item, i) => {
              const active = checkActive(item.path);
              return (
                <li
                  key={item.name}
                  className="animate-slideInLeft"
                  style={{ animationDelay: `${360 + i * 60}ms` }}
                >
                  <Link
                    href={item.path}
                    className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 overflow-hidden ${active
                      ? "bg-white/15 text-white"
                      : "text-white/70 hover:text-white"
                      }`}
                  >
                    <span
                      className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full bg-petro-yellow transition-all duration-300 ${active ? "h-6 opacity-100" : "h-0 opacity-0"
                        }`}
                    />
                    <span className="absolute inset-0 rounded-xl bg-white/0 group-hover:bg-white/5 transition-colors duration-200" />
                    <span className="relative z-10">{item.icon}</span>
                    {/* Menggunakan 'tx' agar bebas dari Hydration Mismatch pada pemetaan item general */}
                    <span className="relative z-10">{tx(item.name, item.name)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/10 flex flex-col items-center gap-2 animate-fadeIn delay-500">
        <div className="relative">
          <span className="px-2.5 py-1 rounded-full bg-white/10 text-white font-bold text-[9px] uppercase tracking-widest">
            {tx("Internal Use Only", "Internal Use Only")}
          </span>
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-petro-yellow animate-ping opacity-60" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-petro-yellow" />
        </div>
        <span className="text-[9px] text-white/40 font-medium">© 2026 PT Petrokimia Gresik</span>
      </div>
    </aside>
  );
}