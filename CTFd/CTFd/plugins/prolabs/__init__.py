import json
import re
from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from CTFd.cache import clear_standings
from CTFd.models import db
from CTFd.models import Awards
from CTFd.plugins import register_admin_plugin_menu_bar
from CTFd.utils.config.pages import build_markdown
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.dates import ctftime
from CTFd.utils.user import (
    get_current_team,
    get_current_user,
    get_ip,
    get_team_score,
    get_user_score,
    is_admin,
)


prolabs = Blueprint("prolabs", __name__, template_folder="templates")

OS_CHOICES = {
    "windows": "Windows",
    "linux": "Linux",
    "freebsd": "FreeBSD",
}

LEVELS_CONFIG_KEY = "prolab_levels"

DEFAULT_LEVELS = [
    {"name": "Recruit", "min_score": 0},
    {"name": "Operator", "min_score": 200},
    {"name": "Specialist", "min_score": 500},
    {"name": "Elite", "min_score": 900},
]

DEFAULT_CHANGELOG_TEXT = (
    "## Prolab Changelog\n"
    "Last Updated: -\n\n"
    "There seems to be no changes made to this Pro Lab yet.\n"
    "Keep your eyes peeled to this tab! When the Pro Lab gets updated, we list out the changes made here."
)

DEFAULT_PRO_LAB_INFO_TEXT = (
    "## Synopsis\n"
    "You are tasked with performing a red team engagement on Mythical Inc. The company does not allow data leaving the internal network, so a c2 server has been set up internally and an employee executed a payload in order to simulate a successful social engineering attack.\n\n"
    "## What is Mythical\n"
    "Mythical is a small active directory scenario in which you start with an already running Mythic C2 beacon on an internal system. It is designed to practice operating through a C2 framework in a modern, challenging windows environment.\n\n"
    "## Who is Mythical for?\n"
    "Mythical is designed for penetration testers and red teamers in search of a quick and challenging lab that has c2 infrastructure already set up in order to practice c2 operations.\n\n"
    "## Skills / Knowledge\n"
    "- A grasp of penetration testing methodologies\n"
    "- Basic knowledge of Active Directory\n"
    "- C2 fundamentals\n\n"
    "## Attitude / Mentality\n"
    "- A willingness to undertake a significant amount of research\n"
    "- Patience and perseverance\n"
    "- Thinking outside the box\n\n"
    "## What will you gain?\n"
    "Upon completion of this lab, players will have a good understanding of Active Directory attacks and be well versed in the following areas:\n\n"
    "- Enumeration\n"
    "- Active Directory enumeration and attacks\n"
    "- Active Directory Certificate Services\n"
    "- Lateral movement\n"
    "- Local privilege escalation\n"
    "- Situational awareness\n"
    "- MSSQL attacks\n"
    "- C2 Operations"
)


