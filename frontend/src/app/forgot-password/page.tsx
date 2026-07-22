"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { t, getLanguage } from "@/utils/i18n";

function AuthLeftPanel() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

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
          <span className="font-extrabold text-base">
            {tx("AI Security Reports", "AI Security Reports")}
          </span>
          <span className="text-[10px] text-white/70 font-semibold uppercase tracking-wider mt-0.5">
            {tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}
          </span>
        </div>
      </Link>

      <div className="flex-1 flex flex-col justify-center gap-12 my-auto">
        <div className="space-y-4 text-left">
          <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight">
            {tx("AI-Powered SOC Reporting", "AI-Powered SOC Reporting")}
          </h1>
          <p className="text-sm lg:text-base text-white/80 leading-relaxed font-medium">
            {tx(
              "Automate monthly SOC report generation with AI. Fast, accurate, and reliable.",
              "Automate monthly SOC report generation with AI. Fast, accurate, and reliable.",
            )}
          </p>
        </div>

        <div className="flex justify-center">
          <img
            src="/soc-logo.png"
            alt="SOC Report Illustration"
            className="w-full max-w-[340px] object-contain h-auto transition-transform hover:scale-[1.02] duration-300"
          />
        </div>
      </div>

      <div className="h-2"></div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        "http://localhost:8000/api/v1/auth/forgot-password",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          data.detail || "Gagal mengirim permintaan reset kata sandi.",
        );
      }
      setSuccess(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-petro-bg-warm">
      <AuthLeftPanel />
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[560px] bg-white rounded-2xl shadow-sm border border-stone-200/80 p-10 sm:p-12">
          {success ? (
            <div className="space-y-6 text-center py-6">
              <div className="flex justify-center">
                <div className="w-16 h-16 rounded-full bg-emerald-50 border-2 border-emerald-100 flex items-center justify-center shadow-sm">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.8}
                    stroke="currentColor"
                    className="w-8 h-8 text-emerald-600"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"
                    />
                  </svg>
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-extrabold text-stone-900">
                  {tx("Email Sent!", "Email Sent!")}
                </h3>
                <p className="text-sm font-semibold text-stone-700">
                  {tx(
                    "Password reset instructions have been sent to",
                    "Password reset instructions have been sent to",
                  )}{" "}
                  <span className="text-petro-green font-bold">({email})</span>.
                </p>
                <p className="text-sm text-stone-500 font-semibold">
                  {tx(
                    "Please check your inbox or spam folder to update your password.",
                    "Please check your inbox or spam folder to update your password.",
                  )}
                </p>
              </div>
              <div className="pt-4 border-t border-stone-100 mt-6">
                <Link
                  href="/login"
                  className="text-sm text-petro-green font-bold hover:underline"
                >
                  {tx("Back to Login", "Back to Login")}
                </Link>
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-6">
                <Link
                  href="/login"
                  className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900 font-semibold transition-colors"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-4 h-4"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
                    />
                  </svg>
                  {tx("Back", "Back")}
                </Link>
              </div>

              <div className="text-center mb-8">
                <h2 className="text-2xl font-extrabold text-stone-900">
                  {tx("Forgot Password?", "Forgot Password?")}
                </h2>
                <p className="text-sm text-stone-500 font-semibold mt-2">
                  {tx(
                    "Reset instructions will be sent to your email address.",
                    "Reset instructions will be sent to your email address.",
                  )}
                </p>
              </div>

              {error && (
                <div className="mb-5 bg-red-50 border border-red-200 text-red-700 text-xs font-medium px-4 py-3 rounded-xl">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-1.5">
                  <label className="block text-sm font-semibold text-stone-700">
                    {tx("Email Address", "Email Address")}
                  </label>
                  <div className="relative">
                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.8}
                        stroke="currentColor"
                        className="w-4 h-4"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"
                        />
                      </svg>
                    </span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={tx(
                        "Enter your registered email",
                        "Enter your registered email",
                      )}
                      required
                      className="w-full pl-10 pr-4 py-3 border border-stone-200 rounded-xl bg-stone-50 text-sm text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm rounded-xl shadow transition-all duration-200 disabled:opacity-60"
                >
                  {loading
                    ? tx("Sending link...", "Sending link...")
                    : tx("Send Reset Link", "Send Reset Link")}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
