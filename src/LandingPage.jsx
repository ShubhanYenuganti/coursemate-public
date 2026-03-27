import { useState } from "react";
import { useNavigate } from "react-router-dom";

const FEATURES = [
  {
    id: "rag",
    label: "RAG-Powered Chat",
    title: "RAG-Powered Chat",
    subtitle: "Answers grounded in your materials",
    description:
      "Ask anything about your course. CourseMate retrieves the most relevant chunks from your uploaded documents and streams a grounded answer with whichever LLM you've connected.",
    bullets: [
      "Retrieves relevant course chunks before every answer",
      "Streams responses with source grounding metadata",
      "Use GPT, Claude, or Gemini — bring your own API key for each",
    ],
    badges: ["OpenAI", "Anthropic", "Google Gemini"],
  },
  {
    id: "web",
    label: "Agentic Web Search",
    title: "Agentic Web Search",
    subtitle: "Goes beyond your notes when needed",
    description:
      "When your uploaded materials don't have the answer, CourseMate can search the web autonomously — pulling in fresh, cited sources to supplement your course content.",
    bullets: [
      "Automatically detects when web search is needed",
      "Returns cited, real-time results alongside document context",
      "Fully optional — you stay in control of when it activates",
    ],
    badges: ["OpenAI", "Anthropic", "Google Gemini"],
  },
  {
    id: "async",
    label: "Async Generation",
    title: "Async Generation",
    subtitle: "Generate while you study",
    description:
      "Quizzes, flashcards, and reports are generated asynchronously in the background — fast, queued, and ready when you are. No waiting at a spinner.",
    bullets: [
      "Non-blocking — keep studying while content generates",
      "Progress tracked across sessions",
      "Regenerate or resolve conflicts with full version history",
    ],
    badges: ["OpenAI", "Anthropic", "Google Gemini"],
  },
];

const GENERATE_TABS = [
  {
    id: "quiz",
    label: "Quiz",
    description:
      "Multiple choice, true/false, short answer, and long answer, with study mode. Generated from your materials using the model you choose.",
  },
  {
    id: "flashcards",
    label: "Flashcards",
    description:
      "Term-and-definition cards built directly from your notes. Study them in flip mode or export for use in other tools.",
  },
  {
    id: "reports",
    label: "Reports",
    description:
      "Structured summaries and study guides generated from your course materials. Great for exam prep and quick review.",
  },
];

const FAQ_ITEMS = [
  {
    q: "How are my API keys stored?",
    a: "Your API keys are encrypted at rest and never logged or shared. They are stored securely in the database and only decrypted server-side when making model calls on your behalf.",
  },
  {
    q: "Which LLM providers are supported?",
    a: "CourseMate supports OpenAI (GPT-4o, GPT-4 Turbo, etc.), Anthropic (Claude 3.5, Claude 3 Opus, etc.), and Google Gemini (1.5 Pro, 1.5 Flash, etc.). You can bring keys for one or all three.",
  },
  {
    q: "Can I use a different model for chat vs. generation?",
    a: "Yes. You can select a different model for chat and for each generation type (quizzes, flashcards, reports) independently.",
  },
  {
    q: "What does async generation mean?",
    a: "Generation tasks (quizzes, flashcards, reports) are queued and run in the background. You don't have to wait on the page — the result appears in your history when it's ready.",
  },
  {
    q: "Does CourseMate search the web?",
    a: "Optionally, yes. Agentic web search can be enabled per-chat. When active, CourseMate will search the web when your uploaded materials don't contain a sufficient answer.",
  },
];

function ProviderBadges({ providers }) {
  const icons = { OpenAI: "○", Anthropic: "◆", "Google Gemini": "✦" };
  return (
    <div className="flex items-center gap-2 text-sm text-gray-600">
      {providers.map((p) => (
        <span key={p} className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-gray-200 bg-white">
          <span>{icons[p]}</span>
          <span>{p}</span>
        </span>
      ))}
    </div>
  );
}

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-gray-200">
      <button
        className="w-full flex items-center justify-between py-4 text-left text-gray-900 font-medium hover:text-indigo-600 transition-colors"
        onClick={() => setOpen(!open)}
      >
        {q}
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <p className="pb-4 text-gray-600 text-sm leading-relaxed">{a}</p>}
    </div>
  );
}

