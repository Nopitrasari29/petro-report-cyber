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
  duration = 1000, // Dinaikkan menjadi 1000ms (1 detik) agar transisi lambat, halus, dan sinematik
  threshold = 0.1,
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
        // Memberikan sedikit ruang margin atas dan bawah agar transisi masuk-keluar terasa lebih mulus
        rootMargin: "-20px 0px -20px 0px",
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
          : "opacity-0 scale-90"; // Jangkauan skala diturunkan ke 90 agar efek membesar lebih terlihat jelas
      case "slideInLeft":
        return isVisible
          ? "opacity-100 translate-x-0"
          : "opacity-0 -translate-x-12"; // Jarak geser diperlebar agar efek terlihat jelas
      case "slideInRight":
        return isVisible
          ? "opacity-100 translate-x-0"
          : "opacity-0 translate-x-12"; // Jarak geser diperlebar agar efek terlihat jelas
      case "fadeInUp":
      default:
        return isVisible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-16"; // Jarak luncur vertikal diperbesar agar efek terlihat jelas
    }
  };

  return (
    <div
      ref={ref}
      className={`transition-all ease-out ${getAnimationClass()} ${className}`}
      style={{
        transitionDelay: `${delay}ms`,
        transitionDuration: `${duration}ms`,
      }}
    >
      {children}
    </div>
  );
}