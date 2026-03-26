"""
Inbound SMS webhook handler for VoIP Innovations.
Handles STOP/START/HELP opt-in commands and Y/N availability responses.
No authentication required — endpoint is called by VoIP Innovations.
"""
from datetime import datetime
from flask import Blueprint, request
from app import db
from app.models import Technician, JobAssignment, SMSNotification
from app.utils.logging import get_logger

sms_webhook_bp = Blueprint('sms_webhook', __name__)
logger = get_logger(__name__)


def _find_tech_by_phone(raw_number):
    """Look up a Technician by phone number (tolerant of formatting differences)."""
    import re
    # Normalize to last 10 digits
    digits = re.sub(r'[^\d]', '', raw_number or '')
    if not digits:
        return None
    lookup = digits[-10:]
    for tech in Technician.query.all():
        if tech.phone:
            tech_digits = re.sub(r'[^\d]', '', tech.phone)[-10:]
            if tech_digits == lookup:
                return tech
    return None


def _is_delivery_receipt(from_number, message_body):
    """
    Check if this inbound message is a delivery receipt (empty body arriving
    shortly after an outbound to the same number). If so, update the outbound's
    delivered_at and return True.
    """
    import re
    if message_body.strip():
        return False

    # Normalize to last 10 digits for matching
    digits = re.sub(r'[^\d]', '', from_number or '')
    if not digits:
        return False
    lookup = digits[-10:]

    # Find the most recent outbound to this number in the last 60 seconds
    cutoff = datetime.utcnow() - __import__('datetime').timedelta(seconds=60)
    recent_outbound = (
        SMSNotification.query
        .filter(
            SMSNotification.sent_at >= cutoff,
            SMSNotification.provider_message_id.isnot(None),  # outbound messages have this
            SMSNotification.phone_number.like(f'%{lookup}'),
        )
        .order_by(SMSNotification.sent_at.desc())
        .first()
    )

    if recent_outbound and not recent_outbound.delivered_at:
        recent_outbound.delivered_at = datetime.utcnow()
        recent_outbound.status = 'delivered'
        db.session.commit()
        logger.info(f"Delivery receipt matched to notification #{recent_outbound.notification_id}")
        return True

    return False


def _log_inbound(from_number, message_body, tech=None):
    """Persist the inbound message to sms_notifications."""
    notif = SMSNotification(
        notification_type='other',
        tech_id=tech.tech_id if tech else None,
        phone_number=from_number,
        message_body=f'[INBOUND] {message_body}',
        status='sent',
        sent_at=datetime.utcnow(),
    )
    db.session.add(notif)
    # Don't commit here — caller will commit after updating tech/assignment


def _reply(from_number, reply_text, tech=None, bypass_opt_in=False):
    """Send a reply SMS back to the sender."""
    from app.utils.sms_service import get_sms_service
    sms = get_sms_service()
    sms.reload_config()
    return sms.send_sms(
        to_number=from_number,
        message=reply_text,
        notification_type='other',
        tech_id=tech.tech_id if tech else None,
        bypass_opt_in_check=bypass_opt_in,
    )


