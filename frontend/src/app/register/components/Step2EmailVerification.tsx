import { useState } from "react";
import Link from "next/link";
import { t } from "@/utils/i18n";

interface Step2EmailVerificationProps {
  email: string;
  onBack: () => void;
}

export default function Step2EmailVerification({
  email,
  onBack,
}: Step2EmailVerificationProps) {
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleResend = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mengirim ulang email verifikasi.");
      setResent(true);
      setTimeout(() => setResent(false), 6000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-[560px] bg-white rounded-2xl shadow-sm border border-stone-200/80 p-10 sm:p-12">
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900 font-semibold transition-colors cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {t("Back")}
        </button>
        <span className="text-sm font-bold text-petro-green">{t("Step 2 of 2")}</span>
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-extrabold text-stone-900">{t("Confirm Your Account")}</h2>
        <p className="text-sm text-stone-500 font-medium mt-1">{t("We've sent a verification link to your email")}</p>
      </div>

      {error && (
        <div className="mb-5 bg-red-50 border border-red-200 text-red-700 text-xs font-medium px-4 py-3 rounded-xl text-center">
          {error}
        </div>
      )}

      {/* Email Envelope Illustration */}
      <div className="flex justify-center mb-8">
        <div className="relative">
          <svg viewBox="0 0 150 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-44 h-36">
            {/* Sparkles & Dots */}
            <circle cx="20" cy="40" r="2.5" fill="#EAB308" className="animate-pulse" opacity="0.8" />
            <circle cx="130" cy="30" r="1.5" fill="#10B981" className="animate-ping" />
            <circle cx="125" cy="80" r="2" fill="#EAB308" />
            <path d="M12 25 L15 28 L12 31 L9 28 Z" fill="#EAB308" opacity="0.6" />
            <path d="M138 65 L140 67 L138 69 L136 67 Z" fill="#10B981" opacity="0.5" />

            {/* Envelope Back & Inside Background */}
            <path d="M25 55 L25 100 C25 104 28 107 32 107 L118 107 C122 107 125 104 125 100 L125 55 Z" fill="#D1FAE5" />
            <path d="M25 55 L75 22 L125 55" stroke="#A7F3D0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

            {/* The Document sliding out */}
            <g className="animate-bounce" style={{ animationDuration: '3s' }}>
              <rect x="42" y="32" width="66" height="50" rx="4" fill="#FFFFFF" filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.05))" />
              <line x1="50" y1="42" x2="100" y2="42" stroke="#E2E8F0" strokeWidth="3" strokeLinecap="round" />
              <line x1="50" y1="52" x2="90" y2="52" stroke="#E2E8F0" strokeWidth="3" strokeLinecap="round" />
              <line x1="50" y1="62" x2="80" y2="62" stroke="#E2E8F0" strokeWidth="3" strokeLinecap="round" />
              {/* Checkmark Badge on the Document */}
              <circle cx="90" cy="58" r="9" fill="#10B981" />
              <path d="M87 58 L89 60 L93 56" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </g>

            {/* Envelope Sides & Front Flaps (drawn over the document) */}
            <path d="M25 55 L75 78 L125 55" fill="#E6FDF4" opacity="0.95" />
            <path d="M25 107 L75 77 L125 107" fill="#E6FDF4" opacity="0.9" />
            <path d="M25 55 L25 100 C25 104 28 107 32 107 L118 107 C122 107 125 104 125 100 L125 55 Z" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>

      {/* Message */}
      <div className="text-center space-y-2 mb-8">
        <p className="text-sm font-semibold text-stone-700">
          {t("Please check your email")}{" "}
          <span className="text-petro-green font-bold">({email})</span>
        </p>
        <p className="text-sm text-stone-500 font-medium">
          {t("and click the verification link to activate your account.")}
        </p>
      </div>

      {/* Resend */}
      <div className="text-center space-y-2">
        <p className="text-sm text-stone-500 font-medium">{t("Didn't receive the email?")}</p>
        {resent ? (
          <p className="text-sm text-emerald-600 font-bold">✓ {t("Verification email resent!")}</p>
        ) : (
          <button
            onClick={handleResend}
            disabled={loading}
            className="text-sm text-petro-green font-bold hover:underline transition-colors disabled:opacity-50 cursor-pointer"
          >
            {loading ? t("Resending...") : t("Resend verification email")}
          </button>
        )}
      </div>

      <p className="text-center text-sm text-stone-500 font-medium mt-8">
        {t("Already have an account?")}{" "}
        <Link href="/login" className="text-petro-green font-bold hover:underline">{t("Sign In")}</Link>
      </p>
    </div>
  );
}
