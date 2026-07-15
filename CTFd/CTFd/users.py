import re

from flask import Blueprint, redirect, render_template, request, url_for

from CTFd.models import UserFieldEntries, UserFields, Users, db
from CTFd.utils import config, email, get_config, validators
from CTFd.utils.crypto import verify_password
from CTFd.utils.decorators import authed_only, ratelimit
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)
from CTFd.utils.helpers import error_for, get_errors, get_infos, info_for
from CTFd.utils.user import get_current_user

users = Blueprint("users", __name__)


@users.route("/users")
@check_account_visibility
def listing():
    q = request.args.get("q")
    field = request.args.get("field", "name")
    if field not in ("name", "affiliation", "website"):
        field = "name"

    filters = []
    if q:
        filters.append(getattr(Users, field).like("%{}%".format(q)))

    users = (
        Users.query.filter_by(banned=False, hidden=False)
        .filter(*filters)
        .order_by(Users.id.asc())
        .paginate(per_page=50, error_out=False)
    )

    args = dict(request.args)
    args.pop("page", 1)

    return render_template(
        "users/users.html",
        users=users,
        prev_page=url_for(request.endpoint, page=users.prev_num, **args),
        next_page=url_for(request.endpoint, page=users.next_num, **args),
        q=q,
        field=field,
    )


def get_register_number_field():
    return UserFields.query.filter_by(name="Register Number").first()


def get_register_number(user):
    field = get_register_number_field()
    if field is None:
        return ""
    entry = UserFieldEntries.query.filter_by(
        field_id=field.id, user_id=user.id
    ).first()
    return entry.value if entry else ""


@users.route("/profile")
@users.route("/user")
@authed_only
def private():
    infos = get_infos()
    errors = get_errors()

    user = get_current_user()

    if config.is_scoreboard_frozen():
        infos.append("Scoreboard has been frozen")

    return render_template(
        "users/private.html",
        user=user,
        account=user.account,
        register_number=get_register_number(user),
        infos=infos,
        errors=errors,
    )


@users.route("/profile/update", methods=["POST"])
@authed_only
@ratelimit(method="POST", limit=10, interval=60)
def profile_update():
    user = get_current_user()

    name = request.form.get("name", "").strip()
    email_address = request.form.get("email", "").strip().lower()
    register_number = request.form.get("register_number", "").strip()
    confirm = request.form.get("confirm", "").strip()

    errors = []

    if (
        len(confirm) == 0
        or user.password is None
        or verify_password(plaintext=confirm, ciphertext=user.password) is False
    ):
        errors.append("Your current password is incorrect")

    if len(name) == 0:
        errors.append("Pick a longer user name")
    elif len(name) > 128:
        errors.append("Pick a shorter user name")
    elif validators.validate_email(name) is True:
        errors.append("Your user name cannot be an email address")
    elif name != user.name:
        if bool(get_config("name_changes", default=True)) is False:
            errors.append("Name changes are disabled")
        elif Users.query.filter(Users.name == name, Users.id != user.id).first():
            errors.append("That user name is already taken")

    if validators.validate_email(email_address) is False or len(email_address) > 128:
        errors.append("Please enter a valid email address")
    elif email_address != user.email:
        if Users.query.filter(
            Users.email == email_address, Users.id != user.id
        ).first():
            errors.append("That email has already been used")
        elif (
            email.check_email_is_whitelisted(email_address) is False
            or email.check_email_is_blacklisted(email_address) is True
        ):
            errors.append("Your email address is not from an allowed domain")

    register_number_field = get_register_number_field()
    if re.fullmatch(r"[0-9]{12}", register_number) is None:
        errors.append("Register number must contain exactly 12 digits")
    elif register_number_field and UserFieldEntries.query.filter(
        UserFieldEntries.field_id == register_number_field.id,
        UserFieldEntries.value == register_number,
        UserFieldEntries.user_id != user.id,
    ).first():
        errors.append("That register number has already been used")

    if errors:
        for error in errors:
            error_for("users.private", error)
        return redirect(url_for("users.private"))

    email_changed = email_address != user.email
    user.name = name
    user.email = email_address
    if email_changed and get_config("verify_emails"):
        user.verified = False

    if register_number_field is None:
        register_number_field = UserFields(
            name="Register Number",
            field_type="text",
            description="12-digit institutional register number",
            required=False,
            public=False,
            editable=False,
        )
        db.session.add(register_number_field)
        db.session.flush()

    entry = UserFieldEntries.query.filter_by(
        field_id=register_number_field.id, user_id=user.id
    ).first()
    if entry:
        entry.value = register_number
    else:
        db.session.add(
            UserFieldEntries(
                field_id=register_number_field.id,
                value=register_number,
                user_id=user.id,
            )
        )

    db.session.commit()

    info_for("users.private", "Your profile has been updated")
    return redirect(url_for("users.private"))


@users.route("/users/<int:user_id>")
@check_account_visibility
@check_score_visibility
def public(user_id):
    infos = get_infos()
    errors = get_errors()
    user = Users.query.filter_by(id=user_id, banned=False, hidden=False).first_or_404()

    if config.is_scoreboard_frozen():
        infos.append("Scoreboard has been frozen")

    return render_template(
        "users/public.html", user=user, account=user.account, infos=infos, errors=errors
    )
