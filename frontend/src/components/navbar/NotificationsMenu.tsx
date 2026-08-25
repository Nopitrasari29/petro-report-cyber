import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import ConfirmDialog from "@/components/ConfirmDialog";

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
  onMarkAllRead?: () => void;
  onMarkSingleRead?: (id: number) => void;
  onDeleteNotification?: (id: number) => void;
  onBulkDeleteNotifications?: (ids: number[]) => void;
  onDeleteAllRead?: () => void;
}

const TrashIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className={className}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
  </svg>
);

export default function NotificationsMenu({
  mounted,
  tx,
  allNotifications,
  getNotifIcon,
  setShowUserMenu,
  onMarkAllRead,
  onMarkSingleRead,
  onDeleteNotification,
  onBulkDeleteNotifications,
  onDeleteAllRead,
}: NotificationsMenuProps) {
  const [showNotif, setShowNotif] = useState(false);
  const [showAllNotifModal, setShowAllNotifModal] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [pendingAction, setPendingAction] = useState<
    { type: "bulk"; ids: number[] } | { type: "clearRead" } | null
  >(null);
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

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === allNotifications.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(allNotifications.map((n) => n.id));
    }
  };

  const closeModal = () => {
    setShowAllNotifModal(false);
    setSelectedIds([]);
  };

  const confirmPendingAction = () => {
    if (!pendingAction) return;
    if (pendingAction.type === "bulk") {
      onBulkDeleteNotifications?.(pendingAction.ids);
      setSelectedIds([]);
    } else {
      onDeleteAllRead?.();
    }
    setPendingAction(null);
  };

  const readCount = allNotifications.filter((n) => !n.unread).length;

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
            <button
              onClick={onMarkAllRead}
              className="text-[10px] text-petro-green font-bold cursor-pointer hover:underline focus:outline-none"
            >
              {tx("Mark all read", "Mark all read")}
            </button>
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
                  onClick={() => {
                    setShowNotif(false);
                    if (n.unread) onMarkSingleRead?.(n.id);
                  }}
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

      {/* Modal Popup All Notifications dengan Teleportasi createPortal */}
      {showAllNotifModal && mounted && createPortal(
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-md flex items-center justify-center z-[9999] animate-fadeIn px-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-stone-200/80 w-full max-w-xl max-h-[80vh] flex flex-col overflow-hidden animate-scaleIn border-t-4 border-t-petro-yellow">

            {/* Header Modal */}
            <div className="px-6 py-4.5 border-b border-stone-100 flex items-center justify-between">
              <div className="text-left">
                <h3 className="text-base font-black text-stone-900">{tx("All Notifications", "All Notifications")}</h3>
                <p className="text-[10px] text-stone-400 font-semibold mt-1">{tx("View and manage your recent system alerts and updates", "View and manage your recent system alerts and updates")}</p>
              </div>
              <button
                onClick={closeModal}
                className="w-8 h-8 rounded-full hover:bg-stone-50 border border-stone-200 flex items-center justify-center text-stone-500 hover:text-stone-700 transition-all cursor-pointer focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Action Bar — mode ganda: pilih & hapus terpilih, ATAU (kalau tidak ada yg dipilih)
                pilih semua + hapus yang sudah dibaca sekaligus. */}
            {allNotifications.length > 0 && (
              selectedIds.length > 0 ? (
                <div className="px-6 py-2.5 border-b border-stone-100 bg-red-50/60 flex items-center justify-between animate-fadeIn">
                  <span className="text-xs font-bold text-red-700">
                    {selectedIds.length} {tx("notification(s) selected", "notification(s) selected")}
                  </span>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setSelectedIds([])}
                      className="text-xs text-stone-500 font-bold hover:underline cursor-pointer focus:outline-none"
                    >
                      {tx("Cancel", "Batal")}
                    </button>
                    <button
                      onClick={() => setPendingAction({ type: "bulk", ids: selectedIds })}
                      className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-extrabold text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <TrashIcon className="w-3.5 h-3.5" />
                      {tx("Delete Selected", "Hapus Terpilih")}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="px-6 py-2.5 border-b border-stone-100 flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs font-bold text-stone-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={false}
                      onChange={toggleSelectAll}
                      className="w-3.5 h-3.5 rounded text-petro-green focus:ring-petro-green border-stone-300"
                    />
                    {tx("Select All", "Pilih Semua")}
                  </label>
                  <button
                    onClick={() => setPendingAction({ type: "clearRead" })}
                    disabled={readCount === 0}
                    className="text-[11px] text-red-600 font-bold hover:underline cursor-pointer focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:no-underline"
                  >
                    {tx("Delete Read Notifications", "Hapus yang Sudah Dibaca")}
                  </button>
                </div>
              )
            )}

            {/* List Notifikasi (Scrollable) */}
            <div className="flex-1 overflow-y-auto divide-y divide-stone-100 px-2 py-1">
              {allNotifications.length === 0 ? (
                <div className="p-12 text-center text-xs text-stone-400 font-bold">
                  {tx("No notifications", "No notifications")}
                </div>
              ) : (
                allNotifications.map((n) => (
                  <div
                    key={n.id}
                    className="flex gap-3 p-5 hover:bg-stone-50/50 transition-colors duration-150 items-start rounded-2xl my-1"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(n.id)}
                      onChange={() => toggleSelect(n.id)}
                      className="mt-1 w-3.5 h-3.5 rounded text-petro-green focus:ring-petro-green border-stone-300 shrink-0"
                    />
                    <Link
                      href={n.href}
                      onClick={() => {
                        closeModal();
                        if (n.unread) onMarkSingleRead?.(n.id);
                      }}
                      className="flex gap-4 flex-1 min-w-0 text-left items-start"
                    >
                      {getNotifIcon(n.type)}
                      <div className="flex-1 min-w-0 text-left">
                        <p className="text-xs font-black text-stone-900">{n.title}</p>
                        <p className="text-[10px] text-stone-500 font-semibold mt-1 leading-relaxed">{n.sub}</p>
                        <span className="text-[9px] text-stone-455 font-bold block mt-2">{n.time}</span>
                      </div>
                    </Link>
                    {n.unread && (
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 shrink-0 self-center shadow-sm" />
                    )}
                    <button
                      onClick={() => onDeleteNotification?.(n.id)}
                      title={tx("Delete", "Hapus")}
                      className="p-1.5 rounded-lg text-stone-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer shrink-0"
                    >
                      <TrashIcon className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Footer Modal */}
            <div className="px-6 py-4 border-t border-stone-100 flex items-center justify-between bg-stone-50/50">
              <button
                onClick={onMarkAllRead}
                className="text-xs text-petro-green font-extrabold cursor-pointer hover:underline focus:outline-none"
              >
                {tx("Mark all read", "Mark all read")}
              </button>
              <button
                onClick={closeModal}
                className="px-4 py-2 bg-stone-200 hover:bg-stone-300 text-stone-700 text-xs font-extrabold rounded-xl transition-all cursor-pointer focus:outline-none"
              >
                {tx("Close", "Close")}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* createPortal SENGAJA — ConfirmDialog ini dipicu dari DALAM modal "All Notifications"
          yang sudah dirender lewat portal ke document.body dengan z-[9999]; kalau ConfirmDialog
          dirender inline di sini (di dalam tree Navbar biasa), z-index-nya tidak pernah bisa
          menang lawan z-[9999] itu walau class-nya lebih tinggi (kemungkinan besar terjebak di
          stacking context ancestor Navbar) — BUG DITEMUKAN saat verifikasi: dialog konfirmasi
          hapus notifikasi selalu tersembunyi di belakang modal, klik tombol "Hapus" tidak bisa
          kena sama sekali. */}
      {mounted && createPortal(
        <ConfirmDialog
          open={pendingAction !== null}
          title={
            pendingAction?.type === "bulk"
              ? tx("Delete Notifications", "Hapus Notifikasi")
              : tx("Delete Read Notifications", "Hapus yang Sudah Dibaca")
          }
          message={
            pendingAction?.type === "bulk"
              ? tx(
                  "Apakah Anda yakin ingin menghapus {count} notifikasi terpilih? Tindakan ini tidak bisa dibatalkan.",
                  "Are you sure you want to delete {count} selected notification(s)? This action cannot be undone.",
                ).replace("{count}", String(pendingAction.ids.length))
              : tx(
                  "Apakah Anda yakin ingin menghapus semua notifikasi yang sudah dibaca? Tindakan ini tidak bisa dibatalkan.",
                  "Are you sure you want to delete all read notifications? This action cannot be undone.",
                )
          }
          danger
          confirmLabel={tx("Delete", "Hapus")}
          onConfirm={confirmPendingAction}
          onCancel={() => setPendingAction(null)}
          zIndexClass="z-[10000]"
        />,
        document.body
      )}
    </div>
  );
}
