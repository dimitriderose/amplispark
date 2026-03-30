import os
import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")


async def send_calendar_email(to_email: str, brand_name: str, ics_content: str):
    """Send a content plan .ics file as a calendar invite email."""
    resend.Emails.send({
        "from": "Amplispark <onboarding@resend.dev>",
        "to": to_email,
        "subject": f"Your {brand_name} Content Calendar — Amplispark",
        "html": (
            f"<p>Hi! Your 7-day content plan for <strong>{brand_name}</strong> "
            "is attached as a calendar file.</p>"
            "<p>Open the attachment or click 'Add to Calendar' to import all "
            "your posting events.</p>"
            "<p>— Amplispark</p>"
        ),
        "attachments": [{
            "filename": "amplispark_content_plan.ics",
            "content_type": "text/calendar; method=REQUEST; charset=utf-8",
            "content": ics_content,
        }],
    })
