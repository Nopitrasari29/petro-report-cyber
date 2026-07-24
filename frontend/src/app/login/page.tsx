"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, getLanguage } from "@/utils/i18n";
import AuthLeftPanel from "../register/components/AuthLeftPanel";
import LoginForm from "./components/LoginForm";
import GoogleSignInButton from "./components/GoogleSignInButton";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);

  // REVISI: Memisahkan loading form manual dan loading Google OAuth
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const [error, setError] = useState("");
  const [unverifiedEmail, setUnverifiedEmail] = useState("");
  const [resendMessage, setResendMessage] = useState("");
  const [resendLoading, setResendLoading] = useState(false);
  const [lang, setLang] = useState("English");

  // Pengaman Hidrasi (Hydration Guard)
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

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

  // Memuat kredensial tersimpan saat pertama kali dimuat
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

  const handleGoogleSuccess = async (googleToken: string) => {
    setError("");
    setGoogleLoading(true);
    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/v1/auth/google-login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: googleToken }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Gagal masuk menggunakan akun Google.");
        setGoogleLoading(false);
        return;
      }
      localStorage.setItem("token", data.access_token);

      // Decode Google JWT email untuk autofill
      try {
        const base64Url = googleToken.split(".")[1];
        let base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
        const pad = base64.length % 4;
        if (pad) {
          if (pad === 2) {
            base64 += "==";
          } else if (pad === 3) {
            base64 += "=";
          }
        }
        const jsonPayload = decodeURIComponent(
          window
            .atob(base64)
            .split("")
            .map(function (c) {
              return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
            })
            .join(""),
        );
        const payload = JSON.parse(jsonPayload);
        if (payload.email) {
          localStorage.setItem("saved_email", payload.email);
          localStorage.setItem("remember_me", "true");
        }
      } catch (e) {
        console.warn("[GOOGLE AUTH] Gagal decode JWT email untuk autofill:", e);
      }

      router.push("/generate");
    } catch (err: any) {
      console.error("[GOOGLE AUTH] Exception saat Google login:", err);
      setError(err.message || "Gagal melakukan login dengan Google.");
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setUnverifiedEmail("");
    setResendMessage("");
    setIsSubmitting(true);

    try {
      // Menggunakan IP 127.0.0.1 secara konsisten
      const res = await fetch("http://127.0.0.1:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        const errMsg = data.detail || "Email atau password salah.";
        if (res.status === 403 && errMsg.includes("belum diverifikasi")) {
          setUnverifiedEmail(email);
        }
        setError(errMsg);
        setIsSubmitting(false);
        return;
      }

      // Simpan token akses JWT
      localStorage.setItem("token", data.access_token);

      // Simpan/hapus email berdasarkan "Remember Me"
      if (rememberMe) {
        localStorage.setItem("saved_email", email);
        localStorage.setItem("remember_me", "true");
      } else {
        localStorage.removeItem("saved_email");
        localStorage.removeItem("remember_me");
      }

      window.location.href = "/generate";
    } catch (err: any) {
      console.error("[LOGIN] Exception saat login:", err);
      setError(err.message || "Gagal terhubung ke server.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendVerification = async () => {
    setResendLoading(true);
    setResendMessage("");
    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/v1/auth/resend-verification",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: unverifiedEmail }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          data.detail || "Gagal mengirim ulang email verifikasi.",
        );
      }
      setResendMessage(
        data.message || "Tautan verifikasi baru berhasil dikirim!",
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-petro-bg-warm">
      {/* ── LEFT PANEL ── */}
      <AuthLeftPanel />

      {/* ── RIGHT PANEL ── */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[560px] bg-white rounded-2xl shadow-sm border border-stone-200/80 p-10 sm:p-12 animate-scaleIn">
          {/* Heading */}
          <div className="text-center mb-10 animate-fadeInUp delay-100">
            <h2 className="text-2xl font-extrabold text-stone-900">
              {tx("Welcome Back!", "Welcome Back!")}
            </h2>
            <p className="text-sm text-stone-500 font-semibold mt-2">
              {tx(
                "Sign in to continue to your dashboard",
                "Sign in to continue to your dashboard",
              )}
            </p>
          </div>

          {/* Form Manual */}
          <LoginForm
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            rememberMe={rememberMe}
            setRememberMe={setRememberMe}
            loading={isSubmitting} // Hanya menggunakan status loading form manual
            error={error}
            unverifiedEmail={unverifiedEmail}
            resendMessage={resendMessage}
            resendLoading={resendLoading}
            handleResendVerification={handleResendVerification}
            handleSubmit={handleSubmit}
            tx={tx}
          />

          {/* Pembatas */}
          <div className="flex items-center gap-3 my-5 animate-fadeIn delay-300">
            <div className="flex-1 h-px bg-stone-200"></div>
            <span className="text-xs text-stone-400 font-medium">or</span>
            <div className="flex-1 h-px bg-stone-200"></div>
          </div>

          {/* Tombol Google */}
          <GoogleSignInButton
            onSuccess={handleGoogleSuccess}
            onError={(msg) => setError(msg)}
            loading={googleLoading}
          />

          {/* Tautan Pendaftaran */}
          <p className="text-center text-sm text-stone-500 font-medium mt-6">
            {tx("Don't have an account?", "Don't have an account?")}{" "}
            <Link
              href="/register"
              className="text-petro-green font-bold hover:underline"
            >
              {tx("Register Now", "Register Now")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}