const HOW_IT_WORKS = [
  {
    step: 1,
    title: "Sign in with Google",
    description: "One click, no passwords, no setup. Your Google account is all you need to get started.",
  },
  {
    step: 2,
    title: "Add your API keys",
    description: "Connect your OpenAI, Anthropic, or Google Gemini API keys. You pay providers directly, CourseMate never marks up usage.",
  },
  {
    step: 3,
    title: "Upload materials & start learning",
    description: "Upload PDFs, slides, or notes. CourseMate indexes them instantly. Start learning with refined selection of models for chat and generation. Chat right away or queue a quiz, flashcard deck, or report to pick up whenever it's ready.",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const [activeFeature, setActiveFeature] = useState("rag");
  const [activeGenerate, setActiveGenerate] = useState("quiz");
  const [activeStep, setActiveStep] = useState(1);

  const feature = FEATURES.find((f) => f.id === activeFeature);
  const generateTab = GENERATE_TABS.find((t) => t.id === activeGenerate);

  function goToSignIn() {
    navigate("/signin");
  }

  return (
    <div className="min-h-screen bg-white text-gray-900">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-md flex items-center justify-center">
              <span className="text-xs font-bold text-white">C</span>
            </div>
            <span className="font-semibold text-gray-900">CourseMate</span>
          </div>
          <button
            onClick={goToSignIn}
            className="px-4 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Sign up free
          </button>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-block px-3 py-1 bg-indigo-50 text-indigo-600 text-xs font-medium rounded-full mb-6">
          Your keys. Your models. Your learning.
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold leading-tight mb-6">
          Chat with your course —{" "}
          <span className="text-indigo-600">powered by the models you choose.</span>
        </h1>
        <p className="text-gray-600 text-lg leading-relaxed mb-3">
          Bring your own <span className="text-indigo-600 font-medium">OpenAI</span>,{" "}
          <span className="text-orange-500 font-medium">Anthropic</span>, or{" "}
          <span className="text-blue-500 font-medium">Google Gemini</span> API keys. CourseMate
          uses RAG to ground every answer in{" "}
          <span className="underline decoration-indigo-400">your uploaded materials</span>, with
          optional web search when your notes don't have the answer. Generate quizzes, flashcards,
          and reports asynchronously — fast, queued, ready when you are.
        </p>
        <p className="font-semibold text-gray-900 mb-8">Full control, full transparency.</p>
        <div className="flex flex-wrap justify-center gap-3 mb-10">
          <button
            onClick={goToSignIn}
            className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
          >
            Sign up free
          </button>
          <a
            href="#how-it-works"
            className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
          >
            See how it works
          </a>
        </div>
        <ProviderBadges providers={["OpenAI", "Anthropic", "Google Gemini"]} />
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-6">
            Features
          </p>
          {/* Card wrapping tabs + content */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          {/* Tabs - segmented control */}
          <div className="grid grid-cols-3 gap-1 bg-gray-100 rounded-xl p-1 mb-6">
            {FEATURES.map((f) => (
              <button
                key={f.id}
                onClick={() => setActiveFeature(f.id)}
                className={`px-4 py-2.5 text-sm font-medium rounded-lg transition-all ${
                  activeFeature === f.id
                    ? "bg-white text-indigo-600 shadow-sm border border-gray-200"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          {/* Feature content */}
          <div>
            <div className="flex items-start gap-3 mb-3">
              <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{feature.title}</h3>
                <p className="text-xs text-gray-500">{feature.subtitle}</p>
              </div>
            </div>
            <p className="text-gray-600 text-sm leading-relaxed mb-4">{feature.description}</p>
            <ul className="space-y-2 mb-5">
              {feature.bullets.map((b) => (
                <li key={b} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-indigo-500 mt-0.5">•</span>
                  {b}
                </li>
              ))}
            </ul>
            <ProviderBadges providers={feature.badges} />
          </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-16">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-8">
            How It Works
          </p>
          <div className="flex gap-6 items-start">
            {/* Steps list */}
            <div className="flex-1 border-l-2 border-gray-100 space-y-2">
              {HOW_IT_WORKS.map(({ step, title }) => {
                const active = step === activeStep;
                return (
                  <button
                    key={step}
                    onClick={() => setActiveStep(step)}
                    className={`w-full text-left px-5 py-4 rounded-xl transition-all ${
                      active
                        ? "bg-indigo-50 border border-indigo-300 border-l-4 border-l-indigo-500"
                        : "hover:bg-gray-50"
                    }`}
                  >
                    <p className={`text-xs font-semibold mb-1 ${active ? "text-indigo-600" : "text-gray-400"}`}>
                      Step {step}
                    </p>
                    <p className={`text-sm font-semibold ${active ? "text-gray-900" : "text-gray-400"}`}>
                      {title}
                    </p>
                  </button>
                );
              })}
            </div>
            {/* Description panel */}
            <div className="w-80 flex-shrink-0 bg-white border border-gray-200 rounded-xl p-6 shadow-sm min-h-[160px] flex items-center">
              <p className="text-gray-700 text-sm leading-relaxed">
                {HOW_IT_WORKS.find((s) => s.step === activeStep)?.description}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* What You Can Generate */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-6">
            What You Can Generate
          </p>
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            {/* Tabs - segmented control */}
            <div className="grid grid-cols-3 gap-1 bg-gray-100 rounded-xl p-1 mb-6">
              {GENERATE_TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveGenerate(t.id)}
                  className={`px-4 py-2.5 text-sm font-medium rounded-lg transition-all ${
                    activeGenerate === t.id
                      ? "bg-white text-indigo-600 shadow-sm border border-gray-200"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="flex items-start gap-2">
              <svg className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h8" />
              </svg>
              <div>
                <p className="text-sm font-medium text-gray-900">{generateTab.label}</p>
                <p className="text-sm text-gray-600 mt-1">{generateTab.description}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-8">FAQ</p>
          <div>
            {FAQ_ITEMS.map((item) => (
              <FaqItem key={item.q} q={item.q} a={item.a} />
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="bg-indigo-600 py-14 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Ready to learn smarter?</h2>
        <p className="text-indigo-200 mb-8">
          Bring your own API keys and start chatting with your course materials in minutes.
        </p>
        <button
          onClick={goToSignIn}
          className="px-8 py-3 bg-white text-indigo-600 font-semibold rounded-lg hover:bg-indigo-50 transition-colors shadow"
        >
          Sign up free
        </button>
      </section>
    </div>
  );
}
