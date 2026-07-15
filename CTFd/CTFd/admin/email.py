from flask import render_template, request

from CTFd.admin import admin
from CTFd.models import Users
from CTFd.utils.config import can_send_mail
from CTFd.utils.decorators import admins_only
from CTFd.utils.email import sendmail


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

        if errors:
            return render_template(
                "admin/email.html",
                mail_configured=mail_configured,
                recipient_counts=recipient_counts,
                errors=errors,
                subject=subject,
                message=message,
                recipients=recipients,
            )

        query = Users.query.filter_by(banned=False)
        if recipients == "verified":
            query = query.filter_by(verified=True)
        elif recipients == "unverified":
            query = query.filter_by(verified=False)

        sent = 0
        failed = 0
        failed_addresses = []
        for user in query.all():
            if not user.email:
                continue
            result, _ = sendmail(addr=user.email, text=message, subject=subject)
            if result:
                sent += 1
            else:
                failed += 1
                if len(failed_addresses) < 20:
                    failed_addresses.append(user.email)

        return render_template(
            "admin/email.html",
            mail_configured=mail_configured,
            recipient_counts=recipient_counts,
            sent=sent,
            failed=failed,
            failed_addresses=failed_addresses,
        )

    return render_template(
        "admin/email.html",
        mail_configured=mail_configured,
        recipient_counts=recipient_counts,
    )
