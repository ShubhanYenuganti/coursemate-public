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
        setTimeout(initializeGoogleSignIn, 100);
      }
    };

    initializeGoogleSignIn();
  }, [onGoogleSignIn]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50 flex items-center justify-center px-4 py-12">
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

                {/* Divider */}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-200"></div>
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-white px-4 text-sm text-gray-500 font-medium">Or continue with</span>
                  </div>
                </div>

                {/* Email / Password placeholders */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Email address</label>
                    <div className="relative">
                      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                        <rect width="20" height="16" x="2" y="4" rx="2" />
                        <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                      </svg>
                      <input
                        type="email"
                        placeholder="Enter your email"
                        disabled
                        className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg bg-gray-50 text-gray-400 cursor-not-allowed focus:outline-none"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Password</label>
                    <div className="relative">
                      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                        <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                      <input
                        type="password"
                        placeholder="Enter your password"
                        disabled
                        className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg bg-gray-50 text-gray-400 cursor-not-allowed focus:outline-none"
                      />
                    </div>
                  </div>

                  <button
                    disabled
                    className="w-full h-12 bg-gradient-to-r from-indigo-300 to-cyan-300 text-white font-medium rounded-lg cursor-not-allowed opacity-60"
                  >
                    Sign in
                  </button>
                </div>
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

        <div className="text-center text-sm text-gray-600 mt-6">
          Don&apos;t have an account?{" "}
          <span className="font-semibold text-indigo-600">Sign up</span>
        </div>
      </div>
    </div>
  );
}
