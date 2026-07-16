"use client";

import { useEffect, useState } from "react";

export default function ScrollProgressBar() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        const currentProgress = (window.scrollY / totalHeight) * 100;
        setProgress(currentProgress);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="fixed top-0 left-0 right-0 h-[3px] bg-stone-200/30 z-[100] pointer-events-none">
      <div
        className="h-full bg-petro-yellow transition-all duration-75 ease-out rounded-r-full shadow-[0_0_8px_rgba(217,167,0,0.5)]"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