class ProLabSubmission(db.Model):
    __tablename__ = "prolab_submissions"
    __table_args__ = (
        db.UniqueConstraint("lab_slug", "flag_id", "user_id"),
        db.UniqueConstraint("lab_slug", "flag_id", "team_id"),
        {},
    )

    id = db.Column(db.Integer, primary_key=True)
    lab_slug = db.Column(db.String(128), index=True, nullable=False)
    flag_id = db.Column(db.String(128), index=True, nullable=False)
    provided = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="incorrect")
    ip = db.Column(db.String(46), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


DEFAULT_PROLABS = [
    {
        "slug": "mythical",
        "title": "Mythical",
        "category": "Mini Pro Labs",
        "difficulty": "Advanced",
        "is_free": True,
        "cover_image": "https://images.unsplash.com/photo-1534088568595-a066f410bcda?auto=format&fit=crop&w=1400&q=80",
        "logo_image": "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?auto=format&fit=crop&w=300&q=80",
        "rating": 5,
        "rating_count": 37,
        "entry_ip": "10.13.38.32",
        "introduction": "You are tasked with performing a red team engagement on Mythical Inc. Operate through an active C2 workflow and complete objective-driven milestones.",
        "topics": [
            "Enumeration",
            "Active Directory attacks",
            "AD Certificate Services",
            "Lateral movement",
            "Privilege escalation",
            "Situational awareness",
            "MSSQL attacks",
            "C2 operations",
        ],
        "progress": 33.33,
        "machines": [
            {
                "name": "MYTHICAL-FILE",
                "os": "Linux",
                "flags": {
                    "user": "",
                    "admin": "",
                },
            },
            {
                "name": "MYTHICAL-DC01",
                "os": "Windows",
                "flags": {
                    "user": "",
                    "admin": "",
                },
            },
            {
                "name": "MYTHICAL-DC02",
                "os": "Windows",
                "flags": {
                    "user": "",
                    "admin": "",
                },
            },
        ],
        "badges": [
            {
                "name": "Mythical Master",
                "description": "Completed Mythical Mini Pro Lab",
            }
        ],
        "creator": "xct",
    }
]


def _slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _normalize_os(value):
    os_name = (value or "").strip().lower()
    return OS_CHOICES.get(os_name, "Linux")


def _safe_points(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_level_name(value):
    return (value or "").strip()


def _safe_int(value, default=0):
    """Convert value to int safely, handling strings and integers."""
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str):
        try:
            return max(0, int(value.strip()))
        except (ValueError, AttributeError):
            return default
    return default


def _normalize_levels(levels):
    if not isinstance(levels, list):
        levels = []

    normalized = []
    seen_names = set()
    for item in levels:
        if not isinstance(item, dict):
            continue
        name = _normalize_level_name(item.get("name"))
        if not name or name in seen_names:
            continue
        normalized.append(
            {
                "name": name,
                "min_score": max(0, _safe_int(item.get("min_score"), 0)),
            }
        )
        seen_names.add(name)

    if not normalized:
        normalized = [dict(level) for level in DEFAULT_LEVELS]

    normalized.sort(key=lambda level: level["min_score"])
    return normalized


def get_level_rules():
    configured = get_config(LEVELS_CONFIG_KEY)
    if not configured:
        return _normalize_levels(DEFAULT_LEVELS)

    try:
        parsed = json.loads(configured)
    except Exception:
        parsed = DEFAULT_LEVELS

    return _normalize_levels(parsed)


def get_level_for_score(score, level_rules=None):
    rules = level_rules or get_level_rules()
    normalized_score = max(0, _safe_int(score, 0))

    current = rules[0]
    for rule in rules:
        if normalized_score >= rule["min_score"]:
            current = rule
        else:
            break
    return current


def get_level_name_for_score(score, level_rules=None):
    return get_level_for_score(score, level_rules).get("name", "Recruit")


def _find_level_rule(level_name, level_rules=None):
    if not level_name:
        return None
    rules = level_rules or get_level_rules()
    for rule in rules:
        if rule["name"] == level_name:
            return rule
    return None


def _normalize_flag_slot(raw_slot, fallback_value="", fallback_points=0):
    if isinstance(raw_slot, dict):
        flag_value = (raw_slot.get("value") or raw_slot.get("flag") or "").strip()
        points = _safe_points(raw_slot.get("points", fallback_points))
    else:
        flag_value = (raw_slot or fallback_value or "").strip()
        points = _safe_points(fallback_points)

    return {
        "value": flag_value,
        "points": points,
    }


def _normalize_machine(machine, fallback_index):
    name = (machine.get("name") or f"MACHINE-{fallback_index + 1}").strip()
    os_name = _normalize_os(machine.get("os"))

    flags = machine.get("flags") or {}
    if isinstance(flags, str):
        # Backward compatibility for older comma-separated format
        split_flags = [v.strip() for v in flags.split(",") if v.strip()]
        flags = {
            "user": split_flags[0] if len(split_flags) > 0 else "",
            "admin": split_flags[1] if len(split_flags) > 1 else "",
        }

    user_slot = _normalize_flag_slot(
        flags.get("user"),
        fallback_value=machine.get("user_flag", ""),
        fallback_points=machine.get("user_points", 0),
    )
    admin_slot = _normalize_flag_slot(
        flags.get("admin"),
        fallback_value=machine.get("admin_flag", ""),
        fallback_points=machine.get("admin_points", 0),
    )

    return {
        "name": name,
        "os": os_name,
        "flags": {
            "user": user_slot,
            "admin": admin_slot,
        },
    }


def _resolve_machine_flag_config(lab, flag_id):
    for machine in lab.get("machines", []):
        machine_slug = _slugify(machine.get("name") or "")
        user_slot = machine.get("flags", {}).get("user", {})
        admin_slot = machine.get("flags", {}).get("admin", {})

        if flag_id == f"{machine_slug}-user":
            return {
                "machine": machine.get("name", "Unknown Machine"),
                "role": "user",
                "value": user_slot.get("value", ""),
                "points": _safe_points(user_slot.get("points", 0)),
            }
        if flag_id == f"{machine_slug}-admin":
            return {
                "machine": machine.get("name", "Unknown Machine"),
                "role": "admin",
                "value": admin_slot.get("value", ""),
                "points": _safe_points(admin_slot.get("points", 0)),
            }
    return None


def _get_current_account_scope():
    user = get_current_user()
    team = get_current_team()
    if team is not None:
        return user, team, "team"
    return user, None, "user"


def _get_current_account_score():
    user, team, scope = _get_current_account_scope()
    if user is None:
        return 0

    if scope == "team" and team is not None:
        return max(0, _safe_int(get_team_score(team.id), 0))
    return max(0, _safe_int(get_user_score(user.id), 0))


def _is_lab_locked_for_current_account(lab, level_rules=None):
    required_score = _safe_int(lab.get("required_level"), 0)
    if required_score <= 0:
        return False

    if is_admin():
        return False

    current_score = _get_current_account_score()
    return current_score < required_score


def _get_solved_flag_ids_for_lab(lab_slug):
    user, team, scope = _get_current_account_scope()
    if user is None:
        return set()

    query = ProLabSubmission.query.filter_by(lab_slug=lab_slug, status="correct")
    if scope == "team":
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)

    return {row.flag_id for row in query.all()}


