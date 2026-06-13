import LegalPage from "./LegalPage.jsx";

// NOTE: Replace the [BRACKETED] placeholders before publishing.
const CONTACT_EMAIL = "yrshubhan@gmail.com";
const APP_NAME = "CourseMate";

export default function PrivacyPolicy() {
  return (
    <LegalPage title="Privacy Policy" lastUpdated="June 13, 2026">
      <p>
        This Privacy Policy describes how {APP_NAME} ("we", "us", or "our")
        collects, uses, and protects your information when you use our
        application. By using {APP_NAME}, you agree to the practices described
        below.
      </p>

      <h2>Information We Collect</h2>
      <ul>
        <li>
          <strong>Account information.</strong> When you sign in with Google, we
          receive your name, email address, and profile picture as provided by
          Google. We do not receive or store your Google password.
        </li>
        <li>
          <strong>Course materials you provide.</strong> Documents, notes, and
          files you upload, or that you choose to sync from connected services,
          are stored so we can generate study materials for you.
        </li>
        <li>
          <strong>Connected service data.</strong> If you connect Google Drive
          or Notion, we access only the files and content you explicitly select
          in order to import them into your courses.
        </li>
        <li>
          <strong>Generated content.</strong> Quizzes, flashcards, summaries,
          chat history, and other study materials created from your sources.
        </li>
        <li>
          <strong>Usage data.</strong> Basic technical and usage information
          needed to operate and secure the service.
        </li>
      </ul>

      <h2>How We Use Your Information</h2>
      <ul>
        <li>To authenticate you and maintain your account.</li>
        <li>
          To process your course materials and generate study tools (quizzes,
          flashcards, summaries, and chat answers).
        </li>
        <li>To save your work and sync it across your sessions.</li>
        <li>To operate, maintain, secure, and improve the service.</li>
      </ul>

      <h2>AI Processing and Third-Party Providers</h2>
      <p>
        To generate study materials and chat responses, we send relevant
        portions of your course content to third-party large language model
        providers (such as OpenAI, Anthropic, and Google). These providers
        process the content solely to return results to you and do not use your
        data to train their models under our configuration. We do not sell your
        personal information.
      </p>

      <h2>Google User Data</h2>
      <p>
        {APP_NAME}'s use of information received from Google APIs adheres to the{" "}
        <a
          href="https://developers.google.com/terms/api-services-user-data-policy"
          target="_blank"
          rel="noopener noreferrer"
        >
          Google API Services User Data Policy
        </a>
        , including the Limited Use requirements. We access Google Drive content
        only to import the files you select, and we never use Google user data
        for advertising.
      </p>

      <h2>Data Storage and Security</h2>
      <p>
        Your data is stored in secured cloud infrastructure. We use industry
        standard measures such as encrypted connections (HTTPS) and access
        controls to protect your information. No method of transmission or
        storage is completely secure, and we cannot guarantee absolute security.
      </p>

      <h2>Data Retention and Deletion</h2>
      <p>
        We retain your data for as long as your account is active. You may delete
        your courses and materials at any time from within the app. To delete
        your account and all associated data, contact us at the address below and
        we will process your request.
      </p>

      <h2>Your Rights</h2>
      <p>
        Depending on your location, you may have the right to access, correct, or
        delete your personal information, or to revoke connected-service access
        (which you can also do directly from your Google or Notion account
        settings). To exercise these rights, contact us.
      </p>

      <h2>Children's Privacy</h2>
      <p>
        {APP_NAME} is not directed to children under 13, and we do not knowingly
        collect personal information from them.
      </p>

      <h2>Changes to This Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. Material changes will
        be reflected by updating the "Last updated" date above.
      </p>

      <h2>Contact Us</h2>
      <p>
        If you have questions about this Privacy Policy, contact us at{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalPage>
  );
}
