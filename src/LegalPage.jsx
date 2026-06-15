import { Link } from "react-router-dom";

// Shared shell for the static legal pages (privacy policy, terms of service).
// Public — no auth gate — so Google's OAuth verifier can crawl them.
export default function LegalPage({ title, lastUpdated, children }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background/70 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-xl flex items-center justify-center">
              <span className="text-sm font-bold text-white">CM</span>
            </div>
            <span className="font-semibold text-foreground">CourseMate</span>
          </Link>
          <Link to="/" className="text-sm text-primary hover:text-accent-foreground font-medium">
            ← Back to home
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-bold text-foreground mb-2">{title}</h1>
        <p className="text-sm text-muted-foreground mb-10">Last updated: {lastUpdated}</p>
        <div className="prose prose-primary max-w-none text-foreground space-y-6 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mt-8 [&_h2]:mb-2 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-1 [&_a]:text-primary [&_a]:underline">
          {children}
        </div>
      </main>

      <footer className="max-w-3xl mx-auto px-6 py-10 text-sm text-muted-foreground border-t border-border flex gap-6">
        <Link to="/privacy" className="hover:text-foreground">Privacy Policy</Link>
        <Link to="/terms" className="hover:text-foreground">Terms of Service</Link>
      </footer>
    </div>
  );
}