def _build_display_flags(raw_flags, machines):
    display_flags = []

    # Prefer machine-bound user/admin flag slots
    for index, machine in enumerate(machines):
        machine_slug = _slugify(machine.get("name") or f"machine-{index + 1}")
        user_slot = machine.get("flags", {}).get("user", {})
        admin_slot = machine.get("flags", {}).get("admin", {})

        display_flags.append(
            {
                "id": f"{machine_slug}-user",
                "name": f"{machine['name']} - User",
                "status": "Pending",
                "machine": machine["name"],
                "role": "user",
                "points": _safe_points(user_slot.get("points", 0)),
            }
        )
        display_flags.append(
            {
                "id": f"{machine_slug}-admin",
                "name": f"{machine['name']} - Admin",
                "status": "Pending",
                "machine": machine["name"],
                "role": "admin",
                "points": _safe_points(admin_slot.get("points", 0)),
            }
        )

    if display_flags:
        return display_flags

    # Fallback for legacy flags list
    for index, flag in enumerate(raw_flags or []):
        name = (flag.get("name") or f"Flag {index + 1}").strip()
        status = (flag.get("status") or "Pending").strip()
        display_flags.append(
            {
                "id": _slugify(name) or f"flag-{index + 1}",
                "name": name,
                "status": status,
                "points": _safe_points(flag.get("points", 0)),
            }
        )

    return display_flags


