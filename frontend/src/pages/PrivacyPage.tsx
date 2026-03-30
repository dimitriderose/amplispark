import { A } from '../theme'

export default function PrivacyPage() {
  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px 80px' }}>
      <h1 style={{ fontSize: 32, fontWeight: 700, color: A.text, marginBottom: 8 }}>Privacy Policy</h1>
      <p style={{ fontSize: 13, color: A.textMuted, marginBottom: 32 }}>Last updated: February 27, 2026</p>

      <div style={{ fontSize: 14, color: A.textSoft, lineHeight: 1.8 }}>
        <Section title="1. Overview">
          Amplispark ("we", "our", "the Service") is committed to protecting your privacy. This policy explains what data we collect, how we use it, and your rights.
        </Section>

        <Section title="2. Data We Collect">
          <p style={{ fontWeight: 600, color: A.text, marginBottom: 6 }}>Information you provide:</p>
          <ul style={{ paddingLeft: 20, marginBottom: 12 }}>
            <li>Brand information (business name, description, website URL, industry)</li>
            <li>Uploaded assets (logos, product photos)</li>
            <li>Social media access tokens (for voice analysis)</li>
            <li>Email address (only if you use the calendar email feature)</li>
          </ul>
          <p style={{ fontWeight: 600, color: A.text, marginBottom: 6 }}>Automatically collected:</p>
          <ul style={{ paddingLeft: 20 }}>
            <li>Anonymous Firebase authentication identifier (no personal information)</li>
            <li>Basic usage data (pages visited, features used)</li>
          </ul>
        </Section>

        <Section title="3. How We Use Your Data">
          <ul style={{ paddingLeft: 20 }}>
            <li><strong>Brand analysis:</strong> Your business description and website URL are sent to Google Gemini to generate your brand profile</li>
            <li><strong>Content generation:</strong> Your brand profile is used to generate captions, images, and videos</li>
            <li><strong>Voice analysis:</strong> Social media tokens are used to fetch your recent posts for writing style analysis, then discarded</li>
            <li><strong>Calendar delivery:</strong> Your email address is used solely to send the calendar invite you requested</li>
            <li><strong>Integration tokens:</strong> Third-party tokens (Notion, Buffer) are stored encrypted and used only to publish content on your behalf</li>
          </ul>
        </Section>

        <Section title="4. Data Storage">
          <ul style={{ paddingLeft: 20 }}>
            <li>Brand profiles and generated content are stored in Google Cloud Firestore</li>
            <li>Uploaded images and generated media are stored in Google Cloud Storage</li>
            <li>All data is stored in Google Cloud Platform infrastructure</li>
            <li>Social media access tokens are stored server-side and never exposed to the frontend</li>
          </ul>
        </Section>

        <Section title="5. Third-Party Services">
          We use the following third-party services to operate Amplispark:
          <ul style={{ paddingLeft: 20, marginTop: 8 }}>
            <li><strong>Google Cloud / Gemini API:</strong> AI content generation, data storage, and video generation</li>
            <li><strong>Firebase:</strong> Anonymous authentication</li>
            <li><strong>Resend:</strong> Email delivery for calendar invites</li>
            <li><strong>Notion API:</strong> Content calendar export (when connected by user)</li>
            <li><strong>Buffer API:</strong> Social media publishing (when connected by user)</li>
          </ul>
          <p style={{ marginTop: 8 }}>Each service has its own privacy policy. We encourage you to review them.</p>
        </Section>

        <Section title="6. Data Sharing">
          We do not sell, rent, or share your personal data with third parties for marketing purposes. Data is only shared with the third-party services listed above as necessary to provide the Service.
        </Section>

        <Section title="7. Data Retention">
          Brand data and generated content are retained as long as your anonymous session remains active. Since no account creation is required, data is associated with your browser's anonymous session. You can request deletion by contacting us through the project's GitHub repository.
        </Section>

        <Section title="8. Your Rights">
          You have the right to:
          <ul style={{ paddingLeft: 20, marginTop: 8 }}>
            <li>Access the data we hold about your brand profile</li>
            <li>Request deletion of your brand data and generated content</li>
            <li>Disconnect third-party integrations at any time</li>
            <li>Export your content using our download and export features</li>
          </ul>
        </Section>

        <Section title="9. Cookies">
          Amplispark uses minimal browser storage (localStorage and sessionStorage) to maintain your session and brand preferences. We do not use tracking cookies or third-party analytics cookies.
        </Section>

        <Section title="10. Children's Privacy">
          The Service is not directed at children under 13. We do not knowingly collect personal information from children.
        </Section>

        <Section title="11. Changes to This Policy">
          We may update this Privacy Policy at any time. Changes will be reflected by the "Last updated" date above.
        </Section>

        <Section title="12. Contact">
          For privacy-related questions or data deletion requests, please reach out through the project's GitHub repository.
        </Section>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: A.text, marginBottom: 8 }}>{title}</h2>
      <div>{children}</div>
    </div>
  )
}
