import datetime
import threading

from flask import current_app, render_template, request

from CTFd.admin import admin
from CTFd.cache import cache
from CTFd.models import Users
from CTFd.utils.config import can_send_mail
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail

BULK_EMAIL_STATUS_KEY = "bulk_email_status"


def _get_bulk_email_status():
    return cache.get(BULK_EMAIL_STATUS_KEY)


def _set_bulk_email_status(status):
    # Keep status around for an hour so the admin can refresh and read the result
    cache.set(BULK_EMAIL_STATUS_KEY, status, timeout=3600)


def _send_bulk_email(app, addresses, subject, message):
    with app.app_context():
        status = {
            "running": True,
            "total": len(addresses),
            "sent": 0,
            "failed": 0,
            "last_error": None,
            "started": datetime.datetime.utcnow().isoformat(),
            "finished": None,
        }
        _set_bulk_email_status(status)

        for address in addresses:
            result, response = sendmail(addr=address, text=message, subject=subject)
            if result:
                status["sent"] += 1
            else:
                status["failed"] += 1
                status["last_error"] = str(response)
            _set_bulk_email_status(status)

        status["running"] = False
        status["finished"] = datetime.datetime.utcnow().isoformat()
        _set_bulk_email_status(status)


@admin.route("/admin/email", methods=["GET", "POST"])
@admins_only
def email():
    mail_configured = can_send_mail()

    # Count of users we could email, for display on the compose form
    recipient_counts = {
        "all": Users.query.filter_by(banned=False).count(),
        "verified": Users.query.filter_by(banned=False, verified=True).count(),
        "unverified": Users.query.filter_by(banned=False, verified=False).count(),
    }

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        recipients = request.form.get("recipients", "all")

        status = _get_bulk_email_status()
        already_running = bool(status and status.get("running"))

        errors = []
        if mail_configured is False:
            errors.append(
                "No mail server is configured. Set one up in Config > Email "
                "(for example a free Gmail SMTP account) before sending email."
            )
        if not subject:
            errors.append("Please provide an email subject.")
        if not message:
            errors.append("Please provide an email message.")
        if recipients not in recipient_counts:
            errors.append("Please choose a valid group of recipients.")
        if already_running:
            errors.append(
                "A bulk email send is already in progress. Please wait for it "
                "to finish before starting another."
            )

        if errors:
            return render_template(
                "admin/email.html",
                mail_configured=mail_configured,
                recipient_counts=recipient_counts,
                errors=errors,
                subject=subject,
                message=message,
                recipients=recipients,
                status=status,
            )

        # Collect the recipient addresses now (inside the request context)
        query = Users.query.filter_by(banned=False)
        if recipients == "verified":
            query = query.filter_by(verified=True)
        elif recipients == "unverified":
            query = query.filter_by(verified=False)
        addresses = [user.email for user in query.all() if user.email]

        # Send in a background thread so the request returns immediately instead
        # of blocking the browser while every message is delivered.
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_send_bulk_email,
            args=(app, addresses, subject, message),
            daemon=True,
        )
        thread.start()

        started_status = {
            "running": True,
            "total": len(addresses),
            "sent": 0,
            "failed": 0,
            "last_error": None,
            "started": datetime.datetime.utcnow().isoformat(),
            "finished": None,
        }
        return render_template(
            "admin/email.html",
            mail_configured=mail_configured,
            recipient_counts=recipient_counts,
            status=started_status,
            just_started=True,
        )

    return render_template(
        "admin/email.html",
        mail_configured=mail_configured,
        recipient_counts=recipient_counts,
        status=_get_bulk_email_status(),
    )
