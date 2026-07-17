"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { setLanguage as setUiLanguage, t } from "@/utils/i18n";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";

export default function SettingsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<"general" | "account">("general");

  // Loading & Error States
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Account Form States
  const [fullName, setFullName] = useState("");
  const [emailAddress, setEmailAddress] = useState("");
  const [avatarUrl, setAvatarUrl] = useState(""); // Menyimpan Base64 atau URL foto profil
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  // General Preferences States
  const [language, setLanguage] = useState("English");
  const [notifySuccess, setNotifySuccess] = useState(true);
  const [notifyFailed, setNotifyFailed] = useState(true);

  // Fetch initial profile & settings on mount
  const loadData = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // 1. Fetch User Profile
      const profileRes = await fetch("http://localhost:8000/api/v1/settings/profile", { headers });
      if (profileRes.status === 401 || profileRes.status === 403) {
        router.push("/login");
        return;
      }

      if (profileRes.ok) {
        const profile = await profileRes.json();
        setFullName(profile.full_name || "");
        setEmailAddress(profile.email || "");
        setAvatarUrl(profile.avatar_url || ""); // Mengambil foto profil dari backend
      }

      // 2. Fetch System/User Settings
      const settingsRes = await fetch("http://localhost:8000/api/v1/settings/", { headers });
      if (settingsRes.ok) {
        const settings = await settingsRes.json();
        const langVal = settings.ai_language === "Indonesian" ? "Indonesian" : "English";
        setLanguage(langVal);
        setUiLanguage(langVal);
        setNotifySuccess(settings.include_charts ?? true);
        setNotifyFailed(settings.include_exec_summary ?? true);
      }
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Gagal memuat preferensi pengguna.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    if (typeof window !== "undefined") {
      window.document.documentElement.classList.remove("dark");
    }
  }, []);

  // Penanganan pemilihan foto profil (Konversi ke Base64)
  const handleAvatarClick = () => {
    fileInputRef.current?.click(); // Memicu klik pada input file yang tersembunyi
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Batasi ukuran file maksimal 2MB untuk mencegah payload kebesaran
      if (file.size > 2 * 1024 * 1024) {
        setErrorMsg("Ukuran foto maksimal adalah 2MB.");
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarUrl(reader.result as string); // Menyimpan hasil konversi Base64 ke state
      };
      reader.readAsDataURL(file);
    }
  };

  // Reset to default preferences
  const handleResetToDefault = async () => {
    if (!confirm("Apakah Anda yakin ingin mengatur ulang preferensi ke default?")) {
      return;
    }
    setErrorMsg("");
    setSuccessMsg("");
    try {
      setLanguage("English");
      setNotifySuccess(true);
      setNotifyFailed(true);
      setSuccessMsg("Preferensi berhasil diatur ulang ke default.");
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (e) {
      setErrorMsg("Gagal mengatur ulang preferensi.");
    }
  };

  // Save changes handler
  const handleSaveChanges = async () => {
    setErrorMsg("");
    setSuccessMsg("");

    if (newPassword || confirmNewPassword) {
      if (newPassword.length < 8) {
        setErrorMsg("Password baru minimal terdiri dari 8 karakter.");
        return;
      }
      if (newPassword !== confirmNewPassword) {
        setErrorMsg("Konfirmasi password baru tidak cocok.");
        return;
      }
      if (!currentPassword) {
        setErrorMsg("Password saat ini harus diisi untuk memperbarui password.");
        return;
      }
    }

    setIsSaving(true);
    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {
        "Content-Type": "application/json"
      };
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      // 1. Menyatukan data Profile & Avatar Base64 ke dalam satu payload JSON
      const profileBody: Record<string, any> = {
        full_name: fullName,
        email: emailAddress,
        avatar_url: avatarUrl // Mengirimkan string Base64 langsung ke DB
      };

      if (newPassword) {
        profileBody.current_password = currentPassword;
        profileBody.new_password = newPassword;
      }

      const profileRes = await fetch("http://localhost:8000/api/v1/settings/profile", {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify(profileBody)
      });

      if (!profileRes.ok) {
        const errData = await profileRes.json();
        throw new Error(errData.detail || "Gagal memperbarui profil pengguna.");
      }

      const profileData = await profileRes.json();
      setFullName(profileData.full_name);
      setEmailAddress(profileData.email);
      setAvatarUrl(profileData.avatar_url || "");

      const settingsBody = {
        ai_language: language,
        include_charts: notifySuccess,
        include_exec_summary: notifyFailed,
        appearance: "light"
      };

      const settingsRes = await fetch("http://localhost:8000/api/v1/settings/", {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify(settingsBody)
      });

      if (!settingsRes.ok) {
        throw new Error("Gagal menyimpan preferensi sistem.");
      }

      setUiLanguage(language);

      // Reset password fields setelah sukses menyimpan
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");

      window.dispatchEvent(new Event("user_profile_updated"));

      setSuccessMsg("Pengaturan berhasil disimpan.");
      setTimeout(() => setSuccessMsg(""), 3500);

    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Terjadi kesalahan saat menyimpan pengaturan.");
    } finally {
      setIsSaving(false);
    }
  };

  const getAvatarInitial = () => {
    if (fullName && fullName.trim()) {
      return fullName.trim().charAt(0).toUpperCase();
    }
    return "U";
  };

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      <Sidebar />

      <div className="flex-1 pl-64 flex flex-col min-h-screen">
        <Navbar />

        <main className="flex-1 p-8 max-w-4xl mx-auto w-full space-y-6">
          {/* Header Title section */}
          <div className="flex justify-between items-center text-left animate-fadeInUp">
            <div>
              <h2 className="text-2xl font-extrabold text-stone-900">{t("Settings")}</h2>
              <p className="text-sm text-stone-500 font-medium mt-1">
                {t("Manage your settings and preferences.")}
              </p>
            </div>

            <button
              onClick={handleResetToDefault}
              className="inline-flex items-center gap-2 px-4 py-2 border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 font-bold text-xs rounded-xl shadow-sm hover:shadow transition-all duration-200 group cursor-pointer"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 transition-transform duration-500 group-hover:-rotate-180">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              {t("Reset to Default")}
            </button>
          </div>

          {/* Error and Success alerts */}
          {errorMsg && (
            <div className="bg-red-50 border border-red-200 text-red-750 px-4 py-3 rounded-xl text-xs font-medium text-left animate-fadeIn">
              <strong>Error:</strong> {t(errorMsg)}
            </div>
          )}
          {successMsg && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-xl text-xs font-bold text-left animate-slideDown flex items-center gap-2">
              <span className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="white" className="w-2.5 h-2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                </svg>
              </span>
              {t(successMsg)}
            </div>
          )}

          {/* Navigation Tabs (Account vs General) */}
          <div className="bg-white border border-stone-200/80 rounded-2xl py-3.5 px-6 flex justify-center gap-16 shadow-sm animate-fadeInUp delay-100 relative overflow-hidden">
            <button
              onClick={() => {
                setActiveTab("general");
                setErrorMsg("");
                setSuccessMsg("");
              }}
              className={`pb-1.5 font-extrabold text-xs transition-all duration-200 relative ${activeTab === "general"
                  ? "text-stone-900 font-black"
                  : "text-stone-400 hover:text-stone-700"
                }`}
            >
              {t("General")}
              <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-petro-yellow rounded-full transition-all duration-300 ${activeTab === "general" ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0"}`} />
            </button>
            <button
              onClick={() => {
                setActiveTab("account");
                setErrorMsg("");
                setSuccessMsg("");
              }}
              className={`pb-1.5 font-extrabold text-xs transition-all duration-200 relative ${activeTab === "account"
                  ? "text-stone-900 font-black"
                  : "text-stone-400 hover:text-stone-700"
                }`}
            >
              {t("Account")}
              <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-petro-yellow rounded-full transition-all duration-300 ${activeTab === "account" ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0"}`} />
            </button>
          </div>

          {/* TAB CONTENTS */}
          {loading ? (
            <div className="space-y-4 animate-fadeIn">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4">
                  <div className="skeleton h-4 w-32 rounded" />
                  <div className="skeleton h-3 w-64 rounded" />
                  <div className="skeleton h-9 w-full max-w-xs rounded-xl" />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-6">

              {/* GENERAL TAB CONTENT */}
              {activeTab === "general" && (
                <ScrollReveal animation="fadeInUp" delay={100}>
                  <div className="space-y-6">
                    {/* Language Card */}
                    <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover">
                      <h3 className="font-extrabold text-stone-900 text-sm">{t("Language Preferences")}</h3>
                      <p className="text-[10px] text-stone-450 mt-1 font-semibold">{t("Choose your preferred language for the application")}</p>

                      <div className="relative mt-4 max-w-xl">
                        <select
                          value={language}
                          onChange={(e) => setLanguage(e.target.value)}
                          className="appearance-none w-full pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                        >
                          <option value="English">English</option>
                          <option value="Indonesian">Indonesian</option>
                        </select>
                        <span className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-stone-500">
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                          </svg>
                        </span>
                      </div>
                    </div>

                    {/* Notification Preferences Card */}
                    <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left space-y-4 premium-card-hover">
                      <div>
                        <h3 className="font-extrabold text-stone-900 text-sm">{t("Notification Preferences")}</h3>
                        <p className="text-[10px] text-stone-450 mt-1 font-semibold">{t("Choose what notifications you want to receive")}</p>
                      </div>

                      <div className="space-y-3 mt-4">
                        {/* Row 1: Report Generation Completed */}
                        <div className="bg-white border border-stone-200/80 rounded-xl p-4 flex justify-between items-center shadow-sm">
                          <div className="flex gap-4 items-center">
                            <span className="w-10 h-10 rounded-xl bg-[#e6f0ea] border border-[#004D25]/10 flex items-center justify-center text-emerald-600 shrink-0">
                              <span className="w-5 h-5 rounded-full border-2 border-emerald-600 flex items-center justify-center bg-white">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-650">
                                  <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                                </svg>
                              </span>
                            </span>
                            <div className="text-left">
                              <h4 className="font-bold text-stone-850 text-xs">{t("Report Generation Completed")}</h4>
                              <p className="text-[10px] text-stone-500 font-semibold mt-0.5">{t("Receive a notification when your report has been generated successfully")}</p>
                            </div>
                          </div>
                          {/* Toggle switch success */}
                          <label className="flex items-center cursor-pointer gap-2.5 select-none">
                            <div className="toggle-switch">
                              <input
                                type="checkbox"
                                checked={notifySuccess}
                                onChange={() => setNotifySuccess(!notifySuccess)}
                              />
                              <div className="toggle-track" />
                            </div>
                            <span className="text-[11px] font-bold text-stone-700 min-w-[20px]">{notifySuccess ? t("On") : t("Off")}</span>
                          </label>
                        </div>

                        {/* Row 2: Report Generation Failed */}
                        <div className="bg-white border border-stone-200/80 rounded-xl p-4 flex justify-between items-center shadow-sm">
                          <div className="flex gap-4 items-center">
                            <span className="w-10 h-10 rounded-xl bg-red-50 border border-red-200/40 flex items-center justify-center text-red-500 shrink-0">
                              <span className="w-5 h-5 rounded-full border-2 border-red-500 flex items-center justify-center bg-white">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-red-500">
                                  <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0-1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                                </svg>
                              </span>
                            </span>
                            <div className="text-left">
                              <h4 className="font-bold text-stone-850 text-xs">{t("Report Generation Failed")}</h4>
                              <p className="text-[10px] text-stone-500 font-semibold mt-0.5">{t("Receive a notification when your report generation fails")}</p>
                            </div>
                          </div>
                          {/* Toggle switch failure */}
                          <label className="flex items-center cursor-pointer gap-2.5 select-none">
                            <div className="toggle-switch">
                              <input
                                type="checkbox"
                                checked={notifyFailed}
                                onChange={() => setNotifyFailed(!notifyFailed)}
                              />
                              <div className="toggle-track" />
                            </div>
                            <span className="text-[11px] font-bold text-stone-700 min-w-[20px]">{notifyFailed ? t("On") : t("Off")}</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                </ScrollReveal>
              )}

              {/* ACCOUNT TAB CONTENT */}
              {activeTab === "account" && (
                <ScrollReveal animation="fadeInUp" delay={100}>
                  <div className="bg-white border border-stone-200/80 rounded-2xl p-8 shadow-sm text-left premium-card-hover">
                    <h3 className="font-extrabold text-stone-900 text-sm">{t("Profile Information")}</h3>
                    <p className="text-[10px] text-stone-450 mt-1 font-semibold">{t("Manage your personal information")}</p>

                    <div className="grid grid-cols-1 md:grid-cols-12 gap-8 mt-8 items-start">

                      {/* Left Column Profile photo */}
                      <div className="md:col-span-4 flex flex-col items-center py-4">
                        <span className="text-xs font-bold text-stone-500 mb-3">{t("Profile Picture")}</span>

                        {/* Input file tersembunyi */}
                        <input
                          type="file"
                          ref={fileInputRef}
                          onChange={handleAvatarChange}
                          accept="image/*"
                          className="hidden"
                        />

                        {/* Penayangan Foto Dinamis (Fallback ke Inisial jika kosong) */}
                        {avatarUrl ? (
                          <img
                            src={avatarUrl}
                            alt="Avatar"
                            className="w-28 h-28 rounded-full object-cover border border-stone-200 shadow-sm mb-4 select-none"
                          />
                        ) : (
                          <div className="w-28 h-28 rounded-full bg-stone-100 border border-stone-200 flex items-center justify-center text-petro-green font-black text-4xl mb-4 shadow-sm select-none">
                            {getAvatarInitial()}
                          </div>
                        )}

                        <button
                          onClick={handleAvatarClick}
                          className="px-4 py-2 border border-petro-green text-petro-green hover:bg-petro-green/5 font-extrabold text-[10px] uppercase tracking-wide rounded-xl shadow-sm transition-colors cursor-pointer"
                        >
                          {t("Change Photo")}
                        </button>
                      </div>

                      {/* Right Column Form Inputs */}
                      <div className="md:col-span-8 space-y-4">
                        {/* Full Name */}
                        <div className="flex flex-col gap-1">
                          <label className="text-xs font-bold text-stone-700 mb-1.5">{t("Full Name")}</label>
                          <input
                            type="text"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder={t("Enter your full name")}
                            className="w-full px-3 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-855 placeholder-stone-400 bg-white"
                          />
                        </div>

                        {/* Email Address */}
                        <div className="flex flex-col gap-1">
                          <label className="text-xs font-bold text-stone-700 mb-1.5">{t("Email Address")}</label>
                          <input
                            type="email"
                            value={emailAddress}
                            onChange={(e) => setEmailAddress(e.target.value)}
                            placeholder={t("Enter your email address")}
                            className="w-full px-3 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-855 placeholder-stone-400 bg-white"
                          />
                        </div>

                        <hr className="border-stone-100 my-2" />

                        {/* Current Password */}
                        <div className="flex flex-col gap-1 relative">
                          <label className="text-xs font-bold text-stone-700 mb-1.5">{t("Current Password")}</label>
                          <input
                            type={showCurrentPw ? "text" : "password"}
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            placeholder="••••••••••••"
                            className="w-full pl-3 pr-10 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-855 placeholder-stone-400 bg-white"
                          />
                          <button
                            type="button"
                            onClick={() => setShowCurrentPw(!showCurrentPw)}
                            className="absolute right-3.5 bottom-2 text-stone-400 hover:text-stone-600 transition-colors cursor-pointer"
                          >
                            {showCurrentPw ? (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                              </svg>
                            ) : (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                            )}
                          </button>
                        </div>

                        {/* New Password */}
                        <div className="flex flex-col gap-1 relative">
                          <label className="text-xs font-bold text-stone-700 mb-1.5">{t("New Password")}</label>
                          <input
                            type={showNewPw ? "text" : "password"}
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            placeholder="••••••••••••"
                            className="w-full pl-3 pr-10 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-855 placeholder-stone-400 bg-white"
                          />
                          <button
                            type="button"
                            onClick={() => setShowNewPw(!showNewPw)}
                            className="absolute right-3.5 bottom-2 text-stone-400 hover:text-stone-600 transition-colors cursor-pointer"
                          >
                            {showNewPw ? (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                              </svg>
                            ) : (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                            )}
                          </button>
                        </div>

                        {/* Confirm New Password */}
                        <div className="flex flex-col gap-1 relative">
                          <label className="text-xs font-bold text-stone-700 mb-1.5">{t("Confirm New Password")}</label>
                          <input
                            type={showConfirmPw ? "text" : "password"}
                            value={confirmNewPassword}
                            onChange={(e) => setConfirmNewPassword(e.target.value)}
                            placeholder="••••••••••••"
                            className="w-full pl-3 pr-10 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-855 placeholder-stone-400 bg-white"
                          />
                          <button
                            type="button"
                            onClick={() => setShowConfirmPw(!showConfirmPw)}
                            className="absolute right-3.5 bottom-2 text-stone-400 hover:text-stone-600 transition-colors cursor-pointer"
                          >
                            {showConfirmPw ? (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                              </svg>
                            ) : (
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                            )}
                          </button>
                        </div>
                        <span className="text-[10px] text-stone-450 font-semibold mt-1">{t("Minimum 8 characters with letters, numbers, and symbols")}</span>
                      </div>
                    </div>
                  </div>
                </ScrollReveal>
              )}

              {/* SAVE CHANGE BUTTON BAR */}
              <div className="pt-5 border-t border-stone-200/60 mt-6 flex justify-end">
                <button
                  onClick={handleSaveChanges}
                  disabled={isSaving}
                  className="px-6 py-3 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs shadow-md transition-all disabled:opacity-60 flex items-center gap-2 cursor-pointer"
                >
                  {isSaving ? (
                    <>
                      <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t("Saving...")}
                    </>
                  ) : (
                    t("Save Change")
                  )}
                </button>
              </div>

            </div>
          )}
        </main>
      </div>
    </div>
  );
}