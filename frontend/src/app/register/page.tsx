"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AuthLeftPanel from "./components/AuthLeftPanel";
import Step1AccountDetails from "./components/Step1AccountDetails";
import Step2EmailVerification from "./components/Step2EmailVerification";

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleGoogleSuccess = async (googleToken: string) => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        "http://localhost:8000/api/v1/auth/google-login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: googleToken }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gagal mendaftar menggunakan akun Google.");
      }
      localStorage.setItem("token", data.access_token);
      router.push("/generate");
    } catch (err: any) {
      console.error("[GOOGLE AUTH] Exception saat Google register:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = (msg: string) => {
    setError(msg);
  };

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
          <Step1AccountDetails
            fullName={fullName}
            setFullName={setFullName}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            confirmPassword={confirmPassword}
            setConfirmPassword={setConfirmPassword}
            showPassword={showPassword}
            setShowPassword={setShowPassword}
            showConfirm={showConfirm}
            setShowConfirm={setShowConfirm}
            onNext={handleNext}
            error={error}
            loading={loading}
            onGoogleSuccess={handleGoogleSuccess}
            onGoogleError={handleGoogleError}
          />
        ) : (
          <Step2EmailVerification email={email} onBack={() => setStep(1)} />
        )}
      </div>
    </div>
  );
}
