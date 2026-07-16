"use client";

import Link from "next/link";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { t, getLanguage } from "@/utils/i18n";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

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
    if (!token) {
      setStatus("error");
      setMessage("Tautan verifikasi tidak valid atau tidak ditemukan.");
      return;
    }

    const verifyToken = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/auth/verify-email?token=${token}`, {
          method: "GET",
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Gagal memverifikasi email.");
        }
        setStatus("success");
        setMessage(data.message || "Email Anda berhasil diverifikasi!");
      } catch (err: any) {
        setStatus("error");
        setMessage(err.message || "Terjadi kesalahan saat memverifikasi email Anda.");
      }
    };

    verifyToken();
  }, [token]);

  return (
    <div className="w-full max-w-xl bg-white rounded-2xl shadow-sm border border-stone-200/85 p-10 text-center">
      {/* ── STATE: LOADING ─────────────────────────────────────── */}
      {status === "loading" && (
        <div className="space-y-6">
          <div className="flex justify-center">
            <div className="w-14 h-14 border-4 border-stone-100 border-t-petro-green rounded-full animate-spin"></div>
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-stone-900">{t("Verifying Account")}</h2>
            <p className="text-sm text-stone-500 font-semibold mt-2">
              {t("Please wait a moment while we activate your account...")}
            </p>
          </div>
        </div>
      )}

      {/* ── STATE: SUCCESS ─────────────────────────────────────── */}
      {status === "success" && (
        <div className="space-y-8">
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full bg-emerald-50 border-2 border-emerald-100 flex items-center justify-center shadow-sm">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 text-emerald-600">
                <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.6Z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-stone-900">{t("Verification Successful!")}</h2>
            <p className="text-sm text-emerald-600 font-bold mt-2">✓ {message}</p>
            <p className="text-sm text-stone-500 font-semibold mt-1">
              {t("Your account is now active. Please sign in to access the platform.")}
            </p>
          </div>
          <Link
            href="/login"
            className="block w-full py-3 bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm rounded-xl shadow transition-all duration-200"
          >
            {t("Sign in to My Account")}
          </Link>
        </div>
      )}

      {/* ── STATE: ERROR ───────────────────────────────────────── */}
      {status === "error" && (
        <div className="space-y-8">
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full bg-red-50 border-2 border-red-100 flex items-center justify-center shadow-sm">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 text-red-600">
                <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25Zm-1.72 6.97a.75.75 0 1 0-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 1 0 1.06 1.06L12 13.06l1.72 1.72a.75.75 0 1 0 1.06-1.06L13.06 12l1.72-1.72a.75.75 0 1 0-1.06-1.06L12 10.94l-1.72-1.72Z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-stone-900">{t("Verification Failed")}</h2>
            <p className="text-sm text-red-600 font-bold mt-2">✗ {message}</p>
            <p className="text-sm text-stone-500 font-semibold mt-1">
              {t("The verification token may have expired or is invalid. Please request a new link.")}
            </p>
          </div>
          <Link
            href="/login"
            className="block w-full py-3 bg-stone-100 hover:bg-stone-200 text-stone-700 font-bold text-sm rounded-xl transition-all duration-200"
          >
            {t("Back to Login")}
          </Link>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-petro-bg-warm p-6">
      <Suspense fallback={
        <div className="w-full max-w-xl bg-white rounded-2xl shadow-sm border border-stone-200/85 p-10 text-center">
          <div className="w-14 h-14 border-4 border-stone-100 border-t-petro-green rounded-full animate-spin mx-auto mb-6"></div>
          <h2 className="text-xl font-extrabold text-stone-900">{t("Loading")}</h2>
        </div>
      }>
        <VerifyEmailContent />
      </Suspense>
    </div>
  );
}
