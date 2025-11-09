"""Email alert system."""

from .sender import EmailSender
from .templates import render_alert_email

__all__ = ['EmailSender', 'render_alert_email']
