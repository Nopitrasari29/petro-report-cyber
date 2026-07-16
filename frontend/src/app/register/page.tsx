"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, getLanguage } from "@/utils/i18n";

// ─── Shared Left Panel ───────────────────────────────────────────────────────
function AuthLeftPanel() {
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

  return (
    <div className="hidden lg:flex lg:w-[30%] xl:w-[33%] lg:min-w-[400px] shrink-0 bg-petro-green flex-col justify-between p-10 text-white">
      <Link href="/" className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-petro-yellow flex items-center justify-center shrink-0 shadow-sm">
          <span className="font-extrabold text-white text-base">P</span>
        </div>
        <div className="flex flex-col leading-none">
          <span className="font-extrabold text-base">{t("AI Security Reports")}</span>
          <span className="text-[10px] text-white/70 font-semibold uppercase tracking-wider mt-0.5">{t("PT Petrokimia Gresik")}</span>
        </div>
      </Link>

      {/* Center Content Group */}
      <div className="flex-1 flex flex-col justify-center gap-12 my-auto">
        {/* Hero text */}
        <div className="space-y-4 text-left">
          <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight">{t("AI-Powered SOC Reporting")}</h1>
          <p className="text-sm lg:text-base text-white/80 leading-relaxed font-medium">
            {t("Automate monthly SOC report generation with AI. Fast, accurate, and reliable.")}
          </p>
        </div>

        {/* Illustration */}
        <div className="flex justify-center">
          <img src="/soc-logo.png" alt="SOC Report Illustration" className="w-full max-w-[340px] object-contain h-auto transition-transform hover:scale-[1.02] duration-300" />
        </div>
      </div>

      {/* Small Bottom Spacer to keep balance */}
      <div className="h-2"></div>
    </div>
  );
}

// ─── Step 1: Account Details ──────────────────────────────────────────────────
function Step1({
  fullName, setFullName,
  email, setEmail,
  password, setPassword,
  confirmPassword, setConfirmPassword,
  showPassword, setShowPassword,
  showConfirm, setShowConfirm,
  onNext,
  error,
  loading,
}: any) {
  return (
    <div className="w-full max-w-[560px] bg-white rounded-2xl shadow-sm border border-stone-200/80 p-10 sm:p-12">
      <div className="flex items-center justify-between mb-6">
        <Link href="/login" className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900 font-semibold transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {t("Back")}
        </Link>
        <span className="text-sm font-bold text-petro-green">{t("Step 1 of 2")}</span>
      </div>

      <div className="mb-7">
        <h2 className="text-xl font-extrabold text-stone-900">{t("Create Your Account")}</h2>
        <p className="text-sm text-stone-500 font-medium mt-1">{t("Fill in your information to get started")}</p>
      </div>

      {error && (
        <div className="mb-5 bg-red-50 border border-red-200 text-red-700 text-xs font-medium px-4 py-3 rounded-xl">{error}</div>
      )}

      <form onSubmit={onNext} className="space-y-4">
        {/* Full Name */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-stone-700">{t("Full Name")}</label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
              </svg>
            </span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t("Enter your full name")}
              required
              autoComplete="off"
              className="w-full pl-10 pr-4 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            />
          </div>
        </div>

        {/* Email */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-stone-700">{t("Email")}</label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
              </svg>
            </span>
            <input
              type="text"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("Enter your email")}
              required
              autoComplete="off"
              className="w-full pl-10 pr-4 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            />
          </div>
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-stone-700">{t("Password")}</label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
            </span>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("Enter your password")}
              required
              minLength={8}
              autoComplete="new-password"
              className="w-full pl-10 pr-12 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
            </button>
          </div>
          <p className="text-[11px] text-stone-400 font-medium">{t("Minimum 8 characters with letters, numbers, and symbols")}</p>
        </div>

        {/* Confirm Password */}
        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-stone-700">{t("Confirm Password")}</label>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
            </span>
            <input
              type={showConfirm ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t("Confirm your password")}
              required
              autoComplete="new-password"
              className="w-full pl-10 pr-12 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            />
            <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm rounded-xl shadow transition-all duration-200 mt-2 disabled:opacity-60"
        >
          {loading ? t("Registering...") : t("Next")}
        </button>
      </form>

      <p className="text-center text-sm text-stone-500 font-medium mt-6">
        {t("Already have an account?")}{" "}
        <Link href="/login" className="text-petro-green font-bold hover:underline">{t("Sign In")}</Link>
      </p>
    </div>
  );
}

// ─── Step 2: Email Verification ───────────────────────────────────────────────
function Step2({ email, onBack }: { email: string; onBack: () => void }) {
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
          className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900 font-semibold transition-colors"
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
            className="text-sm text-petro-green font-bold hover:underline transition-colors disabled:opacity-50"
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

// ─── Main Register Page ───────────────────────────────────────────────────────
export default function RegisterPage() {
  const [step, setStep] = useState(1);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleNext = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    console.log("[REGISTER] 🔵 Memulai proses pendaftaran untuk email:", email);

    if (password !== confirmPassword) {
      console.log("[REGISTER] ❌ Error: Password dan konfirmasi tidak cocok.");
      setError("Password dan konfirmasi password tidak cocok.");
      return;
    }
    if (password.length < 8) {
      console.log("[REGISTER] ❌ Error: Password kurang dari 8 karakter.");
      setError("Password harus minimal 8 karakter.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error("[REGISTER] ❌ Pendaftaran gagal. Detail error backend:", data);
        throw new Error(data.detail || "Pendaftaran gagal. Silakan coba lagi.");
      }
      console.log("[REGISTER] ✅ Pendaftaran berhasil! Lanjut ke Step 2.");
      setStep(2);
    } catch (err: any) {
      console.error("[REGISTER] ❌ Terjadi exception saat registrasi:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-petro-bg-warm">
      <AuthLeftPanel />
      <div className="flex-1 flex items-center justify-center p-6">
        {step === 1 ? (
          <Step1
            fullName={fullName} setFullName={setFullName}
            email={email} setEmail={setEmail}
            password={password} setPassword={setPassword}
            confirmPassword={confirmPassword} setConfirmPassword={setConfirmPassword}
            showPassword={showPassword} setShowPassword={setShowPassword}
            showConfirm={showConfirm} setShowConfirm={setShowConfirm}
            onNext={handleNext}
            error={error}
            loading={loading}
          />
        ) : (
          <Step2 email={email} onBack={() => setStep(1)} />
        )}
      </div>
    </div>
  );
}
