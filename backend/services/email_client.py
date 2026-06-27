import asyncio
import logging
import os
from typing import Any, cast

import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

logger = logging.getLogger(__name__)


async def send_waitlist_confirmation(to_email: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: resend.Emails.send(
                {
                    "from": "Amplispark <onboarding@resend.dev>",
                    "to": to_email,
                    "subject": "You're on the Amplispark waitlist!",
                    "html": (
                        "<p>Thanks for signing up! You're on the Amplispark waitlist.</p>"
                        "<p>We'll reach out as soon as your account is approved and ready to go.</p>"
                        "<p>— The Amplispark Team</p>"
                    ),
                }
            ),
        )
    except Exception:
        logger.error("send_waitlist_confirmation: failed to send email to %s", to_email)


async def send_calendar_email(to_email: str, brand_name: str, ics_content: str):
    """Send a content plan .ics file as a calendar invite email."""
    resend.Emails.send(
        {
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
            "attachments": [
                cast(
                    Any,
                    {
                        "filename": "amplispark_content_plan.ics",
                        "content_type": "text/calendar; method=REQUEST; charset=utf-8",
                        "content": ics_content,
                    },
                )
            ],
        }
    )
