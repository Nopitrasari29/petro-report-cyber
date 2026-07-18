import ScrollReveal from "@/components/ScrollReveal";
import Link from "next/link";


interface LandingModulesListProps {
  tx: (key: string, fallback: string) => string;
}

export default function LandingModulesList({ tx }: LandingModulesListProps) {
  const modules = [
    {
      title: tx("Generate Report", "Generate Report"),
      desc: tx("Create monthly SOC reports automatically with AI", "Create monthly SOC reports automatically with AI"),
      href: "/generate",
      color: "text-petro-green",
      bg: "bg-petro-green-light",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-300 group-hover:rotate-6 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      ),
    },
    {
      title: tx("Report History", "Report History"),
      desc: tx("View, search, download, and manage previously generated reports", "View, search, download, and manage previously generated reports"),
      href: "/history",
      color: "text-amber-600",
      bg: "bg-amber-50",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
        </svg>
      ),
    },
    {
      title: tx("Settings", "Settings"),
      desc: tx("Manage account preferences and profile settings", "Manage account preferences and profile settings"),
      href: "/settings",
      color: "text-violet-650",
      bg: "bg-violet-50/70",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-7 h-7 transition-transform duration-500 group-hover:rotate-90">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 2.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
        </svg>
      ),
    },
  ];

  return (
    <section className="relative py-20 px-6 bg-white/70 overflow-hidden text-stone-900">
      {/* Subtle gold diagonal pinstripe pattern background */}
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(217,167,0,0.02)_25%,transparent_25%,transparent_50%,rgba(217,167,0,0.02)_50%,rgba(217,167,0,0.02)_75%,transparent_75%,transparent)] bg-[size:40px_40px] pointer-events-none" />

      <ScrollReveal animation="fadeInUp" className="relative z-10 max-w-4xl mx-auto">
        <div className="text-center mb-14">
          <span className="text-[10px] font-extrabold tracking-widest text-petro-yellow uppercase bg-petro-yellow-light border border-petro-yellow/20 px-3 py-1 rounded-full">{tx("Launch Centre", "Launch Centre")}</span>
          <h2 className="text-3xl font-extrabold text-stone-900 mt-3.5">{tx("Available Modules", "Available Modules")}</h2>
          <p className="text-xs text-stone-455 font-bold mt-1.5 max-w-sm mx-auto">{tx("Direct shortcuts to generate reports, view logs, or adjust settings.", "Direct shortcuts to generate reports, view logs, or adjust settings.")}</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {modules.map((mod) => (
            <Link
              key={mod.title}
              href={mod.href}
              className="group bg-white rounded-2xl border border-stone-200/80 p-8 flex flex-col items-center text-center shadow-sm hover:shadow-md transition-all duration-300 premium-card-hover cursor-pointer"
            >
              <div className={`w-14 h-14 rounded-2xl ${mod.bg} flex items-center justify-center ${mod.color} mb-6 transition-transform duration-350`}>
                {mod.icon}
              </div>
              <h3 className="font-extrabold text-stone-855 text-sm tracking-tight">{mod.title}</h3>
              <p className="text-[10px] text-stone-455 font-semibold mt-2.5 leading-relaxed max-w-[180px]">{mod.desc}</p>
            </Link>
          ))}
        </div>
      </ScrollReveal>
    </section>
  );
}