def _normalize_lab(raw, fallback_index, level_rules=None):
    title = (raw.get("title") or f"Lab {fallback_index + 1}").strip()
    slug = _slugify(raw.get("slug") or title) or f"lab-{fallback_index + 1}"

    category = (raw.get("category") or "Pro Labs").strip()
    difficulty = (raw.get("difficulty") or "Intermediate").strip()
    is_free = bool(raw.get("is_free"))
    cover_image = (raw.get("cover_image") or "").strip()
    logo_image = (raw.get("logo_image") or "").strip()
    entry_ip = (raw.get("entry_ip") or "").strip()
    introduction = (raw.get("introduction") or "").strip()
    introduction_html = build_markdown(introduction, sanitize=True)
    pro_lab_info = (raw.get("pro_lab_info") or "").strip() or DEFAULT_PRO_LAB_INFO_TEXT
    pro_lab_info_html = build_markdown(pro_lab_info, sanitize=True)
    changelog = (raw.get("changelog") or "").strip() or DEFAULT_CHANGELOG_TEXT
    changelog_html = build_markdown(changelog, sanitize=True)
    creator = (raw.get("creator") or "Unknown").strip()
    required_level = _safe_int(raw.get("required_level", 0), default=0)

    machines = raw.get("machines") or []
    if isinstance(machines, str):
        try:
            parsed_machines = json.loads(machines)
            if isinstance(parsed_machines, list):
                machines = parsed_machines
            else:
                raise ValueError("Expected list")
        except Exception:
            machines = [
                {"name": m.strip(), "os": "Unknown", "flags": {"user": "", "admin": ""}}
                for m in machines.split(",")
                if m.strip()
            ]

    normalized_machines = []
    for index, machine in enumerate(machines):
        if isinstance(machine, dict):
            normalized_machines.append(_normalize_machine(machine, index))

    flags = raw.get("flags") or []
    if isinstance(flags, str):
        flags = [
            {"name": f.strip(), "status": "Pending"}
            for f in flags.split(",")
            if f.strip()
        ]

    topics = raw.get("topics") or []
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(",") if t.strip()]

    badges = raw.get("badges") or []
    if isinstance(badges, str):
        badges = [
            {"name": b.strip(), "description": ""}
            for b in badges.split(",")
            if b.strip()
        ]

    rating = raw.get("rating", 5)
    rating_count = raw.get("rating_count", 0)
    progress = raw.get("progress", 0)

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 5

    try:
        rating_count = int(rating_count)
    except (TypeError, ValueError):
        rating_count = 0

    try:
        progress = float(progress)
    except (TypeError, ValueError):
        progress = 0

    display_flags = _build_display_flags(flags, normalized_machines)

    return {
        "slug": slug,
        "title": title,
        "category": category,
        "difficulty": difficulty,
        "is_free": is_free,
        "cover_image": cover_image,
        "logo_image": logo_image,
        "rating": rating,
        "rating_count": rating_count,
        "entry_ip": entry_ip,
        "introduction": introduction,
        "introduction_html": introduction_html,
        "pro_lab_info": pro_lab_info,
        "pro_lab_info_html": pro_lab_info_html,
        "changelog": changelog,
        "changelog_html": changelog_html,
        "topics": topics,
        "progress": max(0, min(progress, 100)),
        "flags": display_flags,
        "machines": normalized_machines,
        "badges": badges,
        "creator": creator,
        "required_level": required_level,
    }


def get_prolabs():
    level_rules = get_level_rules()
    configured = get_config("pro_red_team_labs")
    if not configured:
        return [
            _normalize_lab(item, index, level_rules=level_rules)
            for index, item in enumerate(DEFAULT_PROLABS)
        ]

    try:
        data = json.loads(configured)
        if not isinstance(data, list):
            raise ValueError("Expected a list")
    except Exception:
        data = DEFAULT_PROLABS

    labs = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            labs.append(_normalize_lab(item, index, level_rules=level_rules))

    if not labs:
        labs = [
            _normalize_lab(item, index, level_rules=level_rules)
            for index, item in enumerate(DEFAULT_PROLABS)
        ]
    return labs


@prolabs.route("/pro-red-team-labs", methods=["GET"])
def prolab_listing():
    labs = get_prolabs()
    level_rules = get_level_rules()

    for lab in labs:
        lab["is_locked"] = _is_lab_locked_for_current_account(lab, level_rules=level_rules)

    return render_template("prolabs/list.html", labs=labs)


@prolabs.route("/pro-red-team-labs/<slug>", methods=["GET"])
def prolab_detail(slug):
    labs = get_prolabs()
    lab = next((item for item in labs if item["slug"] == slug), None)
    if not lab:
        abort(404)

    level_rules = get_level_rules()
    if _is_lab_locked_for_current_account(lab, level_rules=level_rules):
        required_score = _safe_int(lab.get("required_level"), 0)
        current_score = _get_current_account_score()
        level_name = get_level_name_for_score(current_score, level_rules)
        return (
            render_template(
                "errors/403.html",
                error=f"You need {required_score}+ points to access this Pro Lab. Your current score: {current_score} points ({level_name}).",
            ),
            403,
        )

    solved_flag_ids = _get_solved_flag_ids_for_lab(slug)
    for flag in lab.get("flags", []):
        if flag.get("id") in solved_flag_ids:
            flag["status"] = "Completed"

    return render_template("prolabs/detail.html", lab=lab)


