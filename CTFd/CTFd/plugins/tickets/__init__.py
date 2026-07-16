from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import inspect

from CTFd.models import Users, db
from CTFd.plugins import register_admin_plugin_menu_bar
from CTFd.utils import config
from CTFd.utils.decorators import admins_only, authed_only, ratelimit
from CTFd.utils.email import sendmail
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
    # Unread flags drive the notification badges:
    # admin_unread  -> ticket has activity the admins have not seen yet
    # player_unread -> ticket has an admin response/status change the player
    #                  has not seen yet
    admin_unread = db.Column(db.Boolean, nullable=False, default=True)
    player_unread = db.Column(db.Boolean, nullable=False, default=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("Users", foreign_keys=[user_id], lazy="joined")


def notify_admins_by_email(ticket, owner):
    """Best-effort email to all admins when a new ticket is raised."""
    try:
        if not config.can_send_mail():
            return
        admins = Users.query.filter_by(type="admin", banned=False).all()
        subject = f"[Support] New ticket #{ticket.id}: {ticket.subject}"
        text = (
            f"{owner.name} raised a new support ticket.\n\n"
            f"Category: {ticket.category}\n"
            f"Subject: {ticket.subject}\n\n"
            f"{ticket.description}\n\n"
            f"Review it in the admin panel: /admin/tickets"
        )
        for admin in admins:
            try:
                sendmail(addr=admin.email, text=text, subject=subject)
            except Exception:
                pass
    except Exception:
        pass


def notify_player_by_email(ticket):
    """Best-effort email to the ticket owner when an admin responds."""
    try:
        if not config.can_send_mail() or ticket.user is None:
            return
        subject = f"[Support] Your ticket #{ticket.id} has been updated"
        text = (
            f"Your support ticket has been updated.\n\n"
            f"Subject: {ticket.subject}\n"
            f"Status: {ticket.status.replace('_', ' ')}\n"
        )
        if ticket.admin_response:
            text += f"\nTeam response:\n{ticket.admin_response}\n"
        text += "\nView it on the Support page: /tickets"
        sendmail(addr=ticket.user.email, text=text, subject=subject)
    except Exception:
        pass


@tickets.route("/tickets", methods=["GET"])
@authed_only
def listing():
    user = get_current_user()
    user_tickets = (
        SupportTickets.query.filter_by(user_id=user.id)
        .order_by(SupportTickets.created.desc())
        .all()
    )

    # Remember which tickets have fresh admin activity, then mark them seen
    unread_ids = [t.id for t in user_tickets if t.player_unread]
    if unread_ids:
        for t in user_tickets:
            t.player_unread = False
        db.session.commit()

    return render_template(
        "tickets.html",
        tickets=user_tickets,
        unread_ids=unread_ids,
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
        admin_unread=True,
        player_unread=False,
    )
    db.session.add(ticket)
    db.session.commit()

    notify_admins_by_email(ticket, user)

    info_for(
        "tickets.listing",
        f"Your concern has been submitted as ticket #{ticket.id}. "
        "The team will get back to you here.",
    )
    return redirect(url_for("tickets.listing", _anchor="my-tickets"))


@tickets.route("/api/v1/tickets/unread", methods=["GET"])
@authed_only
def unread_count():
    user = get_current_user()
    count = SupportTickets.query.filter_by(
        user_id=user.id, player_unread=True
    ).count()
    return jsonify({"success": True, "data": {"count": count}})


@tickets.route("/api/v1/tickets/admin-unread", methods=["GET"])
@admins_only
def admin_unread_count():
    count = SupportTickets.query.filter_by(admin_unread=True).count()
    return jsonify({"success": True, "data": {"count": count}})


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

    # Remember which tickets are new to the admins, then mark them seen
    new_ids = [t.id for t in all_tickets if t.admin_unread]
    if new_ids:
        for t in all_tickets:
            t.admin_unread = False
        db.session.commit()

    return render_template(
        "tickets/admin.html",
        tickets=all_tickets,
        new_ids=new_ids,
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

    changed = False
    if status in TICKET_STATUSES and status != ticket.status:
        ticket.status = status
        changed = True
    if (response or None) != ticket.admin_response:
        ticket.admin_response = response or None
        changed = True

    if changed:
        ticket.player_unread = True
    ticket.admin_unread = False
    db.session.commit()

    if changed:
        notify_player_by_email(ticket)

    return redirect(
        url_for("tickets.admin_listing", status=request.args.get("status", ""))
    )


def ensure_schema(app):
    """Add notification columns to support_tickets if the table predates them.

    db.create_all() creates missing tables but never alters existing ones,
    so upgrades from the first plugin version are handled here.
    """
    inspector = inspect(db.engine)
    if "support_tickets" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("support_tickets")}
    statements = {
        "admin_unread": (
            "ALTER TABLE support_tickets "
            "ADD COLUMN admin_unread BOOLEAN NOT NULL DEFAULT 1"
        ),
        "player_unread": (
            "ALTER TABLE support_tickets "
            "ADD COLUMN player_unread BOOLEAN NOT NULL DEFAULT 0"
        ),
    }
    for column, statement in statements.items():
        if column not in existing:
            db.session.execute(db.text(statement))
    db.session.commit()


def load(app):
    with app.app_context():
        db.create_all()
        ensure_schema(app)
    app.register_blueprint(tickets)
    register_admin_plugin_menu_bar("Tickets", "/admin/tickets")
