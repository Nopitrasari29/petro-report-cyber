import Link from "next/link";

interface LandingHeroProps {
  tx: (key: string, fallback: string) => string;
}

export default function LandingHero({ tx }: LandingHeroProps) {
  return (
    <section className="flex-1 flex flex-col items-center justify-center text-center px-6 py-20 md:py-28 relative bg-gradient-to-b from-stone-50/40 to-transparent border-b border-stone-200/40">
      {/* Subtle grid pattern background */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,77,37,0.02)_1.5px,transparent_1.5px),linear-gradient(90deg,rgba(0,77,37,0.02)_1.5px,transparent_1.5px)] bg-[size:32px_32px] pointer-events-none opacity-60" />

      <div className="relative z-10 max-w-4xl flex flex-col items-center space-y-6">
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-black text-stone-900 leading-[1.1] tracking-tight max-w-3xl animate-fadeInUp delay-100">
          {tx("Automate Your", "Automate Your")} <br />
          <span className="text-petro-green">{tx("SOC Security Reports", "SOC Security Reports")}</span>
        </h1>

        <p className="max-w-xl text-sm md:text-base text-stone-500 font-medium leading-relaxed animate-fadeInUp delay-150">
          {tx(
            "Automatically transform network firewall logs, VAPT scans, and email threats into executive summaries using advanced AI models.",
            "Automatically transform network firewall logs, VAPT scans, and email threats into executive summaries using advanced AI models."
          )}
        </p>

        <div className="pt-2 animate-fadeInUp delay-200">
          <Link
            href="/generate"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs tracking-wider uppercase shadow-lg hover:shadow-xl transition-all duration-300 group cursor-pointer"
          >
            {tx("Get Started Wizard", "Get Started Wizard")}
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4 transition-transform group-hover:translate-x-1">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        </div>
      </div>

      {/* Feature badge pills */}
      <div className="mt-14 flex flex-wrap items-center justify-center gap-4 max-w-4xl relative z-10 animate-fadeInUp delay-300">
        <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
          <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-650 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          </div>
          <div className="text-left leading-tight">
            <div className="font-bold text-stone-855 text-xs">{tx("Division Compliant", "Division Compliant")}</div>
            <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{tx("PT Petrokimia Gresik", "PT Petrokimia Gresik")}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
          <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
            </svg>
          </div>
          <div className="text-left leading-tight">
            <div className="font-bold text-stone-855 text-xs">{tx("90% Time Saved", "90% Time Saved")}</div>
            <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{tx("Local offline analytics", "Local offline analytics")}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 px-4.5 py-3 rounded-2xl border border-stone-200/80 bg-white text-stone-700 text-xs font-semibold shadow-sm premium-card-hover select-none">
          <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4.5 h-4.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>
          <div className="text-left leading-tight">
            <div className="font-bold text-stone-855 text-xs">{tx("PDF & PPTX Output", "PDF & PPTX Output")}</div>
            <div className="text-[10px] text-stone-400 font-semibold mt-0.5">{tx("Multi-format support", "Multi-format support")}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