@prolabs.route("/api/v1/prolabs/<slug>/submit", methods=["POST"])
@authed_only
def prolab_submit_flag(slug):
    request_data = request.form or request.get_json(silent=True) or {}
    flag_id = (request_data.get("flag_id") or "").strip()
    submission = (request_data.get("submission") or "").strip()

    if not flag_id or not submission:
        return {
            "success": True,
            "data": {"status": "incorrect", "message": "Missing flag id or submission"},
        }

    labs = get_prolabs()
    lab = next((item for item in labs if item["slug"] == slug), None)
    if not lab:
        return {
            "success": False,
            "errors": {"message": "Lab not found"},
        }, 404

    level_rules = get_level_rules()
    if _is_lab_locked_for_current_account(lab, level_rules=level_rules):
        required_score = _safe_int(lab.get("required_level"), 0)
        current_score = _get_current_account_score()
        return {
            "success": False,
            "errors": {
                "message": f"You need {required_score}+ points to access this Pro Lab. Your current score: {current_score} points."
            },
        }, 403

    expected_flag = _resolve_machine_flag_config(lab, flag_id)
    if not expected_flag:
        return {
            "success": True,
            "data": {"status": "incorrect", "message": "Unknown flag target"},
        }

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {
            "success": False,
            "errors": {"message": "Authentication required"},
        }, 403

    if not (ctftime() or is_admin()):
        return {
            "success": True,
            "data": {"status": "incorrect", "message": "Submissions are closed"},
        }, 403

    scoped_query = ProLabSubmission.query.filter_by(lab_slug=slug, flag_id=flag_id)
    if scope == "team":
        scoped_query = scoped_query.filter_by(team_id=team.id)
    else:
        scoped_query = scoped_query.filter_by(user_id=user.id)

    existing_row = scoped_query.first()
    if existing_row is not None and existing_row.status == "correct":
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this",
                "first_blood": False,
            },
        }

    is_correct = submission == expected_flag.get("value", "")
    awarded_points = _safe_points(expected_flag.get("points", 0)) if is_correct else 0

    if existing_row is None:
        row = ProLabSubmission(
            lab_slug=slug,
            flag_id=flag_id,
            provided=submission,
            status="correct" if is_correct else "incorrect",
            ip=get_ip(req=request),
            user_id=user.id,
            team_id=team.id if team else None,
        )
        db.session.add(row)
    else:
        existing_row.provided = submission
        existing_row.status = "correct" if is_correct else "incorrect"
        existing_row.ip = get_ip(req=request)
        existing_row.user_id = user.id
        existing_row.team_id = team.id if team else None
        existing_row.date = datetime.utcnow()

    if is_correct and awarded_points > 0:
        award_name = f"{lab['title']} - {expected_flag['machine']} {expected_flag['role'].title()}"
        award = Awards(
            user_id=user.id,
            team_id=team.id if team else None,
            name=award_name[:80],
            description=f"Solved {expected_flag['machine']} {expected_flag['role']} flag in {lab['title']}",
            value=awarded_points,
            category="Pro Labs",
            icon="fas fa-flag-checkered",
        )
        db.session.add(award)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this",
                "first_blood": False,
            },
        }

    if is_correct:
        if awarded_points > 0:
            clear_standings()
        return {
            "success": True,
            "data": {
                "status": "correct",
                "message": f"Correct (+{awarded_points} pts)" if awarded_points > 0 else "Correct",
                "points": awarded_points,
                "first_blood": False,
            },
        }

    return {
        "success": True,
        "data": {
            "status": "incorrect",
            "message": "Incorrect",
        },
    }


