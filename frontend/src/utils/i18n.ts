import en from "../locales/en.json";
import id from "../locales/id.json";

const translations: Record<string, Record<string, string>> = {
  English: en,
  Indonesian: id,
};

export function getLanguage(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("ui_language") || "English";
  }
  return "English";
}

export function setLanguage(lang: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("ui_language", lang);
    // Dispatch a custom event to notify listeners (e.g. sidebar, pages) to re-render
    window.dispatchEvent(new Event("ui_language_changed"));
  }
}

export function t(key: string): string {
  const lang = getLanguage();
  return translations[lang]?.[key] ?? key;
}
