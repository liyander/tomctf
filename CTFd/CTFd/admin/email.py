import datetime
import threading

from flask import current_app, jsonify, render_template, request

from CTFd.admin import admin
from CTFd.models import Users
from CTFd.utils.config import can_send_mail
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail

# In-process state for the bulk email background job. This is intentionally a
# module-level global (not the cache) so the running worker and the web
# requests always share the exact same objects within the process. A cache
# backend (filesystem/redis) added latency and made the cancel signal
# unreliable.
_bulk_email_lock = threading.Lock()
_bulk_email_cancel = threading.Event()
_bulk_email_status = {
    "running": False,
    "cancelled": False,
    "total": 0,
    "sent": 0,
    "failed": 0,
    "last_error": None,
    "started": None,
    "finished": None,
}


def _status_snapshot():
    with _bulk_email_lock:
        return dict(_bulk_email_status)


def _send_bulk_email(app, addresses, subject, message):
    with app.app_context():
        for address in addresses:
            # Stop before sending the next message if a cancel was requested
            if _bulk_email_cancel.is_set():
                with _bulk_email_lock:
                    _bulk_email_status["cancelled"] = True
                break

            result, response = sendmail(addr=address, text=message, subject=subject)
            with _bulk_email_lock:
                if result:
                    _bulk_email_status["sent"] += 1
                else:
                    _bulk_email_status["failed"] += 1
                    _bulk_email_status["last_error"] = str(response)

        with _bulk_email_lock:
            _bulk_email_status["running"] = False
            _bulk_email_status["finished"] = datetime.datetime.utcnow().isoformat()


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

        status = _status_snapshot()
        already_running = status.get("running")

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
                "to finish or stop it before starting another."
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

        # Reset state for the new run
        _bulk_email_cancel.clear()
        with _bulk_email_lock:
            _bulk_email_status.update(
                {
                    "running": True,
                    "cancelled": False,
                    "total": len(addresses),
                    "sent": 0,
                    "failed": 0,
                    "last_error": None,
                    "started": datetime.datetime.utcnow().isoformat(),
                    "finished": None,
                }
            )

        # Send in a background thread so the request returns immediately instead
        # of blocking the browser while every message is delivered.
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_send_bulk_email,
            args=(app, addresses, subject, message),
            daemon=True,
        )
        thread.start()

        return render_template(
            "admin/email.html",
            mail_configured=mail_configured,
            recipient_counts=recipient_counts,
            status=_status_snapshot(),
            just_started=True,
        )

    return render_template(
        "admin/email.html",
        mail_configured=mail_configured,
        recipient_counts=recipient_counts,
        status=_status_snapshot(),
    )


@admin.route("/admin/email/status", methods=["GET"])
@admins_only
def email_status():
    return jsonify(_status_snapshot())


@admin.route("/admin/email/stop", methods=["POST"])
@admins_only
def email_stop():
    _bulk_email_cancel.set()
    return jsonify({"success": True, "status": _status_snapshot()})
