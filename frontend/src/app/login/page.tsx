"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, getLanguage } from "@/utils/i18n";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

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
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [unverifiedEmail, setUnverifiedEmail] = useState("");
  const [resendMessage, setResendMessage] = useState("");
  const [resendLoading, setResendLoading] = useState(false);

  const [rememberMe, setRememberMe] = useState(true);

  // Load saved credentials on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedEmail = localStorage.getItem("saved_email");
      const savedRemember = localStorage.getItem("remember_me") === "true";
      if (savedRemember && savedEmail) {
        setEmail(savedEmail);
        setRememberMe(true);
      }
    }
  }, []);

  useEffect(() => {
    // Membaca Google Client ID dari env atau menggunakan default value yang disediakan
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "126885950302-sua5h4t01g4qfaug5m7c9is04uvhce88.apps.googleusercontent.com";

    const handleCredentialResponse = async (response: any) => {
      setError("");
      setLoading(true);
      console.log("[GOOGLE AUTH] 🌐 Menerima credential token dari Google OAuth.");
      try {
        const res = await fetch("http://localhost:8000/api/v1/auth/google-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: response.credential }),
        });
        const data = await res.json();
        if (!res.ok) {
          console.error("[GOOGLE AUTH] ❌ Backend menolak Google login:", data);
          throw new Error(data.detail || "Gagal masuk menggunakan akun Google.");
        }
        console.log("[GOOGLE AUTH] ✅ Google login berhasil! Menyimpan token ke localStorage.");
        localStorage.setItem("token", data.access_token);

        // Decode Google JWT payload to extract email and autofill next time
        try {
          const base64Url = response.credential.split('.')[1];
          let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const pad = base64.length % 4;
          if (pad) {
            if (pad === 2) { base64 += '=='; }
            else if (pad === 3) { base64 += '='; }
          }
          const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
              return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
          }).join(''));
          const payload = JSON.parse(jsonPayload);
          if (payload.email) {
            console.log("[GOOGLE AUTH] 💾 Menyimpan email Google untuk autofill selanjutnya:", payload.email);
            localStorage.setItem("saved_email", payload.email);
            localStorage.setItem("remember_me", "true");
          }
        } catch (e) {
          console.warn("[GOOGLE AUTH] Gagal decode JWT email untuk autofill:", e);
        }

        router.push("/");
      } catch (err: any) {
        console.error("[GOOGLE AUTH] ❌ Exception saat Google login:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    const initializeGoogle = () => {
      if ((window as any).google) {
        (window as any).google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleCredentialResponse,
        });
        
        const buttonDiv = document.getElementById("google-signin-btn");
        if (buttonDiv) {
          (window as any).google.accounts.id.renderButton(
            buttonDiv,
            { 
              theme: "outline", 
              size: "large", 
              width: buttonDiv.clientWidth || 360,
              text: "signin_with",
              shape: "rectangular"
            }
          );
        }
      }
    };

    if (typeof window !== "undefined") {
      const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
      if (existingScript) {
        if ((window as any).google) {
          initializeGoogle();
        } else {
          existingScript.addEventListener("load", initializeGoogle);
        }
      } else {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        script.defer = true;
        script.onload = initializeGoogle;
        document.body.appendChild(script);
      }
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setUnverifiedEmail("");
    setResendMessage("");
    setLoading(true);
    console.log("[LOGIN] 🔑 Memulai proses login manual untuk:", email);
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error("[LOGIN] ❌ Login gagal. Status:", res.status, "Error:", data);
        const errMsg = data.detail || "Email atau password salah.";
        if (res.status === 403 && errMsg.includes("belum diverifikasi")) {
          console.warn("[LOGIN] ⚠️ Email belum diverifikasi. Menyimpan email untuk tombol resend.");
          setUnverifiedEmail(email);
        }
        throw new Error(errMsg);
      }
      console.log("[LOGIN] ✅ Login berhasil! Menyimpan token.");
      localStorage.setItem("token", data.access_token);

      // Simpan/hapus email berdasarkan "Remember Me"
      if (rememberMe) {
        localStorage.setItem("saved_email", email);
        localStorage.setItem("remember_me", "true");
      } else {
        localStorage.removeItem("saved_email");
        localStorage.removeItem("remember_me");
      }

      router.push("/");
    } catch (err: any) {
      console.error("[LOGIN] ❌ Exception saat login:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setResendLoading(true);
    setResendMessage("");
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: unverifiedEmail }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gagal mengirim ulang email verifikasi.");
      }
      setResendMessage(data.message || "Tautan verifikasi baru berhasil dikirim!");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-petro-bg-warm">
      {/* ── LEFT PANEL ─────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[30%] xl:w-[33%] lg:min-w-[400px] shrink-0 bg-petro-green flex-col justify-between p-10 text-white animate-slideInLeft">
        {/* Brand */}
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
          <div className="space-y-4 text-left animate-fadeInUp delay-200">
            <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight">{t("AI-Powered SOC Reporting")}</h1>
            <p className="text-sm lg:text-base text-white/80 leading-relaxed font-medium">
              {t("Automate monthly SOC report generation with AI. Fast, accurate, and reliable.")}
            </p>
          </div>

          {/* Illustration */}
          <div className="flex justify-center animate-fadeInUp delay-400">
            <img src="/soc-logo.png" alt="SOC Report Illustration" className="w-full max-w-[340px] object-contain h-auto animate-float" />
          </div>
        </div>

        {/* Small Bottom Spacer to keep balance */}
        <div className="h-2"></div>
      </div>

      {/* ── RIGHT PANEL ─────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[560px] bg-white rounded-2xl shadow-sm border border-stone-200/80 p-10 sm:p-12 animate-scaleIn">
          {/* Heading */}
          <div className="text-center mb-10 animate-fadeInUp delay-100">
            <h2 className="text-2xl font-extrabold text-stone-900">{t("Welcome Back!")}</h2>
            <p className="text-sm text-stone-500 font-semibold mt-2">{t("Sign in to continue to your dashboard")}</p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-5 bg-red-50 border border-red-200 text-red-700 text-xs font-medium px-4 py-3 rounded-xl flex flex-col gap-2">
              <span>{error}</span>
              {unverifiedEmail && (
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resendLoading}
                  className="text-left text-xs text-petro-green font-bold hover:underline disabled:opacity-50 mt-1"
                >
                  {resendLoading ? t("Sending...") : t("Resend verification email")}
                </button>
              )}
            </div>
          )}

          {/* Resend Success Message */}
          {resendMessage && (
            <div className="mb-5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold px-4 py-3 rounded-xl">
              {resendMessage}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5 animate-fadeInUp delay-150">
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
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t("Enter your email")}
                  required
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
                  autoComplete="current-password"
                  className="w-full pl-10 pr-12 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                >
                  {showPassword ? (
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
                    </svg>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                    </svg>
                  )}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 rounded border-stone-300 text-petro-green focus:ring-petro-green/20 focus:border-petro-green transition-all"
                  />
                  <span className="text-xs text-stone-600 font-semibold">{t("Remember Me")}</span>
                </label>
                <Link href="/forgot-password" className="text-xs font-semibold text-petro-green hover:underline">
                  {t("Forgot Password?")}
                </Link>
              </div>
            </div>

            {/* Sign In Button */}
            <button
              type="submit"
              disabled={loading}
              className="relative w-full py-3 bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm rounded-xl shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-60 overflow-hidden group"
            >
              {loading && (
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                </span>
              )}
              <span className={`transition-opacity duration-200 ${loading ? "opacity-0" : "opacity-100"}`}>
                {t("Sign In")}
              </span>
              <span className="absolute inset-0 rounded-xl bg-white/0 group-hover:bg-white/5 transition-colors duration-200" />
            </button>

            {/* Divider */}
            <div className="flex items-center gap-3 my-2 animate-fadeIn delay-300">
              <div className="flex-1 h-px bg-stone-200"></div>
              <span className="text-xs text-stone-400 font-medium">or</span>
              <div className="flex-1 h-px bg-stone-200"></div>
            </div>

            {/* Google Button Container */}
            <div className="flex justify-center w-full min-h-[44px]">
              <div id="google-signin-btn" className="flex justify-center w-full"></div>
            </div>
          </form>

          {/* Footer link */}
          <p className="text-center text-sm text-stone-500 font-medium mt-6">
            {t("Don't have an account?")}{" "}
            <Link href="/register" className="text-petro-green font-bold hover:underline">
              {t("Register Now")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
