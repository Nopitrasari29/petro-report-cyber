import ScrollReveal from "@/components/ScrollReveal";

interface LandingHowItWorksProps {
  tx: (key: string, fallback: string) => string;
}

export default function LandingHowItWorks({ tx }: LandingHowItWorksProps) {
  const steps = [
    {
      number: 1,
      title: tx("Upload Data", "Upload Data"),
      desc: tx("Upload your security evidence files. Supported formats: PDF, CSV, XLSX", "Upload your security evidence files. Supported formats: PDF, CSV, XLSX"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
      ),
    },
    {
      number: 2,
      title: tx("Report Settings", "Report Settings"),
      desc: tx("Set period, template, format, and other preferences for your report", "Set period, template, format, and other preferences for your report"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
        </svg>
      ),
    },
    {
      number: 3,
      title: tx("AI Processing", "AI Processing"),
      desc: tx("Our AI will analyze the data and generate insights, charts, and summary", "Our AI will analyze the data and generate insights, charts, and summary"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-350 group-hover:rotate-12 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
        </svg>
      ),
    },
    {
      number: 4,
      title: tx("Preview & Edit", "Preview & Edit"),
      desc: tx("Review AI generated content and make any necessary edits", "Review AI generated content and make any necessary edits"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
        </svg>
      ),
    },
    {
      number: 5,
      title: tx("Export Report", "Export Report"),
      desc: tx("Export your report to PDF or PowerPoint format", "Export your report to PDF or PowerPoint format"),
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-6 h-6 transition-transform duration-300 group-hover:scale-110">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
      ),
    },
  ];

  return (
    <section className="relative py-20 px-6 bg-[#f2f4f0] border-b border-stone-200/40 overflow-hidden text-stone-900">
      <div className="absolute inset-0 bg-[radial-gradient(rgba(0,77,37,0.045)_1.2px,transparent_1.2px)] bg-[size:24px_24px] pointer-events-none" />

      {/* Kontainer Induk Layang */}
      <div className="relative z-10 max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <ScrollReveal animation="fadeIn" delay={100}>
            <span className="text-[10px] font-extrabold tracking-widest text-petro-yellow uppercase bg-petro-yellow-light border border-petro-yellow/20 px-3 py-1 rounded-full">{tx("Process Flow", "Process Flow")}</span>
            <h2 className="text-3xl font-extrabold text-stone-900 mt-3.5">{tx("How It Works", "How It Works")}</h2>
            <p className="text-xs text-stone-455 font-bold mt-1.5 max-w-md mx-auto">{tx("Transform complex cybersecurity logs into structured reports in five simple phases.", "Transform complex cybersecurity logs into structured reports in five simple phases.")}</p>
          </ScrollReveal>
        </div>

        {/* Desktop timeline horizontal view */}
        <div className="hidden md:flex items-center justify-center gap-0 w-full">
          {steps.map((step, i) => (
            <div key={step.number} className="flex items-center flex-1">
              {/* Step Node Card */}
              <ScrollReveal
                animation="fadeInUp"
                delay={i * 200}
                className="flex-1"
              >
                <div className="flex flex-col items-center text-center group premium-card-hover p-4 bg-white border border-stone-200/80 rounded-2xl cursor-default shadow-sm min-h-[195px] justify-between transition-colors duration-300">
                  <div className="relative w-14 h-14 rounded-2xl bg-petro-green-light border border-petro-green/10 flex items-center justify-center text-petro-green shrink-0">
                    {step.icon}
                    <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-lg bg-petro-yellow text-white text-[9px] font-extrabold flex items-center justify-center border border-white shadow-sm">
                      {step.number}
                    </span>
                  </div>
                  <div className="mt-4 flex-1 flex flex-col justify-center">
                    <h3 className="font-bold text-stone-855 text-xs tracking-tight group-hover:text-petro-green transition-colors duration-200">{step.title}</h3>
                    <p className="text-[10px] text-stone-400 font-semibold mt-1 leading-relaxed max-w-[140px] mx-auto">{step.desc}</p>
                  </div>
                </div>
              </ScrollReveal>

              {/* Panah Konektor Emas Siber Berdenyut */}
              {i < steps.length - 1 && (
                <ScrollReveal
                  animation="fadeIn"
                  delay={(i * 200) + 120}
                  className="shrink-0 mx-2"
                >
                  <div className="flex items-center justify-center text-petro-yellow select-none">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-5 h-5 animate-pulse drop-shadow-sm">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                    </svg>
                  </div>
                </ScrollReveal>
              )}
            </div>
          ))}
        </div>

        {/* Mobile vertical layout list */}
        <div className="md:hidden space-y-4">
          {steps.map((step, i) => (
            <ScrollReveal
              key={step.number}
              animation="fadeInUp"
              delay={i * 150}
              className="w-full"
            >
              <div className="flex items-start gap-4 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm premium-card-hover transition-colors duration-300">
                <div className="relative w-11 h-11 rounded-xl bg-petro-green-light border border-petro-green/15 flex items-center justify-center text-petro-green shrink-0">
                  <span className="font-extrabold text-sm">{step.number}</span>
                </div>
                <div className="text-left">
                  <h3 className="font-bold text-stone-855 text-xs">{step.title}</h3>
                  <p className="text-[10px] text-stone-450 font-semibold mt-0.5 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
