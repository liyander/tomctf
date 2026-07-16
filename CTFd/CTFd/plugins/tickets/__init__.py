from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for

from CTFd.models import db
from CTFd.plugins import register_admin_plugin_menu_bar
from CTFd.utils.decorators import admins_only, authed_only, ratelimit
from CTFd.utils.helpers import error_for, get_errors, get_infos, info_for
from CTFd.utils.user import get_current_user

tickets = Blueprint("tickets", __name__, template_folder="templates")

TICKET_CATEGORIES = [
    "Technical Issue",
    "Challenge Query",
    "Account & Profile",
    "Scoring & Submissions",
    "Other",
]

TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"]

SUBJECT_MAX_LENGTH = 256
DESCRIPTION_MAX_LENGTH = 5000


class SupportTickets(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category = db.Column(db.String(64), nullable=False)
    subject = db.Column(db.String(SUBJECT_MAX_LENGTH), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="open")
    admin_response = db.Column(db.Text, nullable=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("Users", foreign_keys=[user_id], lazy="joined")


@tickets.route("/tickets", methods=["GET"])
@authed_only
def listing():
    user = get_current_user()
    user_tickets = (
        SupportTickets.query.filter_by(user_id=user.id)
        .order_by(SupportTickets.created.desc())
        .all()
    )
    return render_template(
        "tickets.html",
        tickets=user_tickets,
        categories=TICKET_CATEGORIES,
        infos=get_infos(),
        errors=get_errors(),
    )


@tickets.route("/tickets/new", methods=["POST"])
@authed_only
@ratelimit(method="POST", limit=10, interval=60)
def create():
    user = get_current_user()

    subject = request.form.get("subject", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()

    errors = []
    if len(subject) == 0:
        errors.append("Please provide a subject for your concern")
    elif len(subject) > SUBJECT_MAX_LENGTH:
        errors.append("Please provide a shorter subject")
    if category not in TICKET_CATEGORIES:
        errors.append("Please pick a valid category")
    if len(description) == 0:
        errors.append("Please describe your concern")
    elif len(description) > DESCRIPTION_MAX_LENGTH:
        errors.append(
            f"Please keep the description under {DESCRIPTION_MAX_LENGTH} characters"
        )

    if errors:
        for error in errors:
            error_for("tickets.listing", error)
        return redirect(url_for("tickets.listing"))

    ticket = SupportTickets(
        user_id=user.id,
        category=category,
        subject=subject,
        description=description,
    )
    db.session.add(ticket)
    db.session.commit()

    info_for(
        "tickets.listing",
        f"Your concern has been submitted as ticket #{ticket.id}. "
        "The team will get back to you here.",
    )
    return redirect(url_for("tickets.listing", _anchor="my-tickets"))


@tickets.route("/admin/tickets", methods=["GET"])
@admins_only
def admin_listing():
    status = request.args.get("status", "")
    query = SupportTickets.query
    if status in TICKET_STATUSES:
        query = query.filter_by(status=status)
    all_tickets = query.order_by(SupportTickets.created.desc()).all()

    counts = {"": SupportTickets.query.count()}
    for s in TICKET_STATUSES:
        counts[s] = SupportTickets.query.filter_by(status=s).count()

    return render_template(
        "tickets/admin.html",
        tickets=all_tickets,
        statuses=TICKET_STATUSES,
        active_status=status,
        counts=counts,
    )


@tickets.route("/admin/tickets/<int:ticket_id>", methods=["POST"])
@admins_only
def admin_update(ticket_id):
    ticket = SupportTickets.query.filter_by(id=ticket_id).first_or_404()

    status = request.form.get("status", "").strip()
    response = request.form.get("admin_response", "").strip()

    if status in TICKET_STATUSES:
        ticket.status = status
    ticket.admin_response = response or None
    db.session.commit()

    return redirect(
        url_for("tickets.admin_listing", status=request.args.get("status", ""))
    )


def load(app):
    with app.app_context():
        db.create_all()
    app.register_blueprint(tickets)
    register_admin_plugin_menu_bar("Tickets", "/admin/tickets")
