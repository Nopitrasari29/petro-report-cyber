import { useState, useRef, useEffect } from "react";
import Link from "next/link";

interface UserProfileMenuProps {
  user: any;
  tx: (key: string, fallback: string) => string;
  initials: string;
  handleLogout: () => void;
}

export default function UserProfileMenu({
  user,
  tx,
  initials,
  handleLogout,
}: UserProfileMenuProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
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
            <span className="text-xs font-black text-stone-850 leading-none truncate">{user.full_name || user.username}</span>
            <span className="text-[9px] text-stone-400 font-bold mt-1.5 truncate uppercase tracking-wider">{user.role || "SOC Analyst"}</span>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.8} stroke="currentColor" className={`w-2.5 h-2.5 text-stone-400 transition-transform duration-200 ${showUserMenu ? "rotate-180" : ""}`}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
      ) : (
        <div className="w-36 h-10 skeleton rounded-xl animate-pulse" />
      )}

      {/* User Dropdown Menu */}
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
  );
}
