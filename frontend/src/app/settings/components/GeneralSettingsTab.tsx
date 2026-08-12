import ScrollReveal from "@/components/ScrollReveal";
import { useTx } from "@/hooks/useTx";
import { useAppearance } from "@/hooks/useAppearance";
import type { Appearance } from "@/utils/theme";

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
  const { tx } = useTx();
  const { appearance, setAppearance } = useAppearance();

  const appearanceOptions: { value: Appearance; label: string; icon: React.ReactNode }[] = [
    {
      value: "light",
      label: tx("Light", "Light"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
        </svg>
      ),
    },
    {
      value: "dark",
      label: tx("Dark", "Dark"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
        </svg>
      ),
    },
    {
      value: "system",
      label: tx("System", "System"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 0 1-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0 1 15 18.257V17.25m6-12V15a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 15V5.25m18 0A2.25 2.25 0 0 0 18.75 3H5.25A2.25 2.25 0 0 0 3 5.25m18 0V12a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 12V5.25" />
        </svg>
      ),
    },
  ];

  return (
    <ScrollReveal animation="fadeInUp" delay={100}>
      <div className="space-y-6">
        {/* Appearance Card */}
        <div className="bg-white dark:bg-stone-900 border border-stone-200/80 dark:border-stone-700/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover">
          <h3 className="font-extrabold text-stone-900 dark:text-stone-100 text-sm">
            {tx("Appearance", "Appearance")}
          </h3>
          <p className="text-[10px] text-stone-450 dark:text-stone-400 mt-1 font-semibold">
            {tx(
              "Choose how the application looks to you",
              "Choose how the application looks to you",
            )}
          </p>

          <div className="flex gap-2 mt-4 max-w-xl">
            {appearanceOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setAppearance(opt.value)}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-bold border transition-colors cursor-pointer ${
                  appearance === opt.value
                    ? "bg-petro-green text-white border-petro-green shadow-sm"
                    : "bg-white dark:bg-stone-800 text-stone-600 dark:text-stone-300 border-stone-200 dark:border-stone-700 hover:bg-stone-50 dark:hover:bg-stone-750"
                }`}
              >
                {opt.icon}
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Language Card */}
        <div className="bg-white dark:bg-stone-900 border border-stone-200/80 dark:border-stone-700/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover">
          <h3 className="font-extrabold text-stone-900 dark:text-stone-100 text-sm">
            {tx("Language Preferences", "Language Preferences")}
          </h3>
          <p className="text-[10px] text-stone-450 dark:text-stone-400 mt-1 font-semibold">
            {tx(
              "Choose your preferred language for the application",
              "Choose your preferred language for the application",
            )}
          </p>

          <div className="relative mt-4 max-w-xl">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="appearance-none w-full pl-3 pr-8 py-2 border border-stone-200 dark:border-stone-700 rounded-xl text-xs font-bold text-stone-700 dark:text-stone-200 bg-white dark:bg-stone-800 focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
            >
              <option value="English">English</option>
              <option value="Indonesian">Indonesian</option>
            </select>
            <span className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-stone-500 dark:text-stone-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2.5}
                stroke="currentColor"
                className="w-3.5 h-3.5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m19.5 8.25-7.5 7.5-7.5-7.5"
                />
              </svg>
            </span>
          </div>
        </div>

        {/* Notification Preferences Card */}
        <div className="bg-white dark:bg-stone-900 border border-stone-200/80 dark:border-stone-700/80 rounded-2xl p-6 shadow-sm text-left space-y-4 premium-card-hover">
          <div>
            <h3 className="font-extrabold text-stone-900 text-sm">
              {tx("Notification Preferences", "Notification Preferences")}
            </h3>
            <p className="text-[10px] text-stone-450 mt-1 font-semibold">
              {tx(
                "Choose what notifications you want to receive",
                "Choose what notifications you want to receive",
              )}
            </p>
          </div>

          <div className="space-y-3 mt-4">
            {/* Row 1: Report Generation Completed */}
            <div className="bg-white border border-stone-200/80 rounded-xl p-4 flex justify-between items-center shadow-sm">
              <div className="flex gap-4 items-center">
                <span className="w-10 h-10 rounded-xl bg-[#e6f0ea] border border-[#004D25]/10 flex items-center justify-center text-emerald-600 shrink-0">
                  <span className="w-5 h-5 rounded-full border-2 border-emerald-600 flex items-center justify-center bg-white">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-3.5 h-3.5 text-emerald-650"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </span>
                </span>
                <div className="text-left">
                  <h4 className="font-bold text-stone-855 text-xs">
                    {tx(
                      "Report Generation Completed",
                      "Report Generation Completed",
                    )}
                  </h4>
                  <p className="text-[10px] text-stone-500 font-semibold mt-0.5">
                    {tx(
                      "Receive a notification when your report has been generated successfully",
                      "Receive a notification when your report has been generated successfully",
                    )}
                  </p>
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
                <span className="text-[11px] font-bold text-stone-700 min-w-[20px]">
                  {notifySuccess ? tx("On", "On") : tx("Off", "Off")}
                </span>
              </label>
            </div>

            {/* Row 2: Report Generation Failed */}
            <div className="bg-white border border-stone-200/80 rounded-xl p-4 flex justify-between items-center shadow-sm">
              <div className="flex gap-4 items-center">
                <span className="w-10 h-10 rounded-xl bg-red-50 border border-red-200/40 flex items-center justify-center text-red-500 shrink-0">
                  <span className="w-5 h-5 rounded-full border-2 border-red-500 flex items-center justify-center bg-white">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-3.5 h-3.5 text-red-500"
                    >
                      <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0-1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                    </svg>
                  </span>
                </span>
                <div className="text-left">
                  <h4 className="font-bold text-stone-855 text-xs">
                    {tx("Report Generation Failed", "Report Generation Failed")}
                  </h4>
                  <p className="text-[10px] text-stone-500 font-semibold mt-0.5">
                    {tx(
                      "Receive a notification when your report generation fails",
                      "Receive a notification when your report generation fails",
                    )}
                  </p>
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
                <span className="text-[11px] font-bold text-stone-700 min-w-[20px]">
                  {notifyFailed ? tx("On", "On") : tx("Off", "Off")}
                </span>
              </label>
            </div>
          </div>
        </div>
      </div>
    </ScrollReveal>
  );
}
