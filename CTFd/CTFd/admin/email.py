import datetime
import threading

from flask import current_app, jsonify, render_template, request

from CTFd.admin import admin
from CTFd.models import Users
from CTFd.utils import get_config
from CTFd.utils.config import can_send_mail
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail
from CTFd.utils.email.html_templates import (
    EMAIL_TEMPLATES,
    get_template_html,
    render_email_html,
)

# In-process state for the bulk email background job. This is intentionally a
# module-level global (not the cache) so the running worker and the web
# requests always share the exact same objects within the process.
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

DEFAULT_TEXT_FALLBACK = "Please view this email in an HTML-capable email client."


def _status_snapshot():
    with _bulk_email_lock:
        return dict(_bulk_email_status)


def _send_bulk_email(app, recipients, subject, message, html_template):
    with app.app_context():
        ctf_name = get_config("ctf_name")
        for recipient in recipients:
            # Stop before sending the next message if a cancel was requested
            if _bulk_email_cancel.is_set():
                with _bulk_email_lock:
                    _bulk_email_status["cancelled"] = True
                break

            if html_template:
                body_html = render_email_html(
                    html_template,
                    ctf_name=ctf_name,
                    subject=subject,
                    message=message,
                    name=recipient["name"],
                    email=recipient["email"],
                )
                text = message or DEFAULT_TEXT_FALLBACK
                result, response = sendmail(
                    addr=recipient["email"],
                    text=text,
                    subject=subject,
                    html=body_html,
                )
            else:
                result, response = sendmail(
                    addr=recipient["email"], text=message, subject=subject
                )

            with _bulk_email_lock:
                if result:
                    _bulk_email_status["sent"] += 1
                else:
                    _bulk_email_status["failed"] += 1
                    _bulk_email_status["last_error"] = str(response)

        with _bulk_email_lock:
            _bulk_email_status["running"] = False
            _bulk_email_status["finished"] = datetime.datetime.utcnow().isoformat()


def _templates_for_template_context():
    return {
        key: {"name": value["name"], "description": value["description"]}
        for key, value in EMAIL_TEMPLATES.items()
    }


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

    templates_meta = _templates_for_template_context()
    # Full template HTML embedded for the editor to load client-side
    templates_html = {key: value["html"] for key, value in EMAIL_TEMPLATES.items()}

    def render(**extra):
        context = dict(
            mail_configured=mail_configured,
            recipient_counts=recipient_counts,
            templates_meta=templates_meta,
            templates_html=templates_html,
        )
        context.update(extra)
        return render_template("admin/email.html", **context)

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        recipients = request.form.get("recipients", "all")
        email_format = request.form.get("format", "plain")
        html_content = request.form.get("html", "")

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
        if email_format == "html":
            if not html_content.strip():
                errors.append("Please provide HTML content (pick a template or write your own).")
        else:
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
            return render(
                errors=errors,
                subject=subject,
                message=message,
                recipients=recipients,
                email_format=email_format,
                html_content=html_content,
                status=status,
            )

        # Collect the recipients now (inside the request context)
        query = Users.query.filter_by(banned=False)
        if recipients == "verified":
            query = query.filter_by(verified=True)
        elif recipients == "unverified":
            query = query.filter_by(verified=False)
        recipient_list = [
            {"name": user.name, "email": user.email}
            for user in query.all()
            if user.email
        ]

        html_template = html_content if email_format == "html" else None

        # Reset state for the new run
        _bulk_email_cancel.clear()
        with _bulk_email_lock:
            _bulk_email_status.update(
                {
                    "running": True,
                    "cancelled": False,
                    "total": len(recipient_list),
                    "sent": 0,
                    "failed": 0,
                    "last_error": None,
                    "started": datetime.datetime.utcnow().isoformat(),
                    "finished": None,
                }
            )

        # Send in a background thread so the request returns immediately
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_send_bulk_email,
            args=(app, recipient_list, subject, message, html_template),
            daemon=True,
        )
        thread.start()

        return render(status=_status_snapshot(), just_started=True)

    return render(status=_status_snapshot())


@admin.route("/admin/email/preview", methods=["POST"])
@admins_only
def email_preview():
    data = request.get_json(silent=True) or {}
    html_content = data.get("html", "")
    subject = data.get("subject", "")
    message = data.get("message", "")
    rendered = render_email_html(
        html_content,
        ctf_name=get_config("ctf_name") or "Your CTF",
        subject=subject or "Subject preview",
        message=message,
        name="there",
        email="player@example.com",
    )
    return jsonify({"html": rendered})


@admin.route("/admin/email/template/<template_id>", methods=["GET"])
@admins_only
def email_template(template_id):
    html = get_template_html(template_id)
    if html is None:
        return jsonify({"success": False, "error": "Unknown template"}), 404
    return jsonify({"success": True, "html": html})


@admin.route("/admin/email/status", methods=["GET"])
@admins_only
def email_status():
    return jsonify(_status_snapshot())


@admin.route("/admin/email/stop", methods=["POST"])
@admins_only
def email_stop():
    _bulk_email_cancel.set()
    return jsonify({"success": True, "status": _status_snapshot()})
