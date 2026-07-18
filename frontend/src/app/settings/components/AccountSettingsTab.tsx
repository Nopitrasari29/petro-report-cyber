import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import { t } from "@/utils/i18n";

interface AccountSettingsTabProps {
  fullName: string;
  setFullName: (val: string) => void;
  emailAddress: string;
  setEmailAddress: (val: string) => void;
  avatarUrl: string;
  handleAvatarChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleAvatarClick: () => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  currentPassword: string;
  setCurrentPassword: (val: string) => void;
  newPassword: string;
  setNewPassword: (val: string) => void;
  confirmNewPassword: string;
  setConfirmNewPassword: (val: string) => void;
  showCurrentPw: boolean;
  setShowCurrentPw: (val: boolean) => void;
  showNewPw: boolean;
  setShowNewPw: (val: boolean) => void;
  showConfirmPw: boolean;
  setShowConfirmPw: (val: boolean) => void;
  getAvatarInitial: () => string;
}

export default function AccountSettingsTab({
  fullName,
  setFullName,
  emailAddress,
  setEmailAddress,
  avatarUrl,
  handleAvatarChange,
  handleAvatarClick,
  fileInputRef,
  currentPassword,
  setCurrentPassword,
  newPassword,
  setNewPassword,
  confirmNewPassword,
  setConfirmNewPassword,
  showCurrentPw,
  setShowCurrentPw,
  showNewPw,
  setShowNewPw,
  showConfirmPw,
  setShowConfirmPw,
  getAvatarInitial,
}: AccountSettingsTabProps) {
  return (
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
  );
}
