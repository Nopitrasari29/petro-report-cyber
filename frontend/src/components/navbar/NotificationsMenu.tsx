import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { t } from "@/utils/i18n";

interface NotificationItem {
  id: number;
  type: string;
  title: string;
  sub: string;
  time: string;
  unread: boolean;
  href: string;
}

interface NotificationsMenuProps {
  mounted: boolean;
  tx: (key: string, fallback: string) => string;
  allNotifications: NotificationItem[];
  getNotifIcon: (type: string) => React.ReactNode;
  showUserMenu: boolean;
  setShowUserMenu: (show: boolean) => void;
}

export default function NotificationsMenu({
  mounted,
  tx,
  allNotifications,
  getNotifIcon,
  setShowUserMenu,
}: NotificationsMenuProps) {
  const [showNotif, setShowNotif] = useState(false);
  const [showAllNotifModal, setShowAllNotifModal] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotif(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={notifRef}>
      {/* Notification Bell Button */}
      <button
        onClick={() => {
          setShowNotif(!showNotif);
          setShowUserMenu(false);
        }}
        className="relative w-11 h-10.5 rounded-xl bg-white border border-stone-200 flex items-center justify-center text-stone-500 hover:text-petro-green hover:border-petro-green/30 hover:shadow-sm transition-all duration-200 group cursor-pointer"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
        </svg>

        {/* Badge number */}
        {allNotifications.filter((n) => n.unread).length > 0 && (
          <span className="absolute -top-1 -right-1 min-w-5 h-5 px-1.5 rounded-full bg-red-500 text-[10px] font-black text-white flex items-center justify-center border-2 border-white shadow-sm">
            {allNotifications.filter((n) => n.unread).length}
          </span>
        )}
      </button>

      {/* Notifications Dropdown */}
      {showNotif && (
        <div className="absolute right-0 top-13.5 w-80 bg-white rounded-2xl shadow-xl border border-stone-200/80 border-t-4 border-t-petro-yellow z-50 animate-slideDown overflow-hidden">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
            <span className="text-xs font-extrabold text-stone-800">{tx("Notifications", "Notifications")}</span>
            <span className="text-[10px] text-petro-green font-bold cursor-pointer hover:underline">{tx("Mark all read", "Mark all read")}</span>
          </div>
          <div className="divide-y divide-stone-50">
            {allNotifications.length === 0 ? (
              <div className="p-8 text-center text-xs text-stone-400 font-bold">
                {tx("No notifications", "No notifications")}
              </div>
            ) : (
              allNotifications.slice(0, 3).map((n) => (
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
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-stone-100 text-center">
            <button
              onClick={() => {
                setShowAllNotifModal(true);
                setShowNotif(false);
              }}
              className="w-full text-xs text-petro-green font-bold cursor-pointer hover:underline text-center focus:outline-none"
            >
              {tx("View all notifications", "View all notifications")}
            </button>
          </div>
        </div>
      )}

      {/* Modal Popup All Notifications */}
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
              {allNotifications.length === 0 ? (
                <div className="p-12 text-center text-xs text-stone-400 font-bold">
                  {tx("No notifications", "No notifications")}
                </div>
              ) : (
                allNotifications.map((n) => (
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
                      <span className="text-[9px] text-stone-455 font-bold block mt-2">{n.time}</span>
                    </div>
                    {n.unread && (
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 shrink-0 self-center absolute right-6 shadow-sm" />
                    )}
                  </Link>
                ))
              )}
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
    </div>
  );
}
