"use client";

import { useEffect, useRef } from "react";

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => void;
  onError: (errorMsg: string) => void;
  loading: boolean;
}

export default function GoogleSignInButton({ onSuccess, onError, loading }: GoogleSignInButtonProps) {
  // Callback terbaru disimpan di ref (bukan dependency effect), supaya effect di bawah
  // tidak perlu re-run tiap kali komponen induk re-render dan bikin onSuccess/onError
  // ganti referensi — itu penyebab google.accounts.id.initialize() sempat terpanggil berkali-kali.
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  }, [onSuccess, onError]);

  useEffect(() => {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "126885950302-sua5h4t01g4qfaug5m7c9is04uvhce88.apps.googleusercontent.com";
    let initialized = false;

    const handleCredentialResponse = (response: any) => {
      console.log("[GOOGLE AUTH] 🌐 Menerima credential token dari Google OAuth.");
      if (response && response.credential) {
        onSuccessRef.current(response.credential);
      } else {
        onErrorRef.current("Gagal mendapatkan kredensial dari Google.");
      }
    };

    const initializeGoogle = () => {
      if (!(window as any).google?.accounts?.id) return;

      const buttonDiv = document.getElementById("google-signin-btn");
      if (!buttonDiv) return;

      try {
        (window as any).google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        buttonDiv.innerHTML = "";
        (window as any).google.accounts.id.renderButton(
          buttonDiv,
          {
            theme: "outline",
            size: "large",
            width: buttonDiv.clientWidth || 360,
            text: "signin_with",
            shape: "rectangular"
          }
        );
      } catch (e) {
        console.warn("[GOOGLE AUTH] Exception initializing Google Sign-In:", e);
      }
    };

    if (typeof window !== "undefined") {
      const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
      if (existingScript) {
        if ((window as any).google) {
          initializeGoogle();
        } else {
          existingScript.addEventListener("load", initializeGoogle);
        }
      } else {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        script.defer = true;
        script.onload = initializeGoogle;
        document.body.appendChild(script);
      }
    }
    // Deps kosong: script Google dimuat & diinisialisasi sekali per mount komponen,
    // tidak setiap kali prop onSuccess/onError berganti identitas.
  }, []);

  return (
    <div className="flex justify-center w-full min-h-[44px]">
      <div id="google-signin-btn" className="flex justify-center w-full"></div>
    </div>
  );
}
