"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { setLanguage as setUiLanguage, t } from "@/utils/i18n";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import GeneralSettingsTab from "./components/GeneralSettingsTab";
import AccountSettingsTab from "./components/AccountSettingsTab";

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
  const [passwordSet, setPasswordSet] = useState(true); // false = akun Google yang belum pernah nge-set password sendiri
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

      // 1. Fetch User Profile (termasuk preferensi personal: language, appearance, notifikasi)
      const profileRes = await fetch(
        "http://localhost:8000/api/v1/settings/profile",
        { headers },
      );
      if (profileRes.status === 401 || profileRes.status === 403) {
        router.push("/login");
        return;
      }

      if (profileRes.ok) {
        const profile = await profileRes.json();
        setFullName(profile.full_name || "");
        setEmailAddress(profile.email || "");
        setAvatarUrl(profile.avatar_url || ""); // Mengambil foto profil dari backend
        setPasswordSet(profile.password_set ?? true);

        // Preferensi personal ini sekarang disimpan per-user (bukan lagi di pengaturan global),
        // jadi tiap user yang login akan lihat preferensinya sendiri-sendiri.
        const langVal =
          profile.language === "Indonesian" ? "Indonesian" : "English";
        setLanguage(langVal);
        setUiLanguage(langVal);
        setNotifySuccess(profile.notify_report_success ?? true);
        setNotifyFailed(profile.notify_report_failed ?? true);
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
    if (
      !confirm("Apakah Anda yakin ingin mengatur ulang preferensi ke default?")
    ) {
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
      if (passwordSet && !currentPassword) {
        setErrorMsg(
          "Password saat ini harus diisi untuk memperbarui password.",
        );
        return;
      }
    }

    setIsSaving(true);
    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      // 1. Menyatukan data Profile, Avatar, dan preferensi personal ke dalam satu payload JSON.
      // Semua field ini per-user — tidak lagi menyentuh pengaturan global sama sekali.
      const profileBody: Record<string, any> = {
        full_name: fullName,
        email: emailAddress,
        avatar_url: avatarUrl, // Mengirimkan string Base64 langsung ke DB
        language: language,
        appearance: "light",
        notify_report_success: notifySuccess,
        notify_report_failed: notifyFailed,
      };

      if (newPassword) {
        profileBody.current_password = currentPassword;
        profileBody.new_password = newPassword;
      }

      const profileRes = await fetch(
        "http://localhost:8000/api/v1/settings/profile",
        {
          method: "PUT",
          headers: authHeaders,
          body: JSON.stringify(profileBody),
        },
      );

      if (!profileRes.ok) {
        const errData = await profileRes.json();
        throw new Error(errData.detail || "Gagal memperbarui profil pengguna.");
      }

      const profileData = await profileRes.json();
      setFullName(profileData.full_name);
      setEmailAddress(profileData.email);
      setAvatarUrl(profileData.avatar_url || "");
      setPasswordSet(profileData.password_set ?? true);

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
      setErrorMsg(
        err.message || "Terjadi kesalahan saat menyimpan pengaturan.",
      );
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
              <h2 className="text-2xl font-extrabold text-stone-900">
                {t("Settings")}
              </h2>
              <p className="text-sm text-stone-500 font-medium mt-1">
                {t("Manage your settings and preferences.")}
              </p>
            </div>

            <button
              onClick={handleResetToDefault}
              className="inline-flex items-center gap-2 px-4 py-2 border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 font-bold text-xs rounded-xl shadow-sm hover:shadow transition-all duration-200 group cursor-pointer"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                className="w-3.5 h-3.5 transition-transform duration-500 group-hover:-rotate-180"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
                />
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
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2.5}
                  stroke="white"
                  className="w-2.5 h-2.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m4.5 12.75 6 6 9-13.5"
                  />
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
              className={`pb-1.5 font-extrabold text-xs transition-all duration-200 relative ${
                activeTab === "general"
                  ? "text-stone-900 font-black"
                  : "text-stone-400 hover:text-stone-700"
              }`}
            >
              {t("General")}
              <span
                className={`absolute bottom-0 left-0 right-0 h-0.5 bg-petro-yellow rounded-full transition-all duration-300 ${activeTab === "general" ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0"}`}
              />
            </button>
            <button
              onClick={() => {
                setActiveTab("account");
                setErrorMsg("");
                setSuccessMsg("");
              }}
              className={`pb-1.5 font-extrabold text-xs transition-all duration-200 relative ${
                activeTab === "account"
                  ? "text-stone-900 font-black"
                  : "text-stone-400 hover:text-stone-700"
              }`}
            >
              {t("Account")}
              <span
                className={`absolute bottom-0 left-0 right-0 h-0.5 bg-petro-yellow rounded-full transition-all duration-300 ${activeTab === "account" ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0"}`}
              />
            </button>
          </div>

          {/* TAB CONTENTS */}
          {loading ? (
            <div className="space-y-4 animate-fadeIn">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4"
                >
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
                <GeneralSettingsTab
                  language={language}
                  setLanguage={setLanguage}
                  notifySuccess={notifySuccess}
                  setNotifySuccess={setNotifySuccess}
                  notifyFailed={notifyFailed}
                  setNotifyFailed={setNotifyFailed}
                />
              )}

              {/* ACCOUNT TAB CONTENT */}
              {activeTab === "account" && (
                <AccountSettingsTab
                  fullName={fullName}
                  setFullName={setFullName}
                  emailAddress={emailAddress}
                  setEmailAddress={setEmailAddress}
                  avatarUrl={avatarUrl}
                  handleAvatarChange={handleAvatarChange}
                  handleAvatarClick={handleAvatarClick}
                  fileInputRef={fileInputRef}
                  passwordSet={passwordSet}
                  currentPassword={currentPassword}
                  setCurrentPassword={setCurrentPassword}
                  newPassword={newPassword}
                  setNewPassword={setNewPassword}
                  confirmNewPassword={confirmNewPassword}
                  setConfirmNewPassword={setConfirmNewPassword}
                  showCurrentPw={showCurrentPw}
                  setShowCurrentPw={setShowCurrentPw}
                  showNewPw={showNewPw}
                  setShowNewPw={setShowNewPw}
                  showConfirmPw={showConfirmPw}
                  setShowConfirmPw={setShowConfirmPw}
                  getAvatarInitial={getAvatarInitial}
                />
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
                      <svg
                        className="animate-spin h-3.5 w-3.5 text-white"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        ></circle>
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        ></path>
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