@sms_webhook_bp.route('/sms/inbound', methods=['POST'])
def inbound_sms():
    """
    Handle inbound SMS from VoIP Innovations.

    VoIP Innovations posts form-encoded data. Field names may vary by account config;
    we check several common variants.
    """
    # Parse flexible field names from form data or JSON
    data = request.form or request.get_json(silent=True) or {}

    from_number = (
        data.get('from') or data.get('From') or
        data.get('sender') or data.get('Sender') or ''
    ).strip()

    message_body = (
        data.get('message') or data.get('Message') or
        data.get('body') or data.get('Body') or
        data.get('text') or data.get('Text') or ''
    ).strip()

    logger.info(f"Inbound SMS from {from_number}: {message_body[:80]}")

    if not from_number:
        logger.warning("Inbound SMS webhook called with no 'from' number")
        return '', 200

    msg = message_body.strip().upper()
    tech = _find_tech_by_phone(from_number)

    # --- STOP / opt-out ---
    if msg in ('STOP', 'QUIT', 'END', 'CANCEL', 'UNSUBSCRIBE'):
        _log_inbound(from_number, message_body, tech)
        if tech:
            tech.sms_opted_in = False
            tech.sms_opted_out_at = datetime.utcnow()
        db.session.commit()
        _reply(
            from_number,
            "SleepyBear LLC: You have been unsubscribed. No further messages will be sent. "
            "Reply START to re-subscribe.",
            tech=tech,
            bypass_opt_in=True,
        )
        return '', 200

    # --- START / opt-in ---
    if msg == 'START':
        _log_inbound(from_number, message_body, tech)
        if tech:
            tech.sms_opted_in = True
            tech.sms_opted_in_at = datetime.utcnow()
        db.session.commit()
        _reply(
            from_number,
            "SleepyBear LLC: You have been re-subscribed and will receive job notifications. "
            "Reply STOP at any time to unsubscribe.",
            tech=tech,
        )
        return '', 200

    # --- HELP ---
    if msg == 'HELP':
        _log_inbound(from_number, message_body, tech)
        db.session.commit()
        _reply(
            from_number,
            "SleepyBear LLC: Reply Y to accept a job, N to decline. "
            "STOP to unsubscribe, START to re-subscribe. "
            "For support contact your dispatcher.",
            tech=tech,
        )
        return '', 200

    # --- Y / YES — accept availability ---
    if msg in ('Y', 'YES'):
        _log_inbound(from_number, message_body, tech)
        if tech:
            assignment = (
                JobAssignment.query
                .filter_by(tech_id=tech.tech_id, status='invited')
                .order_by(JobAssignment.assigned_at.desc())
                .first()
            )
            if assignment:
                assignment.status = 'accepted'
                assignment.availability_response = 'yes'
                assignment.availability_responded_at = datetime.utcnow()
                assignment.responded_at = datetime.utcnow()
                db.session.commit()
                ticket = assignment.job.ticket_number if assignment.job else 'the job'
                _reply(
                    from_number,
                    f"Got it! You've been confirmed for {ticket}. Your dispatcher will follow up.",
                    tech=tech,
                )
            else:
                db.session.commit()
                _reply(from_number, "No pending job request found for your number.", tech=tech)
        else:
            db.session.commit()
            _reply(from_number, "We couldn't match your number to a technician account.", tech=tech)
        return '', 200

    # --- N / NO — decline availability ---
    if msg in ('N', 'NO'):
        _log_inbound(from_number, message_body, tech)
        if tech:
            assignment = (
                JobAssignment.query
                .filter_by(tech_id=tech.tech_id, status='invited')
                .order_by(JobAssignment.assigned_at.desc())
                .first()
            )
            if assignment:
                assignment.status = 'declined'
                assignment.availability_response = 'no'
                assignment.availability_responded_at = datetime.utcnow()
                assignment.responded_at = datetime.utcnow()
                db.session.commit()
                ticket = assignment.job.ticket_number if assignment.job else 'the job'
                _reply(
                    from_number,
                    f"Understood. You've declined {ticket}. Your dispatcher has been notified.",
                    tech=tech,
                )
            else:
                db.session.commit()
                _reply(from_number, "No pending job request found for your number.", tech=tech)
        else:
            db.session.commit()
            _reply(from_number, "We couldn't match your number to a technician account.", tech=tech)
        return '', 200

    # --- Check if this is a delivery receipt (empty body after outbound) ---
    if _is_delivery_receipt(from_number, message_body):
        return '', 200

    # --- Unrecognized message — log it ---
    _log_inbound(from_number, message_body, tech)
    db.session.commit()
    logger.info(f"Unrecognized inbound SMS from {from_number}: {message_body[:80]}")
    return '', 200
