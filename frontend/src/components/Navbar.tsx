"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { createPortal } from "react-dom";
import { t, getLanguage } from "@/utils/i18n";
import { API_BASE_URL } from "@/utils/api";
import NotificationsMenu from "@/components/navbar/NotificationsMenu";

function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffInSec = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (isNaN(diffInSec) || diffInSec < 60) return "Just now";
  if (diffInSec < 3600) return `${Math.floor(diffInSec / 60)}m ago`;
  if (diffInSec < 86400) return `${Math.floor(diffInSec / 3600)}h ago`;
  return `${Math.floor(diffInSec / 86400)}d ago`;
}

export default function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [apiNotifications, setApiNotifications] = useState<any[]>([]);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const [lang, setLang] = useState("English");

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

  const getPageTitle = () => {
    if (pathname?.startsWith("/generate")) return tx("Generate Report", "Generate Report");
    if (pathname?.startsWith("/history")) return tx("Report History", "Report History");
    if (pathname?.startsWith("/settings")) return tx("Settings", "Settings");
    return tx("Dashboard", "Dashboard");
  };

  const fetchNotifications = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/notifications`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        const formatted = items.map((n: any) => ({
          id: n.id,
          type: n.type || "info",
          title: n.title,
          sub: n.message,
          time: formatRelativeTime(n.created_at),
          unread: !n.is_read,
          href: n.link || "/history"
        }));
        setApiNotifications(formatted);
      }
    } catch (err) {
      console.warn("Failed to fetch notifications:", err);
    }
  };

  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem("token");
      if (!token) { router.push("/login"); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Session expired");
        setUser(await res.json());

        try {
          const settingsRes = await fetch(`${API_BASE_URL}/api/v1/settings/`, {
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
    fetchNotifications();

    const intervalId = setInterval(fetchNotifications, 15000);

    window.addEventListener("user_profile_updated", fetchUser);
    return () => {
      window.removeEventListener("user_profile_updated", fetchUser);
      clearInterval(intervalId);
    };
  }, [router]);

  const handleMarkAllRead = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/notifications/read-all`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        setApiNotifications(prev => prev.map(n => ({ ...n, unread: false })));
      }
    } catch (err) {
      console.error("Failed to mark notifications as read:", err);
    }
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setShowUserMenu(false);
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
              <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
            </svg>
          </div>
        );
    }
  };

  return (
    <header className="h-20 border-b border-stone-200/80 bg-stone-50/80 backdrop-blur-md sticky top-0 z-40 px-4 md:px-8 flex items-center justify-between transition-all duration-300">

      <div className="flex items-center gap-3 md:gap-4">
        {/* Mobile Hamburger Toggle Button */}
        <button
          onClick={() => window.dispatchEvent(new Event("toggle_mobile_sidebar"))}
          className="p-2 rounded-xl border border-stone-200 bg-white text-stone-600 hover:text-petro-green hover:border-petro-green/40 md:hidden transition-all shadow-sm cursor-pointer"
          title="Toggle Navigation Menu"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>

        <img
          src="/LOGO_PETRO_DANANTARA.png"
          alt="Petrokimia Gresik Logo"
          className="h-7 md:h-9 w-auto object-contain transition-transform duration-300 hover:scale-105"
        />
        <div className="w-1 h-7 md:h-8 bg-petro-yellow rounded-full shrink-0 shadow-sm hidden sm:block" />
        <div className="flex flex-col text-left">
          <span className="text-[9px] md:text-[10px] text-stone-400 font-extrabold uppercase tracking-widest truncate">
            {tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}
          </span>
          <h1 className="text-sm md:text-base font-black text-stone-900 leading-none mt-1 tracking-wide truncate">{getPageTitle()}</h1>
        </div>
      </div>

      <div className="flex items-center gap-4.5">

        <NotificationsMenu
          mounted={mounted}
          tx={tx}
          allNotifications={apiNotifications}
          getNotifIcon={getNotifIcon}
          showUserMenu={showUserMenu}
          setShowUserMenu={setShowUserMenu}
          onMarkAllRead={handleMarkAllRead}
        />

        <div className="relative" ref={userMenuRef}>
          {user ? (
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
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
                <Link href="/settings?tab=account" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-bold text-left">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                  </svg>
                  {tx("My Profile", "My Profile")}
                </Link>
                <Link href="/settings?tab=general" onClick={() => setShowUserMenu(false)} className="flex items-center gap-2.5 px-4 py-2.5 text-xs text-stone-700 hover:bg-stone-50 transition-colors duration-150 font-bold text-left">
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

    </header>
  );
}