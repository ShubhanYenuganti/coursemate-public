import { useEffect } from "react";

export default function SignInPage({ loading, error, onGoogleSignIn }) {
  useEffect(() => {
    const initializeGoogleSignIn = () => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
          callback: onGoogleSignIn,
        });

        const buttonDiv = document.getElementById("googleSignInButton");
        if (buttonDiv) {
          buttonDiv.innerHTML = "";
          window.google.accounts.id.renderButton(buttonDiv, {
            theme: "outline",
            size: "large",
            text: "signin_with",
            shape: "rectangular",
            width: 300,
          });
        }
      } else {
        setTimeout(initializeGoogl4eSignIn, 100);
      }
    };

    initializeGoogleSignIn();
  }, [onGoogleSignIn]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md animate-[fadeInUp_0.6s_ease-out]">
        {/* Logo / Brand */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-2xl mx-auto mb-4 flex items-center justify-center animate-[float_3s_ease-in-out_infinite]">
            <span className="text-2xl font-bold text-white">CM</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome to CourseMate</h1>
          <p className="text-gray-600">Sign in to access your personalized learning experience</p>
        </div>

        {/* Card */}
        <div className="p-8 shadow-xl border-0 bg-white/80 backdrop-blur-sm rounded-2xl">
          <div className="space-y-6">
            {loading ? (
              <div className="flex flex-col items-center gap-4 py-8">
                <div className="w-10 h-10 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin"></div>
                <p className="text-gray-500 text-sm font-medium">Verifying your credentials...</p>
              </div>
            ) : (
              <>
                {/* Native Google button */}
                <div className="flex justify-center" id="googleSignInButton"></div>

              </>
            )}

            {error && (
              <div className="bg-red-50 border-2 border-red-300 rounded-xl p-4 text-red-700 text-left animate-[shake_0.5s_ease-in-out]">
                <strong className="block mb-1">Authentication Failed</strong>
                {error}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
