import ScrollReveal from "@/components/ScrollReveal";
import { t } from "@/utils/i18n";

interface GeneralSettingsTabProps {
  language: string;
  setLanguage: (val: string) => void;
  notifySuccess: boolean;
  setNotifySuccess: (val: boolean) => void;
  notifyFailed: boolean;
  setNotifyFailed: (val: boolean) => void;
}

export default function GeneralSettingsTab({
  language,
  setLanguage,
  notifySuccess,
  setNotifySuccess,
  notifyFailed,
  setNotifyFailed,
}: GeneralSettingsTabProps) {
  return (
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
                  <h4 className="font-bold text-stone-855 text-xs">{t("Report Generation Completed")}</h4>
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
                  <h4 className="font-bold text-stone-855 text-xs">{t("Report Generation Failed")}</h4>
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
  );
}
