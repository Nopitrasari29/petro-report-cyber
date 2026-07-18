"use client";

import { useEffect, useRef, useState, ReactNode } from "react";

interface ScrollRevealProps {
  children: ReactNode;
  className?: string;
  animation?: "fadeInUp" | "fadeIn" | "scaleIn" | "slideInLeft" | "slideInRight";
  delay?: number;
  duration?: number;
  threshold?: number;
  triggerOnce?: boolean;
}

export default function ScrollReveal({
  children,
  className = "",
  animation = "fadeInUp",
  delay = 0,
  duration = 800, // Durasi 800ms sangat ideal untuk transisi lambat yang elegan
  threshold = 0.05, // Diturunkan sedikit ke 0.05 agar animasi langsung terpicu saat tepi kartu menyentuh layar
  triggerOnce = false,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (triggerOnce) {
            observer.unobserve(entry.target);
          }
        } else {
          if (!triggerOnce) {
            setIsVisible(false);
          }
        }
      },
      {
        threshold,
        // Margin bawah disesuaikan agar transisi masuk dan keluar terasa sangat halus saat di-scroll
        rootMargin: "0px 0px -40px 0px",
      }
    );

    const currentRef = ref.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [threshold, triggerOnce]);

  const getAnimationClass = () => {
    switch (animation) {
      case "fadeIn":
        return isVisible ? "opacity-100" : "opacity-0";
      case "scaleIn":
        return isVisible
          ? "opacity-100 scale-100"
          : "opacity-0 scale-90";
      case "slideInLeft":
        return isVisible
          ? "opacity-100 translate-x-0"
          : "opacity-0 -translate-x-12";
      case "slideInRight":
        return isVisible
          ? "opacity-100 translate-x-0"
          : "opacity-0 translate-x-12";
      case "fadeInUp":
      default:
        return isVisible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-12"; // Jarak luncur 12 unit sangat pas dan anggun
    }
  };

  return (
    // Parent Div (ref): Diam secara statis di posisinya sebagai jangkar sensor
    <div ref={ref} className={className}>
      {/* Child Div: Menerima seluruh efek transisi visual animasi */}
      <div
        className={`transition-all ease-out ${getAnimationClass()}`}
        style={{
          transitionDelay: `${delay}ms`,
          transitionDuration: `${duration}ms`,
        }}
      >
        {children}
      </div>
    </div>
  );
}