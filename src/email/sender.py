"""
Email sender using SendGrid.

Sends HTML emails for strong buy signals.
"""

import os
from typing import List, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailSender:
    """Send emails via SendGrid."""

    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None):
        """
        Initialize email sender.

        Args:
            api_key: SendGrid API key (or use SENDGRID_API_KEY env var)
            from_email: Sender email address (or use FROM_EMAIL env var)
        """
        self.api_key = api_key or os.getenv('SENDGRID_API_KEY')
        self.from_email = from_email or os.getenv('FROM_EMAIL', 'alerts@openinsidertrader.com')

        if not self.api_key:
            raise ValueError("SendGrid API key not provided. Set SENDGRID_API_KEY environment variable.")

        self.client = SendGridAPIClient(self.api_key)

    def send_alert(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Send a single alert email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            plain_content: Plain text fallback (optional)

        Returns:
            bool: True if sent successfully
        """
        try:
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            if plain_content:
                message.plain_text_content = Content("text/plain", plain_content)

            response = self.client.send(message)

            # SendGrid returns 202 for accepted
            return response.status_code == 202

        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {e}")
            return False

    def send_batch_alerts(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> dict:
        """
        Send alerts to multiple recipients.

        Args:
            recipients: List of email addresses
            subject: Email subject
            html_content: HTML email body
            plain_content: Plain text fallback

        Returns:
            dict: {email: success_bool}
        """
        results = {}
        for email in recipients:
            results[email] = self.send_alert(email, subject, html_content, plain_content)
        return results
