"use client";

import { useEffect } from "react";

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => void;
  onError: (errorMsg: string) => void;
  loading: boolean;
}

export default function GoogleSignInButton({ onSuccess, onError, loading }: GoogleSignInButtonProps) {
  useEffect(() => {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "126885950302-sua5h4t01g4qfaug5m7c9is04uvhce88.apps.googleusercontent.com";

    const handleCredentialResponse = (response: any) => {
      console.log("[GOOGLE AUTH] 🌐 Menerima credential token dari Google OAuth.");
      if (response && response.credential) {
        onSuccess(response.credential);
      } else {
        onError("Gagal mendapatkan kredensial dari Google.");
      }
    };

    const initializeGoogle = () => {
      if ((window as any).google) {
        (window as any).google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleCredentialResponse,
        });
        
        const buttonDiv = document.getElementById("google-signin-btn");
        if (buttonDiv) {
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
        }
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
  }, [onSuccess, onError]);

  return (
    <div className="flex justify-center w-full min-h-[44px]">
      <div id="google-signin-btn" className="flex justify-center w-full"></div>
    </div>
  );
}
