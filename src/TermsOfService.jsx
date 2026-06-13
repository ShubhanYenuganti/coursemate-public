import LegalPage from "./LegalPage.jsx";

// NOTE: Replace the [BRACKETED] placeholders before publishing.
const CONTACT_EMAIL = "yrshubhan@gmail.com";
const APP_NAME = "CourseMate";
const GOVERNING_LAW = "[State of California, USA]";

export default function TermsOfService() {
  return (
    <LegalPage title="Terms of Service" lastUpdated="June 13, 2026">
      <p>
        These Terms of Service ("Terms") govern your access to and use of {APP_NAME}{" "}
        (the "Service"). By accessing or using the Service, you agree to be bound
        by these Terms. If you do not agree, do not use the Service.
      </p>

      <h2>Eligibility and Accounts</h2>
      <p>
        You must be at least 13 years old to use the Service. You sign in using
        your Google account and are responsible for maintaining the security of
        your account and for all activity that occurs under it.
      </p>

      <h2>Acceptable Use</h2>
      <ul>
        <li>
          You may only upload or connect content that you own or have the right to
          use.
        </li>
        <li>
          You may not use the Service for any unlawful purpose, to infringe others'
          rights, or to attempt to disrupt or gain unauthorized access to the
          Service.
        </li>
        <li>
          You may not misuse the AI features to generate harmful, illegal, or
          abusive content.
        </li>
      </ul>

      <h2>Your Content</h2>
      <p>
        You retain ownership of the course materials and other content you upload
        or connect ("Your Content"). You grant us a limited license to store,
        process, and transmit Your Content solely to operate the Service and
        provide its features to you — including sending relevant portions to
        third-party AI providers to generate study materials and chat responses.
      </p>

      <h2>AI-Generated Content</h2>
      <p>
        The Service uses artificial intelligence to generate quizzes, flashcards,
        summaries, and chat answers. AI output may be inaccurate or incomplete and
        is provided for study assistance only. You are responsible for verifying
        any information before relying on it. The Service is not a substitute for
        professional or academic advice.
      </p>

      <h2>Third-Party Services</h2>
      <p>
        The Service integrates with third-party services such as Google Drive and
        Notion. Your use of those services is governed by their respective terms
        and privacy policies. We are not responsible for third-party services.
      </p>

      <h2>Service Availability</h2>
      <p>
        We provide the Service on an "as is" and "as available" basis. We may
        modify, suspend, or discontinue any part of the Service at any time without
        liability to you.
      </p>

      <h2>Disclaimer of Warranties</h2>
      <p>
        To the fullest extent permitted by law, the Service is provided without
        warranties of any kind, whether express or implied, including
        merchantability, fitness for a particular purpose, and non-infringement.
      </p>

      <h2>Limitation of Liability</h2>
      <p>
        To the fullest extent permitted by law, {APP_NAME} and its operators will
        not be liable for any indirect, incidental, special, consequential, or
        punitive damages, or any loss of data, arising out of or related to your
        use of the Service.
      </p>

      <h2>Termination</h2>
      <p>
        You may stop using the Service at any time. We may suspend or terminate
        your access if you violate these Terms. Upon termination, your right to use
        the Service ceases.
      </p>

      <h2>Governing Law</h2>
      <p>
        These Terms are governed by the laws of {GOVERNING_LAW}, without regard to
        its conflict-of-laws principles.
      </p>

      <h2>Changes to These Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be
        reflected by updating the "Last updated" date above. Continued use of the
        Service after changes take effect constitutes acceptance.
      </p>

      <h2>Contact Us</h2>
      <p>
        Questions about these Terms? Contact us at{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalPage>
  );
}
