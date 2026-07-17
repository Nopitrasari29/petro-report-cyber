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
  const [showAllNotifModal, setShowAllNotifModal] = useState(false); // State untuk mengontrol Modal Semua Notifikasi
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const [lang, setLang] = useState("English");

  // ==========================================
  // EFFECT 1: Pengaman Hidrasi (Hydration Guard)
  // ==========================================
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

  // Judul modul dinamis berdasarkan path URL
  const getPageTitle = () => {
    if (pathname?.startsWith("/generate")) return tx("Generate Report", "Generate Report");
    if (pathname?.startsWith("/history")) return tx("Report History", "Report History");
    if (pathname?.startsWith("/settings")) return tx("Settings", "Settings");
    return tx("Dashboard", "Dashboard");
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

        // Sinkronisasi otomatis bahasa UI dari pengaturan database
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

  // Handler klik di luar untuk menutup dropdown otomatis
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

  // Data Contoh Notifikasi Lengkap (Ditambah Item Tambahan untuk Modal)
  const allNotifications = [
    {
      id: 1,
      type: "success",
      title: tx("Report Generated", "Report Generated"),
      sub: tx("SOC Executive Summary - July 2026", "SOC Executive Summary - July 2026"),
      time: "2m ago",
      unread: true,
      href: "/history"
    },
    {
      id: 2,
      type: "warning",
      title: tx("High Alert Detected", "High Alert Detected"),
      sub: tx("22 new critical events flagged", "22 new critical events flagged"),
      time: "18m ago",
      unread: true,
      href: "/history"
    },
    {
      id: 3,
      type: "info",
      title: tx("Export Ready", "Export Ready"),
      sub: tx("VAPT Report Q2 PDF is ready", "VAPT Report Q2 PDF is ready"),
      time: "1h ago",
      unread: false,
      href: "/history"
    },
    {
      id: 4,
      type: "success",
      title: tx("Data Parsing Complete", "Data Parsing Complete"),
      sub: tx("Successfully parsed email_threat_report_july.pdf", "Successfully parsed email_threat_report_july.pdf"),
      time: "3h ago",
      unread: false,
      href: "/history"
    },
    {
      id: 5,
      type: "warning",
      title: tx("Suspicious Login Attempt", "Suspicious Login Attempt"),
      sub: tx("Failed login attempt from unrecognized IP address", "Failed login attempt from unrecognized IP address"),
      time: "1d ago",
      unread: false,
      href: "/settings"
    }
  ];

  // Helper Renderer Ikon SVG Profesional (Bebas dari Emoji)
  const getNotifIcon = (type: string) => {
    switch (type) {
      case "success":
        return (
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-100/30">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
            </svg>
          </div>
        );
      case "warning":
        return (
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0 border border-amber-100/30">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
        );
      case "info":
      default:
        return (
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-100/30">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>
        );
    }
  };

  return (
    // h-20 (80px) memberikan ruang napas yang lega
    <header className="h-20 border-b border-stone-200/60 bg-white/80 backdrop-blur-xl flex items-center justify-between px-10 sticky top-0 z-20 w-full transition-all duration-300">

      {/* Sisi Kiri: Breadcrumb Module dengan Garis Vertikal Emas Petrokimia */}
      <div className="flex items-center gap-4">
        <div className="w-1 h-9 bg-petro-yellow rounded-full shrink-0 shadow-sm" />
        <div className="flex flex-col text-left">
          <span className="text-[10px] text-stone-400 font-extrabold uppercase tracking-widest">
            {tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}
          </span>
          <h1 className="text-base font-black text-stone-900 leading-none mt-1 tracking-wide">{getPageTitle()}</h1>
        </div>
      </div>

      {/* Sisi Tengah: Kolom Pencarian (w-96) */}
      <div className="relative w-96 group">
        <span className="absolute inset-y-0 left-3.5 flex items-center text-stone-400 transition-colors duration-250 group-focus-within:text-petro-green">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.602 10.602Z" />
          </svg>
        </span>
        <input
          type="text"
          placeholder={tx("Search reports, alerts, templates...", "Search reports, alerts, templates...")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-stone-100/80 border border-stone-200/80 rounded-xl pl-10 pr-4 py-2.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-petro-green/10 focus:border-petro-green focus:bg-white transition-all duration-200 placeholder:text-stone-400"
        />
      </div>

      {/* Sisi Kanan: Notifikasi & Widget Profil Dinamis */}
      <div className="flex items-center gap-4.5">

        {/* Lonceng Notifikasi */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => { setShowNotif(!showNotif); setShowUserMenu(false); }}
            className="relative w-11 h-10.5 rounded-xl bg-white border border-stone-200 flex items-center justify-center text-stone-500 hover:text-petro-green hover:border-petro-green/30 hover:shadow-sm transition-all duration-200 group cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:scale-110">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
            </svg>

            {/* Lencana Jumlah Notifikasi Berbentuk Angka */}
            <span className="absolute -top-1 -right-1 min-w-5 h-5 px-1.5 rounded-full bg-red-500 text-[10px] font-black text-white flex items-center justify-center border-2 border-white shadow-sm">
              3
            </span>
          </button>

          {/* Dropdown Notifikasi dengan Garis Emas Petrokimia di Atas */}
          {showNotif && (
            <div className="absolute right-0 top-13.5 w-80 bg-white rounded-2xl shadow-xl border border-stone-200/80 border-t-4 border-t-petro-yellow z-50 animate-slideDown overflow-hidden">
              <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
                <span className="text-xs font-extrabold text-stone-800">{tx("Notifications", "Notifications")}</span>
                <span className="text-[10px] text-petro-green font-bold cursor-pointer hover:underline">{tx("Mark all read", "Mark all read")}</span>
              </div>
              <div className="divide-y divide-stone-50">
                {/* Tampilkan 3 notifikasi teratas di dropdown */}
                {allNotifications.slice(0, 3).map((n) => (
                  <Link
                    href={n.href}
                    key={n.id}
                    onClick={() => setShowNotif(false)}
                    className="flex gap-3 px-4 py-3 hover:bg-stone-50/50 cursor-pointer transition-colors duration-150 text-left items-start relative block"
                  >
                    {getNotifIcon(n.type)}
                    <div className="flex-1 min-w-0 text-left pr-4">
                      <p className="text-xs font-bold text-stone-800 truncate">{n.title}</p>
                      <p className="text-[10px] text-stone-500 font-semibold truncate mt-0.5">{n.sub}</p>
                      <span className="text-[9px] text-stone-400 font-bold block mt-1">{n.time}</span>
                    </div>
                    {n.unread && (
                      <span className="w-2 h-2 rounded-full bg-emerald-600 shrink-0 self-center absolute right-4 shadow-sm" />
                    )}
                  </Link>
                ))}
              </div>

              {/* REVISI: Mengklik "Lihat semua" kini memicu pembukaan Modal Popup Semua Notifikasi */}
              <div className="px-4 py-2.5 border-t border-stone-100 text-center">
                <button
                  onClick={() => { setShowAllNotifModal(true); setShowNotif(false); }}
                  className="w-full text-xs text-petro-green font-bold cursor-pointer hover:underline text-center focus:outline-none"
                >
                  {tx("View all notifications", "View all notifications")}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Card Widget */}
        <div className="relative" ref={userMenuRef}>
          {user ? (
            <button
              onClick={() => { setShowUserMenu(!showUserMenu); setShowNotif(false); }}
              className="flex items-center gap-3 bg-white border border-stone-200/80 pl-2 pr-4 py-2 rounded-xl shadow-sm hover:shadow-md hover:border-stone-300 transition-all duration-200 group cursor-pointer"
            >
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name || user.username} className="w-8 h-8 rounded-lg border border-stone-200/80 object-cover" />
              ) : (
                <div className="w-8 h-8 rounded-lg bg-petro-yellow flex items-center justify-center font-extrabold text-xs uppercase text-white shrink-0 shadow-inner">
                  {initials}
                </div>
              )}
              <div className="flex flex-col text-left max-w-[120px]">
                <span className="text-xs font-black text-stone-800 leading-none truncate">{user.full_name || user.username}</span>
                <span className="text-[9px] text-stone-400 font-bold mt-1.5 truncate uppercase tracking-wider">{user.role || "SOC Analyst"}</span>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.8} stroke="currentColor" className={`w-2.5 h-2.5 text-stone-400 transition-transform duration-200 ${showUserMenu ? "rotate-180" : ""}`}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          ) : (
            <div className="w-36 h-10 skeleton rounded-xl animate-pulse" />
          )}

          {/* Dropdown Menu Pengguna dengan Garis Emas Petrokimia di Atas */}
          {showUserMenu && user && (
            <div className="absolute right-0 top-13.5 w-52 bg-white rounded-2xl shadow-xl border border-stone-200/80 z-50 animate-slideDown overflow-hidden border-t-4 border-t-petro-yellow">
              <div className="px-4 py-3 border-b border-stone-100 text-left">
                <p className="text-xs font-extrabold text-stone-855 truncate">{user.full_name || user.username}</p>
                <p className="text-[10px] text-stone-400 font-semibold truncate mt-0.5">{user.email}</p>
              </div>
              <div className="py-1">
                <Link href="/settings" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-bold text-left">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                  </svg>
                  {tx("My Profile", "My Profile")}
                </Link>
                <Link href="/settings" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-bold text-left">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  </svg>
                  {tx("Settings", "Settings")}
                </Link>
              </div>
              <div className="border-t border-stone-100 py-1">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2.5 w-full px-4 py-2.5 text-xs text-red-655 hover:bg-red-50/60 transition-colors duration-150 font-bold text-left cursor-pointer"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.3} stroke="currentColor" className="w-3.5 h-3.5 text-red-500">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                  </svg>
                  {tx("Sign Out", "Sign Out")}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── REVISI: MODAL POPUP "SEMUA NOTIFIKASI" (INTERAKTIF & INTEGRATIF) ── */}
      {showAllNotifModal && (
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-md flex items-center justify-center z-50 animate-fadeIn px-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-stone-200/80 w-full max-w-xl max-h-[80vh] flex flex-col overflow-hidden animate-scaleIn border-t-4 border-t-petro-yellow">

            {/* Header Modal */}
            <div className="px-6 py-4.5 border-b border-stone-100 flex items-center justify-between">
              <div className="text-left">
                <h3 className="text-base font-black text-stone-900">{tx("All Notifications", "All Notifications")}</h3>
                <p className="text-[10px] text-stone-400 font-semibold mt-1">{tx("View and manage your recent system alerts and updates", "View and manage your recent system alerts and updates")}</p>
              </div>
              <button
                onClick={() => setShowAllNotifModal(false)}
                className="w-8 h-8 rounded-full hover:bg-stone-50 border border-stone-200 flex items-center justify-center text-stone-500 hover:text-stone-700 transition-all cursor-pointer focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* List Notifikasi (Scrollable) */}
            <div className="flex-1 overflow-y-auto divide-y divide-stone-100 px-2 py-1">
              {allNotifications.map((n) => (
                <Link
                  href={n.href}
                  key={n.id}
                  onClick={() => setShowAllNotifModal(false)}
                  className="flex gap-4 p-5 hover:bg-stone-50/50 transition-colors duration-150 text-left items-start relative rounded-2xl my-1 block"
                >
                  {getNotifIcon(n.type)}
                  <div className="flex-1 min-w-0 pr-6 text-left">
                    <p className="text-xs font-black text-stone-900">{n.title}</p>
                    <p className="text-[10px] text-stone-500 font-semibold mt-1 leading-relaxed">{n.sub}</p>
                    <span className="text-[9px] text-stone-450 font-bold block mt-2">{n.time}</span>
                  </div>
                  {n.unread && (
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 shrink-0 self-center absolute right-6 shadow-sm" />
                  )}
                </Link>
              ))}
            </div>

            {/* Footer Modal */}
            <div className="px-6 py-4 border-t border-stone-100 flex items-center justify-between bg-stone-50/50">
              <span className="text-xs text-petro-green font-extrabold cursor-pointer hover:underline">{tx("Mark all read", "Mark all read")}</span>
              <button
                onClick={() => setShowAllNotifModal(false)}
                className="px-4 py-2 bg-stone-200 hover:bg-stone-300 text-stone-700 text-xs font-extrabold rounded-xl transition-all cursor-pointer focus:outline-none"
              >
                {tx("Close", "Close")}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}