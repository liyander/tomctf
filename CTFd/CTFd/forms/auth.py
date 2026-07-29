from flask_babel import lazy_gettext as _l
from wtforms import PasswordField, StringField
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.forms.users import (
    attach_custom_user_fields,
    attach_registration_code_field,
    attach_user_bracket_field,
    build_custom_user_fields,
    build_registration_code_field,
    build_user_bracket_field,
)
from CTFd.utils import get_config


def RegistrationForm(*args, **kwargs):
    password_min_length = int(get_config("password_min_length", default=0))
    password_description = _l("Password used to log into your account")
    if password_min_length:
        password_description += _l(
            f" (Must be at least {password_min_length} characters)"
        )

    class _RegistrationForm(BaseForm):
        name = StringField(
            _l("User Name"),
            description="Your username on the site",
            validators=[InputRequired()],
            render_kw={"autofocus": True},
        )
        email = EmailField(
            _l("Email"),
            description=_l(
                "Use your college email (@srishakthi.ac.in or @siet.ac.in). "
                "Never shown to the public."
            ),
            validators=[InputRequired()],
        )
        register_number = StringField(
            _l("Register Number"),
            description=_l(
                "Your 12-digit institutional register number starting with 7140"
            ),
            validators=[InputRequired()],
            render_kw={
                "inputmode": "numeric",
                "pattern": "7140[0-9]{8}",
                "minlength": "12",
                "maxlength": "12",
                "autocomplete": "off",
                "title": "12 digits starting with 7140, e.g. 714023149048",
            },
        )
        password = PasswordField(
            _l("Password"),
            description=password_description,
            validators=[InputRequired()],
        )
        submit = SubmitField(_l("Submit"))

        @property
        def extra(self):
            return (
                build_custom_user_fields(
                    self,
                    include_entries=False,
                    blacklisted_items=("register number",),
                )
                + build_registration_code_field(self)
                + build_user_bracket_field(self)
            )

    attach_custom_user_fields(_RegistrationForm)
    attach_registration_code_field(_RegistrationForm)
    attach_user_bracket_field(_RegistrationForm)

    return _RegistrationForm(*args, **kwargs)


class LoginForm(BaseForm):
    name = StringField(
        _l("Register Number or Email"),
        validators=[InputRequired()],
        render_kw={
            "autofocus": True,
            "inputmode": "text",
            "autocomplete": "username",
            "title": "Enter your 12-digit register number or email address",
        },
    )
    password = PasswordField(_l("Password"), validators=[InputRequired()])
    submit = SubmitField(_l("Submit"))


class ConfirmForm(BaseForm):
    submit = SubmitField(_l("Send Confirmation Email"))


class ResetPasswordRequestForm(BaseForm):
    email = EmailField(
        _l("Email"), validators=[InputRequired()], render_kw={"autofocus": True}
    )
    submit = SubmitField(_l("Submit"))


class ResetPasswordForm(BaseForm):
    password = PasswordField(
        _l("Password"), validators=[InputRequired()], render_kw={"autofocus": True}
    )
    submit = SubmitField(_l("Submit"))
