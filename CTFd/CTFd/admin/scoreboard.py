from flask import redirect, render_template, url_for

from CTFd.admin import admin
from CTFd.cache import clear_challenges, clear_standings
from CTFd.models import Awards, Solves, Submissions, Tracking, Unlocks, db
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import admins_only
from CTFd.utils.scores import get_standings, get_user_standings


@admin.route("/admin/scoreboard")
@admins_only
def scoreboard_listing():
    standings = get_standings(admin=True)
    user_standings = get_user_standings(admin=True) if is_teams_mode() else None
    return render_template(
        "admin/scoreboard.html", standings=standings, user_standings=user_standings
    )


@admin.route("/admin/scoreboard/reset", methods=["POST"])
@admins_only
def scoreboard_reset():
    Solves.query.delete()
    Submissions.query.delete()
    Awards.query.delete()
    Unlocks.query.delete()
    Tracking.query.delete()
    db.session.commit()

    clear_standings()
    clear_challenges()

    return redirect(url_for("admin.scoreboard_listing", reset="1"))
