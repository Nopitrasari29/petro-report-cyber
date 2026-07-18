import Link from "next/link";
import { useState, useEffect } from "react";
import { t, getLanguage } from "@/utils/i18n";

export default function AuthLeftPanel() {
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