@prolabs.route("/admin/prolabs", methods=["GET", "POST"])
@admins_only
def prolab_admin():
    level_rules = get_level_rules()
    if request.method == "POST":
        slugs = request.form.getlist("slug[]")
        titles = request.form.getlist("title[]")
        categories = request.form.getlist("category[]")
        difficulties = request.form.getlist("difficulty[]")
        free_flags = request.form.getlist("is_free[]")
        covers = request.form.getlist("cover_image[]")
        logos = request.form.getlist("logo_image[]")
        ips = request.form.getlist("entry_ip[]")
        intros = request.form.getlist("introduction[]")
        infos = request.form.getlist("pro_lab_info[]")
        changelogs = request.form.getlist("changelog[]")
        required_levels = request.form.getlist("required_level[]")
        machines_list = request.form.getlist("machines[]")
        creators = request.form.getlist("creator[]")

        labs = []
        row_count = max(
            len(slugs),
            len(titles),
            len(categories),
            len(difficulties),
            len(covers),
            len(logos),
            len(ips),
            len(intros),
            len(infos),
            len(changelogs),
            len(required_levels),
            len(machines_list),
            len(creators),
        )

        for i in range(row_count):
            title = (titles[i] if i < len(titles) else "").strip()
            if not title:
                continue

            raw_machines = (machines_list[i] if i < len(machines_list) else "[]").strip()
            machines = []
            try:
                parsed_machines = json.loads(raw_machines or "[]")
                if isinstance(parsed_machines, list):
                    for machine_index, machine in enumerate(parsed_machines):
                        if not isinstance(machine, dict):
                            continue
                        normalized_machine = _normalize_machine(machine, machine_index)
                        if normalized_machine["name"]:
                            machines.append(normalized_machine)
            except Exception:
                machines = []

            flags = _build_display_flags([], machines)

            is_free = str(i) in free_flags
            required_level = _safe_int(
                required_levels[i] if i < len(required_levels) else 0, 0
            )

            labs.append(
                {
                    "slug": (slugs[i] if i < len(slugs) else "").strip(),
                    "title": title,
                    "category": (categories[i] if i < len(categories) else "Pro Labs").strip(),
                    "difficulty": (difficulties[i] if i < len(difficulties) else "Intermediate").strip(),
                    "is_free": is_free,
                    "cover_image": (covers[i] if i < len(covers) else "").strip(),
                    "logo_image": (logos[i] if i < len(logos) else "").strip(),
                    "entry_ip": (ips[i] if i < len(ips) else "").strip(),
                    "introduction": (intros[i] if i < len(intros) else "").strip(),
                    "pro_lab_info": ((infos[i] if i < len(infos) else "").strip() or DEFAULT_PRO_LAB_INFO_TEXT),
                    "changelog": ((changelogs[i] if i < len(changelogs) else "").strip() or DEFAULT_CHANGELOG_TEXT),
                    "required_level": required_level,
                    "machines": machines,
                    "flags": flags,
                    "topics": [],
                    "badges": [],
                    "progress": 0,
                    "rating": 5,
                    "rating_count": 0,
                    "creator": (creators[i] if i < len(creators) else "Unknown").strip(),
                }
            )

        if not labs:
            labs = DEFAULT_PROLABS

        set_config("pro_red_team_labs", json.dumps(labs))
        return redirect(url_for("prolabs.prolab_admin", saved=1))

    labs = get_prolabs()
    return render_template("prolabs/admin.html", labs=labs, levels=level_rules)


@prolabs.route("/admin/prolabs/levels", methods=["GET", "POST"])
@admins_only
def prolab_levels_admin():
    if request.method == "POST":
        names = request.form.getlist("level_name[]")
        min_scores = request.form.getlist("min_score[]")

        levels = []
        seen_names = set()
        row_count = max(len(names), len(min_scores))
        for i in range(row_count):
            name = _normalize_level_name(names[i] if i < len(names) else "")
            if not name or name in seen_names:
                continue
            min_score = max(0, _safe_int(min_scores[i] if i < len(min_scores) else 0, 0))
            levels.append({"name": name, "min_score": min_score})
            seen_names.add(name)

        levels = _normalize_levels(levels)
        set_config(LEVELS_CONFIG_KEY, json.dumps(levels))
        return redirect(url_for("prolabs.prolab_levels_admin", saved=1))

    levels = get_level_rules()
    return render_template("prolabs/levels.html", levels=levels)


def load(app):
    with app.app_context():
        db.create_all()
    app.register_blueprint(prolabs)
    register_admin_plugin_menu_bar("Pro Labs", "/admin/prolabs")
    register_admin_plugin_menu_bar("Pro Lab Levels", "/admin/prolabs/levels")

    @app.context_processor
    def inject_prolab_level_helpers():
        level_rules = get_level_rules()
        return {
            "prolab_level_rules": level_rules,
            "get_level_name_for_score": lambda score: get_level_name_for_score(
                score, level_rules=level_rules
            ),
        }
