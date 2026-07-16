"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NotFound() {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-petro-bg-warm flex flex-col items-center justify-center p-6 selection:bg-petro-green/20 selection:text-petro-green">
      
      {/* ─── DIAGNOSTIC WINDOW ────────────────────────────────────────── */}
      <div className="w-full max-w-2xl bg-white border border-stone-200 shadow-lg rounded-2xl overflow-hidden flex flex-col">
        {/* Window Header */}
        <div className="bg-stone-50 border-b border-stone-150 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded-full bg-red-400"></span>
            <span className="w-3.5 h-3.5 rounded-full bg-yellow-400"></span>
            <span className="w-3.5 h-3.5 rounded-full bg-green-400"></span>
          </div>
          <span className="text-[10px] font-mono font-bold tracking-wider text-stone-400 uppercase select-none">
            System Console // HTTP_404_NOT_FOUND
          </span>
          <span className="w-14"></span> {/* Spacer */}
        </div>

        {/* Window Body */}
        <div className="p-8 lg:p-12 flex flex-col items-center text-center space-y-6">
          {/* Big Stylized Error Number */}
          <div className="relative">
            <h1 className="text-8xl md:text-9xl font-black text-transparent bg-clip-text bg-gradient-to-br from-petro-green to-stone-500 tracking-tight select-none leading-none">
              404
            </h1>
            <span className="absolute -top-3 -right-3 w-5 h-5 rounded-full bg-petro-yellow border-4 border-white shadow animate-bounce"></span>
          </div>

          {/* Copywriting */}
          <div className="space-y-2">
            <h2 className="text-xl md:text-2xl font-extrabold text-stone-900 tracking-tight">
              Halaman Tidak Ditemukan
            </h2>
            <p className="text-xs font-bold text-petro-green uppercase tracking-widest">
              Sistem Manajemen Laporan Bulanan SOC
            </p>
          </div>

          <p className="text-sm text-stone-500 font-medium leading-relaxed max-w-md">
            Sistem tidak dapat mendeteksi halaman atau dokumen keamanan siber yang Anda minta. Rute ini belum terdaftar, telah dipindahkan, atau sedang dalam pemeliharaan.
          </p>

          {/* Diagnostic Console Panel (Grid info) */}
          <div className="w-full bg-stone-50 border border-stone-200 rounded-xl p-5 text-left font-mono text-xs space-y-2">
            <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
              <span className="text-stone-400">REQUEST_PATH:</span>
              <span className="text-stone-700 font-bold break-all max-w-[280px]">{pathname || "/unknown"}</span>
            </div>
            <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
              <span className="text-stone-400">ERROR_CODE:</span>
              <span className="text-red-650 font-bold">ERR_ROUTE_NOT_FOUND</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-stone-400">TI_DEPARTMENT:</span>
              <span className="text-stone-600 font-semibold">Mitra Bisnis Layanan TI PKG</span>
            </div>
          </div>

          {/* Core Actions */}
          <div className="w-full pt-4 border-t border-stone-100 flex flex-col sm:flex-row gap-3 justify-center">
            <Link 
              href="/" 
              className="px-6 py-3.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 flex items-center justify-center gap-2 group"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M9.293 2.293a1 1 0 0 1 1.414 0l7 7A1 1 0 0 1 17 11h-1v6a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-6H3a1 1 0 0 1-.707-1.707l7-7Z" clipRule="evenodd" />
              </svg>
              Kembali ke Beranda
            </Link>
            
            <button 
              onClick={() => window.history.back()} 
              className="px-6 py-3.5 rounded-xl bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-stone-500">
                <path fillRule="evenodd" d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z" clipRule="evenodd" />
              </svg>
              Kembali Sebelumnya
            </button>
          </div>

          {/* Quick Helpful Suggested Links */}
          <div className="flex items-center gap-6 text-[11px] font-bold text-stone-400">
            <span>Saran Modul:</span>
            <Link href="/generate" className="text-petro-green hover:underline">Generate Report</Link>
            <span className="w-1 h-1 rounded-full bg-stone-300"></span>
            <Link href="/history" className="text-petro-green hover:underline">Report History</Link>
          </div>
        </div>
      </div>

      {/* Decorative Corporate Footer Tag */}
      <div className="mt-12 flex items-center gap-2 opacity-60 hover:opacity-100 transition-opacity duration-200 select-none cursor-default">
        <img src="/LOGO_PETRO.png" alt="Petrokimia Logo" className="h-12 lg:h-14 w-auto object-contain shrink-0 -my-2 lg:-my-3" />
        <span className="text-[10px] font-black text-stone-600 tracking-widest uppercase">
          PT Petrokimia Gresik
        </span>
      </div>

    </div>
  );
}
