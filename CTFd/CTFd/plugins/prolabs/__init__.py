import json
import re
from datetime import datetime, timedelta

from flask import Blueprint, abort, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from CTFd.cache import clear_standings
from CTFd.models import db
from CTFd.models import Awards, Challenges, Solves, Users
from CTFd.plugins import register_admin_plugin_menu_bar
from CTFd.utils.config.pages import build_markdown
from CTFd.utils import uploads
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.dates import ctftime
from CTFd.utils.scores import get_standings
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
    "freebasd": "FreeBSD",
    "solaris": "Solaris",
}

MACHINE_DIFFICULTY_OPTIONS = ["Easy", "Medium", "Hard", "Insane"]
MACHINE_OS_OPTIONS = ["Linux", "Windows", "FreeBSD", "Solaris"]
SHERLOCK_DIFFICULTY_OPTIONS = ["Very Easy", "Easy", "Medium", "Hard", "Insane"]
CVE_SEVERITY_OPTIONS = ["Low", "Medium", "High", "Critical"]

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

PROLAB_CATEGORY_OPTIONS = ["Pro Labs", "Mini Pro Labs"]
PROLAB_DIFFICULTY_OPTIONS = ["Easy", "Intermediate", "Hard", "APT Level"]


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


class Boot2RootSubmission(db.Model):
    __tablename__ = "boot2root_submissions"
    __table_args__ = (
        db.UniqueConstraint("machine_slug", "entry_id", "user_id"),
        db.UniqueConstraint("machine_slug", "entry_id", "team_id"),
        {},
    )

    id = db.Column(db.Integer, primary_key=True)
    machine_slug = db.Column(db.String(128), index=True, nullable=False)
    entry_id = db.Column(db.String(128), index=True, nullable=False)
    provided = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="incorrect")
    ip = db.Column(db.String(46), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class SherlockSubmission(db.Model):
    __tablename__ = "sherlock_submissions"
    __table_args__ = (
        db.UniqueConstraint("sherlock_slug", "entry_id", "user_id"),
        db.UniqueConstraint("sherlock_slug", "entry_id", "team_id"),
        {},
    )

    id = db.Column(db.Integer, primary_key=True)
    sherlock_slug = db.Column(db.String(128), index=True, nullable=False)
    entry_id = db.Column(db.String(128), index=True, nullable=False)
    provided = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="incorrect")
    ip = db.Column(db.String(46), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class CVESubmission(db.Model):
    __tablename__ = "cve_submissions"
    __table_args__ = (
        db.UniqueConstraint("cve_slug", "entry_id", "user_id"),
        db.UniqueConstraint("cve_slug", "entry_id", "team_id"),
        {},
    )

    id = db.Column(db.Integer, primary_key=True)
    cve_slug = db.Column(db.String(128), index=True, nullable=False)
    entry_id = db.Column(db.String(128), index=True, nullable=False)
    provided = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="incorrect")
    ip = db.Column(db.String(46), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


MACHINES_CONFIG_KEY = "boot2root_machines"

DEFAULT_BOOT2ROOT_MACHINES = [
    {
        "slug": "cap",
        "title": "Cap",
        "difficulty": "Easy",
        "os": "Linux",
        "rating": 4.6,
        "rating_count": 3049,
        "user_solves": 89438,
        "root_solves": 82126,
        "release_date": "05 Jun 2021",
        "machine_info": "## Machine Info\nCap is an easy Linux machine focused on misconfigurations and practical enumeration.",
        "walkthrough": "## Walkthrough\nAdd your walkthrough details here.",
        "walkthrough_files": [],
        "user_flag": "",
        "root_flag": "",
        "user_points": 50,
        "root_points": 100,
        "guided_questions": [
            {
                "id": "q1",
                "question": "Which service exposed the vulnerable functionality?",
                "answer": "ftp",
                "points": 10,
            }
        ],
    }
]

MACHINE_TIMER_TIERS = [1800, 3600, 7200]
MACHINE_TIMER_DEFAULT = 1800

SHERLOCKS_CONFIG_KEY = "prolab_sherlocks"

DEFAULT_SHERLOCKS = [
    {
        "slug": "brutus",
        "title": "Brutus",
        "difficulty": "Very Easy",
        "category": "DFIR",
        "rating": 4.7,
        "rating_count": 2034,
        "solves": 31503,
        "release_date": "04 Apr 2024",
        "description": "## Sherlock Scenario\nAnalyze Linux authentication evidence and answer task questions.",
        "docker_enabled": False,
        "docker_image": "",
        "docker_expiry": 0,
        "tasks": [
            {
                "id": "task-1",
                "title": "Task 1",
                "question": "Analyze auth.log. What is the source IP used for brute force?",
                "hint": "Look for repeated failed password attempts.",
                "answer": "127.0.0.1",
                "points": 20,
            }
        ],
    }
]


CVES_CONFIG_KEY = "prolab_cves"

DEFAULT_CVES = [
    {
        "slug": "apache-log4shell",
        "title": "Apache Log4Shell",
        "cve_id": "CVE-2021-44228",
        "severity": "Critical",
        "category": "Remote Code Execution",
        "cvss": 10.0,
        "release_date": "10 Dec 2021",
        "short_description": "Unauthenticated JNDI lookup abuse in Log4j can lead to remote code execution.",
        "description": "## Overview\nLog4Shell allows attackers to trigger remote code execution through crafted log messages.\n\n## Lab Objective\nIdentify impact points and submit the CVE flag.",
        "flag": "",
        "points": 40,
        "docker_enabled": False,
        "docker_image": "",
        "docker_expiry": 0,
        "references": [
            {
                "title": "NVD Entry",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
            }
        ],
    }
]


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


def _normalize_machine_difficulty(value):
    raw_value = (value or "").strip().lower()
    mapping = {
        "easy": "Easy",
        "medium": "Medium",
        "intermediate": "Medium",
        "hard": "Hard",
        "insane": "Insane",
    }
    return mapping.get(raw_value, "Easy")


def _normalize_sherlock_difficulty(value):
    raw_value = (value or "").strip().lower()
    mapping = {
        "very easy": "Very Easy",
        "easy": "Easy",
        "medium": "Medium",
        "intermediate": "Medium",
        "hard": "Hard",
        "insane": "Insane",
        "advanced": "Hard",
    }
    return mapping.get(raw_value, "Very Easy")


def _normalize_cve_severity(value):
    raw_value = (value or "").strip().lower()
    mapping = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }
    return mapping.get(raw_value, "Medium")


def _safe_points(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_int(value, fallback=0, default=None):
    if default is not None:
        fallback = default
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str):
        try:
            return max(0, int(value.strip()))
        except (ValueError, AttributeError):
            return fallback
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _safe_float(value, fallback=0.0):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return fallback


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return False


def _normalize_level_name(value):
    return (value or "").strip()


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


def _normalize_prolab_category(value):
    raw_value = (value or "").strip().lower()
    if raw_value == "mini pro labs":
        return "Mini Pro Labs"
    return "Pro Labs"


def _normalize_prolab_difficulty(value):
    raw_value = (value or "").strip().lower()
    mapping = {
        "easy": "Easy",
        "intermediate": "Intermediate",
        "hard": "Hard",
        "advanced": "Hard",
        "apt level": "APT Level",
        "apt": "APT Level",
    }
    return mapping.get(raw_value, "Intermediate")


def _normalize_lab(raw, fallback_index, level_rules=None):
    title = (raw.get("title") or f"Lab {fallback_index + 1}").strip()
    slug = _slugify(raw.get("slug") or title) or f"lab-{fallback_index + 1}"

    category = _normalize_prolab_category(raw.get("category"))
    difficulty = _normalize_prolab_difficulty(raw.get("difficulty"))
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


def _load_raw_config_list(config_key, default_items):
    configured = get_config(config_key)
    if not configured:
        return json.loads(json.dumps(default_items))

    try:
        data = json.loads(configured)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    return json.loads(json.dumps(default_items))


def _ensure_unique_slug(slug, existing_slugs):
    if slug not in existing_slugs:
        return slug

    index = 2
    candidate = f"{slug}-{index}"
    while candidate in existing_slugs:
        index += 1
        candidate = f"{slug}-{index}"
    return candidate


@prolabs.route("/admin/prolabs/add", methods=["GET", "POST"])
@admins_only
def prolab_admin_add():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            level_rules = get_level_rules()
            return render_template(
                "prolabs/add.html",
                error="Title is required",
                levels=level_rules,
                category_options=PROLAB_CATEGORY_OPTIONS,
                difficulty_options=PROLAB_DIFFICULTY_OPTIONS,
            )

        base_slug = _slugify((request.form.get("slug") or "").strip() or title) or "prolab"
        labs = _load_raw_config_list("pro_red_team_labs", DEFAULT_PROLABS)
        existing_slugs = {_slugify((item or {}).get("slug", "")) for item in labs if isinstance(item, dict)}
        slug = _ensure_unique_slug(base_slug, existing_slugs)

        raw_machines = (request.form.get("machines") or "[]").strip()
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

        template = json.loads(json.dumps(DEFAULT_PROLABS[0] if DEFAULT_PROLABS else {}))
        template["slug"] = slug
        template["title"] = title
        template["category"] = _normalize_prolab_category(request.form.get("category") or template.get("category"))
        template["difficulty"] = _normalize_prolab_difficulty(request.form.get("difficulty") or template.get("difficulty"))
        template["is_free"] = _as_bool(request.form.get("is_free") or "0")
        template["cover_image"] = (request.form.get("cover_image") or template.get("cover_image") or "").strip()
        template["logo_image"] = (request.form.get("logo_image") or template.get("logo_image") or "").strip()
        template["entry_ip"] = (request.form.get("entry_ip") or template.get("entry_ip") or "").strip()
        template["introduction"] = (request.form.get("introduction") or template.get("introduction") or "").strip()
        template["pro_lab_info"] = (
            (request.form.get("pro_lab_info") or "").strip() or template.get("pro_lab_info") or DEFAULT_PRO_LAB_INFO_TEXT
        )
        template["changelog"] = (
            (request.form.get("changelog") or "").strip() or template.get("changelog") or DEFAULT_CHANGELOG_TEXT
        )
        template["creator"] = (request.form.get("creator") or template.get("creator") or "Unknown").strip()
        template["required_level"] = _safe_int(request.form.get("required_level"), 0)
        template["machines"] = machines
        template["flags"] = flags
        template["topics"] = []
        template["badges"] = []
        template["progress"] = 0
        template["rating"] = 5
        template["rating_count"] = 0

        labs.append(template)
        set_config("pro_red_team_labs", json.dumps(labs))
        return redirect(url_for("prolabs.prolab_admin_manage", saved=1, _anchor=f"lab-{slug}"))

    level_rules = get_level_rules()
    return render_template(
        "prolabs/add.html",
        levels=level_rules,
        category_options=PROLAB_CATEGORY_OPTIONS,
        difficulty_options=PROLAB_DIFFICULTY_OPTIONS,
    )


@prolabs.route("/pro-red-team-labs", methods=["GET"])
@authed_only
def prolab_listing():
    labs = get_prolabs()
    level_rules = get_level_rules()

    for lab in labs:
        lab["is_locked"] = _is_lab_locked_for_current_account(lab, level_rules=level_rules)

    return render_template("prolabs/list.html", labs=labs)


@prolabs.route("/pro-red-team-labs/<slug>", methods=["GET"])
@authed_only
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


@prolabs.route("/admin/prolabs", methods=["GET"])
@admins_only
def prolab_admin_list():
    labs = get_prolabs()
    return render_template("prolabs/admin_list.html", labs=labs)


@prolabs.route("/admin/prolabs/manage", methods=["GET", "POST"])
@admins_only
def prolab_admin_manage():
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
                    "category": _normalize_prolab_category(categories[i] if i < len(categories) else "Pro Labs"),
                    "difficulty": _normalize_prolab_difficulty(difficulties[i] if i < len(difficulties) else "Intermediate"),
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
        return redirect(url_for("prolabs.prolab_admin_manage", saved=1))

    labs = get_prolabs()
    return render_template(
        "prolabs/admin.html",
        labs=labs,
        levels=level_rules,
        category_options=PROLAB_CATEGORY_OPTIONS,
        difficulty_options=PROLAB_DIFFICULTY_OPTIONS,
    )


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


def _normalize_guided_questions(raw_questions):
    if isinstance(raw_questions, str):
        try:
            raw_questions = json.loads(raw_questions)
        except Exception:
            raw_questions = []

    if not isinstance(raw_questions, list):
        raw_questions = []

    questions = []
    for idx, item in enumerate(raw_questions):
        if not isinstance(item, dict):
            continue
        qid = _slugify(item.get("id") or f"q-{idx + 1}")
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if not question:
            continue
        questions.append(
            {
                "id": qid,
                "question": question,
                "answer": answer,
                "points": _safe_points(item.get("points", 0)),
            }
        )
    return questions


def _normalize_walkthrough_files(raw_files):
    if isinstance(raw_files, str):
        try:
            raw_files = json.loads(raw_files)
        except Exception:
            raw_files = []

    if not isinstance(raw_files, list):
        return []

    normalized = []
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        location = (item.get("location") or "").strip()
        if not location:
            continue
        normalized.append(
            {
                "name": (item.get("name") or location.split("/")[-1]).strip(),
                "location": location,
            }
        )
    return normalized


def _normalize_boot2root_machine(raw, index):
    title = (raw.get("title") or f"Machine {index + 1}").strip()
    slug = _slugify(raw.get("slug") or title) or f"machine-{index + 1}"
    difficulty = _normalize_machine_difficulty(raw.get("difficulty"))
    os_name = _normalize_os(raw.get("os"))
    release_date = (raw.get("release_date") or "").strip()
    machine_info = (raw.get("machine_info") or "").strip()
    walkthrough = (raw.get("walkthrough") or "").strip()

    return {
        "slug": slug,
        "title": title,
        "difficulty": difficulty,
        "os": os_name,
        "rating": _safe_float(raw.get("rating", 0), 0.0),
        "rating_count": _safe_int(raw.get("rating_count", 0), 0),
        "user_solves": _safe_int(raw.get("user_solves", 0), 0),
        "root_solves": _safe_int(raw.get("root_solves", 0), 0),
        "release_date": release_date,
        "machine_info": machine_info,
        "machine_info_html": build_markdown(machine_info, sanitize=True),
        "walkthrough": walkthrough,
        "walkthrough_html": build_markdown(walkthrough, sanitize=True),
        "walkthrough_files": _normalize_walkthrough_files(raw.get("walkthrough_files", [])),
        "user_flag": (raw.get("user_flag") or "").strip(),
        "root_flag": (raw.get("root_flag") or "").strip(),
        "user_points": _safe_points(raw.get("user_points", 50)),
        "root_points": _safe_points(raw.get("root_points", 100)),
        "guided_questions": _normalize_guided_questions(raw.get("guided_questions", [])),
        "docker_enabled": _as_bool(raw.get("docker_enabled", False)),
        "docker_image": (raw.get("docker_image") or "").strip(),
        "docker_expiry": _safe_int(raw.get("docker_expiry", 0), 0),
    }


def get_boot2root_machines():
    configured = get_config(MACHINES_CONFIG_KEY)
    if not configured:
        return [
            _normalize_boot2root_machine(item, index)
            for index, item in enumerate(DEFAULT_BOOT2ROOT_MACHINES)
        ]

    try:
        data = json.loads(configured)
        if not isinstance(data, list):
            raise ValueError("Expected list")
    except Exception:
        data = DEFAULT_BOOT2ROOT_MACHINES

    machines = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            machines.append(_normalize_boot2root_machine(item, index))

    if not machines:
        machines = [
            _normalize_boot2root_machine(item, index)
            for index, item in enumerate(DEFAULT_BOOT2ROOT_MACHINES)
        ]
    return machines


def _get_machine_submissions(machine_slug):
    user, team, scope = _get_current_account_scope()
    if user is None:
        return {}

    query = Boot2RootSubmission.query.filter_by(machine_slug=machine_slug, status="correct")
    if scope == "team":
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)

    return {row.entry_id: row for row in query.all()}


def _find_guided_question(machine, question_id):
    for item in machine.get("guided_questions", []):
        if item.get("id") == question_id:
            return item
    return None


def _normalize_sherlock_tasks(raw_tasks):
    if isinstance(raw_tasks, str):
        try:
            raw_tasks = json.loads(raw_tasks)
        except Exception:
            raw_tasks = []

    if not isinstance(raw_tasks, list):
        raw_tasks = []

    normalized = []
    for idx, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            continue
        task_id = _slugify(item.get("id") or f"task-{idx + 1}") or f"task-{idx + 1}"
        question = (item.get("question") or "").strip()
        if not question:
            continue
        normalized.append(
            {
                "id": task_id,
                "title": (item.get("title") or f"Task {idx + 1}").strip(),
                "question": question,
                "hint": (item.get("hint") or "").strip(),
                "answer": (item.get("answer") or "").strip(),
                "points": _safe_points(item.get("points", 0)),
            }
        )
    return normalized


def _normalize_sherlock(raw, index):
    title = (raw.get("title") or f"Sherlock {index + 1}").strip()
    slug = _slugify(raw.get("slug") or title) or f"sherlock-{index + 1}"
    description = (raw.get("description") or "").strip()
    tasks = _normalize_sherlock_tasks(raw.get("tasks", []))

    return {
        "slug": slug,
        "title": title,
        "difficulty": _normalize_sherlock_difficulty(raw.get("difficulty")),
        "category": (raw.get("category") or "DFIR").strip(),
        "rating": _safe_float(raw.get("rating", 0), 0.0),
        "rating_count": _safe_int(raw.get("rating_count", 0), 0),
        "solves": _safe_int(raw.get("solves", 0), 0),
        "release_date": (raw.get("release_date") or "").strip(),
        "description": description,
        "description_html": build_markdown(description, sanitize=True),
        "docker_enabled": _as_bool(raw.get("docker_enabled", False)),
        "docker_image": (raw.get("docker_image") or "").strip(),
        "docker_expiry": _safe_int(raw.get("docker_expiry", 0), 0),
        "tasks": tasks,
    }


def get_sherlocks():
    configured = get_config(SHERLOCKS_CONFIG_KEY)
    if not configured:
        return [_normalize_sherlock(item, index) for index, item in enumerate(DEFAULT_SHERLOCKS)]

    try:
        data = json.loads(configured)
        if not isinstance(data, list):
            raise ValueError("Expected list")
    except Exception:
        data = DEFAULT_SHERLOCKS

    sherlocks = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            sherlocks.append(_normalize_sherlock(item, index))

    if not sherlocks:
        sherlocks = [_normalize_sherlock(item, index) for index, item in enumerate(DEFAULT_SHERLOCKS)]
    return sherlocks


def _get_sherlock_submissions(sherlock_slug):
    user, team, scope = _get_current_account_scope()
    if user is None:
        return {}

    query = SherlockSubmission.query.filter_by(sherlock_slug=sherlock_slug, status="correct")
    if scope == "team":
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)

    return {row.entry_id: row for row in query.all()}


def _find_sherlock_task(sherlock, entry_id):
    for task in sherlock.get("tasks", []):
        if task.get("id") == entry_id:
            return task
    return None


def _normalize_cve_references(raw_refs):
    if isinstance(raw_refs, str):
        try:
            raw_refs = json.loads(raw_refs)
        except Exception:
            raw_refs = []

    if not isinstance(raw_refs, list):
        return []

    refs = []
    for item in raw_refs:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title and not url:
            continue
        refs.append({"title": title or url, "url": url})
    return refs


def _normalize_cve(raw, index):
    title = (raw.get("title") or f"CVE Item {index + 1}").strip()
    slug = _slugify(raw.get("slug") or title) or f"cve-{index + 1}"
    cve_id = (raw.get("cve_id") or "").strip()
    severity = _normalize_cve_severity(raw.get("severity"))
    category = (raw.get("category") or "Web").strip()
    release_date = (raw.get("release_date") or "").strip()
    short_description = (raw.get("short_description") or "").strip()
    description = (raw.get("description") or "").strip()

    return {
        "slug": slug,
        "title": title,
        "cve_id": cve_id,
        "severity": severity,
        "category": category,
        "cvss": _safe_float(raw.get("cvss", 0), 0.0),
        "release_date": release_date,
        "short_description": short_description,
        "description": description,
        "description_html": build_markdown(description, sanitize=True),
        "flag": (raw.get("flag") or "").strip(),
        "points": _safe_points(raw.get("points", 0)),
        "docker_enabled": _as_bool(raw.get("docker_enabled", False)),
        "docker_image": (raw.get("docker_image") or "").strip(),
        "docker_expiry": _safe_int(raw.get("docker_expiry", 0), 0),
        "references": _normalize_cve_references(raw.get("references", [])),
    }


def get_cves():
    configured = get_config(CVES_CONFIG_KEY)
    if not configured:
        return [_normalize_cve(item, index) for index, item in enumerate(DEFAULT_CVES)]

    try:
        data = json.loads(configured)
        if not isinstance(data, list):
            raise ValueError("Expected list")
    except Exception:
        data = DEFAULT_CVES

    cves = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            cves.append(_normalize_cve(item, index))

    if not cves:
        cves = [_normalize_cve(item, index) for index, item in enumerate(DEFAULT_CVES)]
    return cves


def _get_cve_submissions(cve_slug):
    user, team, scope = _get_current_account_scope()
    if user is None:
        return {}

    query = CVESubmission.query.filter_by(cve_slug=cve_slug, status="correct")
    if scope == "team":
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)

    return {row.entry_id: row for row in query.all()}


def _get_cve_container_entry(slug, cve, deps, user, team, scope):
    image = cve.get("docker_image")
    if not image:
        return None

    challenge_key = f"cve:{slug}"
    query = deps["DockerChallengeTracker"].query.filter_by(
        docker_image=image,
        challenge=challenge_key,
    )
    if scope == "team" and team is not None:
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)
    return query.first()


def _clean_expired_cve_container(slug, cve, deps, docker_config, user, team, scope):
    entry = _get_cve_container_entry(slug, cve, deps, user, team, scope)
    if entry is None:
        return None

    now = int(datetime.utcnow().timestamp())
    if entry.revert_time and int(entry.revert_time) <= now:
        try:
            deps["delete_container"](docker_config, entry.instance_id, ports_str=entry.ports)
        except Exception:
            pass
        deps["DockerChallengeTracker"].query.filter_by(id=entry.id).delete()
        db.session.commit()
        return None

    return entry


def _build_cve_docker_status(slug, cve):
    max_timer = MACHINE_TIMER_DEFAULT
    base = {
        "enabled": bool(cve.get("docker_enabled")),
        "configured": False,
        "authenticated": False,
        "running": False,
        "docker_image": cve.get("docker_image", ""),
        "host": "",
        "ports": [],
        "revert_time": None,
        "max_timer": max_timer,
        "can_extend": False,
        "current_tier": 0,
        "message": "Docker is disabled for this CVE.",
    }

    if not base["enabled"]:
        return base

    if not cve.get("docker_image"):
        base["message"] = "No Docker image configured by admins."
        return base

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        base["message"] = "Docker plugin is unavailable."
        return base

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        base["message"] = "Docker host is not configured."
        return base

    max_timer = _resolve_machine_timer_cap(cve, docker_config)
    base["max_timer"] = max_timer

    base["configured"] = True
    user, team, scope = _get_current_account_scope()
    if user is None:
        base["message"] = "Log in to spawn a CVE instance."
        return base

    base["authenticated"] = True
    entry = _clean_expired_cve_container(slug, cve, deps, docker_config, user, team, scope)
    if entry is None:
        base["message"] = "No active container instance."
        return base

    host = docker_config.display_host or str(docker_config.hostname).split(":")[0]
    ports = [p for p in (entry.ports or "").split(",") if p]
    tiers = _timer_tiers_for_cap(max_timer)
    current_tier = 0
    if entry.revert_time and entry.timestamp:
        current_tier = max(0, int(entry.revert_time) - int(entry.timestamp))
    can_extend = any(tier > current_tier for tier in tiers)

    base.update(
        {
            "running": True,
            "host": host,
            "ports": ports,
            "revert_time": entry.revert_time,
            "current_tier": current_tier,
            "can_extend": can_extend,
            "message": "Container is running.",
        }
    )
    return base


def _get_sherlock_progress(sherlock):
    tasks = sherlock.get("tasks", [])
    total = len(tasks)
    if total == 0:
        return 0
    solved = _get_sherlock_submissions(sherlock["slug"])
    solved_count = sum(1 for task in tasks if task.get("id") in solved)
    return int((solved_count / total) * 100)


def _get_docker_challenge_dependencies():
    try:
        from CTFd.plugins.docker_challenges import (
            DockerChallengeTracker,
            DockerConfig,
            add_port_forward,
            create_container,
            delete_container,
            get_repositories,
            get_unavailable_ports,
        )
    except Exception:
        return None

    return {
        "DockerChallengeTracker": DockerChallengeTracker,
        "DockerConfig": DockerConfig,
        "add_port_forward": add_port_forward,
        "create_container": create_container,
        "delete_container": delete_container,
        "get_repositories": get_repositories,
        "get_unavailable_ports": get_unavailable_ports,
    }


def _get_machine_container_entry(slug, machine, deps, user, team, scope):
    image = machine.get("docker_image")
    if not image:
        return None

    challenge_key = f"machine:{slug}"
    query = deps["DockerChallengeTracker"].query.filter_by(
        docker_image=image,
        challenge=challenge_key,
    )
    if scope == "team" and team is not None:
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)

    return query.first()


def _clean_expired_machine_container(slug, machine, deps, docker_config, user, team, scope):
    entry = _get_machine_container_entry(slug, machine, deps, user, team, scope)
    if entry is None:
        return None

    now = int(datetime.utcnow().timestamp())
    if entry.revert_time and int(entry.revert_time) <= now:
        try:
            deps["delete_container"](docker_config, entry.instance_id, ports_str=entry.ports)
        except Exception:
            pass
        deps["DockerChallengeTracker"].query.filter_by(id=entry.id).delete()
        db.session.commit()
        return None

    return entry


def _build_machine_docker_status(slug, machine):
    max_timer = MACHINE_TIMER_DEFAULT
    base = {
        "enabled": bool(machine.get("docker_enabled")),
        "configured": False,
        "authenticated": False,
        "running": False,
        "docker_image": machine.get("docker_image", ""),
        "host": "",
        "ports": [],
        "revert_time": None,
        "max_timer": max_timer,
        "can_extend": False,
        "current_tier": 0,
        "message": "Docker is disabled for this machine.",
    }

    if not base["enabled"]:
        return base

    if not machine.get("docker_image"):
        base["message"] = "No Docker image configured by admins."
        return base

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        base["message"] = "Docker plugin is unavailable."
        return base

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        base["message"] = "Docker host is not configured."
        return base

    max_timer = _resolve_machine_timer_cap(machine, docker_config)
    base["max_timer"] = max_timer

    base["configured"] = True
    user, team, scope = _get_current_account_scope()
    if user is None:
        base["message"] = "Log in to spawn a machine instance."
        return base

    base["authenticated"] = True
    entry = _clean_expired_machine_container(slug, machine, deps, docker_config, user, team, scope)
    if entry is None:
        base["message"] = "No active container instance."
        return base

    host = docker_config.display_host or str(docker_config.hostname).split(":")[0]
    ports = [p for p in (entry.ports or "").split(",") if p]
    tiers = _timer_tiers_for_cap(max_timer)
    current_tier = 0
    if entry.revert_time and entry.timestamp:
        current_tier = max(0, int(entry.revert_time) - int(entry.timestamp))
    can_extend = any(tier > current_tier for tier in tiers)

    base.update(
        {
            "running": True,
            "host": host,
            "ports": ports,
            "revert_time": entry.revert_time,
            "current_tier": current_tier,
            "can_extend": can_extend,
            "message": "Container is running.",
        }
    )
    return base


def _resolve_machine_timer_cap(machine, docker_config=None):
    configured = _safe_int(machine.get("docker_expiry", 0), 0)
    if configured in MACHINE_TIMER_TIERS:
        return configured

    if configured <= 0 and docker_config is not None:
        configured = _safe_int(getattr(docker_config, "container_expiry", 0), 0)

    if configured <= 0:
        return MACHINE_TIMER_DEFAULT

    for tier in MACHINE_TIMER_TIERS:
        if configured <= tier:
            return tier
    return MACHINE_TIMER_TIERS[-1]


def _timer_tiers_for_cap(max_timer):
    tiers = [tier for tier in MACHINE_TIMER_TIERS if tier <= max_timer]
    return tiers or [MACHINE_TIMER_DEFAULT]


def _get_available_docker_images():
    deps = _get_docker_challenge_dependencies()
    if deps is None:
        return [], "Docker plugin unavailable"

    try:
        docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
        if docker_config is None or not docker_config.hostname:
            return [], "Docker host is not configured"
        repositories = deps["get_repositories"](docker_config, tags=True) or []
        repositories = sorted({str(item).strip() for item in repositories if str(item).strip()})
        return repositories, ""
    except Exception:
        return [], "Failed to load Docker image tags"


def _get_sherlock_container_entry(slug, sherlock, deps, user, team, scope):
    image = sherlock.get("docker_image")
    if not image:
        return None

    challenge_key = f"sherlock:{slug}"
    query = deps["DockerChallengeTracker"].query.filter_by(
        docker_image=image,
        challenge=challenge_key,
    )
    if scope == "team" and team is not None:
        query = query.filter_by(team_id=team.id)
    else:
        query = query.filter_by(user_id=user.id)
    return query.first()


def _clean_expired_sherlock_container(slug, sherlock, deps, docker_config, user, team, scope):
    entry = _get_sherlock_container_entry(slug, sherlock, deps, user, team, scope)
    if entry is None:
        return None

    now = int(datetime.utcnow().timestamp())
    if entry.revert_time and int(entry.revert_time) <= now:
        try:
            deps["delete_container"](docker_config, entry.instance_id, ports_str=entry.ports)
        except Exception:
            pass
        deps["DockerChallengeTracker"].query.filter_by(id=entry.id).delete()
        db.session.commit()
        return None

    return entry


def _build_sherlock_docker_status(slug, sherlock):
    max_timer = MACHINE_TIMER_DEFAULT
    base = {
        "enabled": bool(sherlock.get("docker_enabled")),
        "configured": False,
        "authenticated": False,
        "running": False,
        "docker_image": sherlock.get("docker_image", ""),
        "host": "",
        "ports": [],
        "revert_time": None,
        "max_timer": max_timer,
        "can_extend": False,
        "current_tier": 0,
        "message": "Docker is disabled for this sherlock.",
    }

    if not base["enabled"]:
        return base

    if not sherlock.get("docker_image"):
        base["message"] = "No Docker image configured by admins."
        return base

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        base["message"] = "Docker plugin is unavailable."
        return base

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        base["message"] = "Docker host is not configured."
        return base

    max_timer = _resolve_machine_timer_cap(sherlock, docker_config)
    base["max_timer"] = max_timer

    base["configured"] = True
    user, team, scope = _get_current_account_scope()
    if user is None:
        base["message"] = "Log in to spawn a sherlock instance."
        return base

    base["authenticated"] = True
    entry = _clean_expired_sherlock_container(slug, sherlock, deps, docker_config, user, team, scope)
    if entry is None:
        base["message"] = "No active container instance."
        return base

    host = docker_config.display_host or str(docker_config.hostname).split(":")[0]
    ports = [p for p in (entry.ports or "").split(",") if p]
    tiers = _timer_tiers_for_cap(max_timer)
    current_tier = 0
    if entry.revert_time and entry.timestamp:
        current_tier = max(0, int(entry.revert_time) - int(entry.timestamp))
    can_extend = any(tier > current_tier for tier in tiers)

    base.update(
        {
            "running": True,
            "host": host,
            "ports": ports,
            "revert_time": entry.revert_time,
            "current_tier": current_tier,
            "can_extend": can_extend,
            "message": "Container is running.",
        }
    )
    return base


@prolabs.route("/machines", methods=["GET"])
@authed_only
def machines_listing():
    machines = get_boot2root_machines()
    user, _, _ = _get_current_account_scope()
    for machine in machines:
        machine["status"] = "Unowned"
        machine["owned_user"] = False
        machine["owned_root"] = False
        if user is None:
            continue

        solved = _get_machine_submissions(machine["slug"])
        machine["owned_user"] = "user-flag" in solved
        machine["owned_root"] = "root-flag" in solved
        if machine["owned_user"] and machine["owned_root"]:
            machine["status"] = "Owned"
        elif machine["owned_user"] or machine["owned_root"]:
            machine["status"] = "Partial"

    return render_template("machines/list.html", machines=machines)


@prolabs.route("/machines/<slug>", methods=["GET"])
@authed_only
def machines_detail(slug):
    machines = get_boot2root_machines()
    machine = next((item for item in machines if item["slug"] == slug), None)
    if not machine:
        abort(404)

    solved = _get_machine_submissions(slug)
    machine["user_flag_owned"] = "user-flag" in solved
    machine["root_flag_owned"] = "root-flag" in solved
    machine["guided_owned"] = [key for key in solved.keys() if key.startswith("guided-")]
    machine["docker_status"] = _build_machine_docker_status(slug, machine)

    return render_template("machines/detail.html", machine=machine)


@prolabs.route("/api/v1/machines/<slug>/container", methods=["GET", "POST"])
@authed_only
def machines_container(slug):
    machines = get_boot2root_machines()
    machine = next((item for item in machines if item["slug"] == slug), None)
    if not machine:
        return {"success": False, "errors": {"message": "Machine not found"}}, 404

    action = "status"
    if request.method == "POST":
        req = request.form or request.get_json(silent=True) or {}
        action = (req.get("action") or "status").strip().lower()
    else:
        action = (request.args.get("action") or "status").strip().lower()

    if action not in {"status", "start", "stop", "extend"}:
        return {"success": False, "errors": {"message": "Unsupported action"}}, 400

    if not machine.get("docker_enabled"):
        return {"success": False, "errors": {"message": "Docker is disabled for this machine"}}, 400
    if not machine.get("docker_image"):
        return {"success": False, "errors": {"message": "No Docker image configured for this machine"}}, 400

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        return {"success": False, "errors": {"message": "Docker plugin is unavailable"}}, 503

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        return {"success": False, "errors": {"message": "Docker host is not configured"}}, 403

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    existing = _clean_expired_machine_container(
        slug,
        machine,
        deps,
        docker_config,
        user,
        team,
        scope,
    )

    if action == "status":
        return {"success": True, "data": _build_machine_docker_status(slug, machine)}

    if action == "extend":
        if existing is None:
            return {
                "success": False,
                "errors": {"message": "No running container to extend."},
            }, 400

        max_timer = _resolve_machine_timer_cap(machine, docker_config)
        tiers = _timer_tiers_for_cap(max_timer)
        current_tier = (
            max(0, int(existing.revert_time) - int(existing.timestamp))
            if existing.revert_time and existing.timestamp
            else tiers[0]
        )
        next_tier = next((tier for tier in tiers if tier > current_tier), None)
        if next_tier is None:
            return {
                "success": False,
                "errors": {"message": "Maximum allowed timer has been reached for this machine."},
                "data": _build_machine_docker_status(slug, machine),
            }, 400

        base_ts = int(existing.timestamp) if existing.timestamp else int(datetime.utcnow().timestamp())
        existing.revert_time = base_ts + next_tier
        db.session.commit()
        return {
            "success": True,
            "data": _build_machine_docker_status(slug, machine),
            "message": f"Container extended to {next_tier // 60} minutes.",
        }

    if action == "stop":
        if existing is None:
            return {
                "success": True,
                "data": _build_machine_docker_status(slug, machine),
                "message": "No running container to stop.",
            }

        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {"success": False, "errors": {"message": "Failed to stop container"}}, 500

        return {
            "success": True,
            "data": _build_machine_docker_status(slug, machine),
            "message": "Container stopped.",
        }

    did_revert = False
    if existing is not None:
        # Match docker challenge behavior: start acts as a revert when an instance already exists.
        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
            did_revert = True
        except Exception:
            db.session.rollback()
            return {
                "success": False,
                "errors": {"message": "Failed to revert existing container"},
            }, 500

    repositories = []
    try:
        repositories = deps["get_repositories"](docker_config, tags=True) or []
    except Exception:
        repositories = []

    image_name = machine.get("docker_image")
    if repositories:
        image_repo = image_name.split(":", 1)[0]
        if image_name not in repositories and image_repo not in repositories:
            return {
                "success": False,
                "errors": {"message": f"Docker image {image_name} is not available on the host"},
            }, 403

    if scope == "team" and team is not None:
        running_count = deps["DockerChallengeTracker"].query.filter_by(team_id=team.id).count()
    else:
        running_count = deps["DockerChallengeTracker"].query.filter_by(user_id=user.id).count()

    max_containers = 3
    if running_count >= max_containers:
        return {
            "success": False,
            "errors": {
                "message": f"You already have {running_count} running containers. Stop one before spawning a new instance.",
            },
        }, 403

    create_result = deps["create_container"](
        docker_config,
        image_name,
        team.name if scope == "team" and team is not None else user.name,
        deps["get_unavailable_ports"](docker_config),
    )
    if not create_result or not create_result[0] or "Id" not in create_result[0]:
        return {
            "success": False,
            "errors": {"message": "Failed to create Docker container. Verify Docker host and image settings."},
        }, 500

    port_bindings = json.loads(create_result[1]).get("HostConfig", {}).get("PortBindings", {})
    host_ports = []
    for bindings in port_bindings.values():
        if not bindings:
            continue
        host_port = bindings[0].get("HostPort")
        if host_port:
            host_ports.append(host_port)

    for host_port in host_ports:
        try:
            deps["add_port_forward"](host_port, docker_config.display_host)
        except Exception:
            continue

    now = int(datetime.utcnow().timestamp())
    max_timer = _resolve_machine_timer_cap(machine, docker_config)
    tiers = _timer_tiers_for_cap(max_timer)
    initial_timer = tiers[0]
    challenge_key = f"machine:{slug}"
    tracker = deps["DockerChallengeTracker"](
        team_id=team.id if scope == "team" and team is not None else None,
        user_id=user.id if scope != "team" else None,
        docker_image=image_name,
        timestamp=now,
        revert_time=now + initial_timer,
        instance_id=create_result[0]["Id"],
        ports=",".join(host_ports),
        host=(docker_config.display_host or str(docker_config.hostname).split(":")[0]),
        challenge=challenge_key,
    )
    db.session.add(tracker)
    db.session.commit()

    return {
        "success": True,
        "data": _build_machine_docker_status(slug, machine),
        "message": (
            f"Container reverted. Timer set to {initial_timer // 60} minutes."
            if did_revert
            else f"Container started. Timer set to {initial_timer // 60} minutes."
        ),
    }


@prolabs.route("/api/v1/machines/<slug>/submit", methods=["POST"])
@authed_only
def machines_submit(slug):
    req = request.form or request.get_json(silent=True) or {}
    entry_id = (req.get("entry_id") or "").strip()
    answer = (req.get("answer") or "").strip()

    if not entry_id or not answer:
        return {"success": False, "errors": {"message": "Missing entry_id or answer"}}, 400

    machines = get_boot2root_machines()
    machine = next((item for item in machines if item["slug"] == slug), None)
    if not machine:
        return {"success": False, "errors": {"message": "Machine not found"}}, 404

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    if not (ctftime() or is_admin()):
        return {"success": False, "errors": {"message": "Submissions are closed"}}, 403

    expected = ""
    points = 0
    award_name = ""

    if entry_id == "user-flag":
        expected = machine.get("user_flag", "")
        points = _safe_points(machine.get("user_points", 0))
        award_name = f"{machine['title']} - User Flag"
    elif entry_id == "root-flag":
        expected = machine.get("root_flag", "")
        points = _safe_points(machine.get("root_points", 0))
        award_name = f"{machine['title']} - Root Flag"
    elif entry_id.startswith("guided-"):
        qid = entry_id.replace("guided-", "", 1)
        question = _find_guided_question(machine, qid)
        if not question:
            return {"success": False, "errors": {"message": "Unknown guided question"}}, 404
        expected = question.get("answer", "")
        points = _safe_points(question.get("points", 0))
        award_name = f"{machine['title']} - Guided {qid}"
    else:
        return {"success": False, "errors": {"message": "Unknown entry type"}}, 400

    scoped_query = Boot2RootSubmission.query.filter_by(machine_slug=slug, entry_id=entry_id)
    if scope == "team":
        scoped_query = scoped_query.filter_by(team_id=team.id)
    else:
        scoped_query = scoped_query.filter_by(user_id=user.id)

    existing = scoped_query.first()
    if existing is not None and existing.status == "correct":
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this",
                "total_score": _get_current_account_score(),
            },
        }

    is_correct = expected and answer == expected

    if existing is None:
        row = Boot2RootSubmission(
            machine_slug=slug,
            entry_id=entry_id,
            provided=answer,
            status="correct" if is_correct else "incorrect",
            ip=get_ip(req=request),
            user_id=user.id,
            team_id=team.id if team else None,
        )
        db.session.add(row)
    else:
        existing.provided = answer
        existing.status = "correct" if is_correct else "incorrect"
        existing.ip = get_ip(req=request)
        existing.user_id = user.id
        existing.team_id = team.id if team else None
        existing.date = datetime.utcnow()

    if is_correct and points > 0:
        db.session.add(
            Awards(
                user_id=user.id,
                team_id=team.id if team else None,
                name=award_name[:80],
                description=f"Solved {entry_id} in {machine['title']}",
                value=points,
                category="Boot2Root Machines",
                icon="fas fa-server",
            )
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this",
                "total_score": _get_current_account_score(),
            },
        }

    if is_correct:
        if points > 0:
            clear_standings()
        return {
            "success": True,
            "data": {
                "status": "correct",
                "message": f"Correct (+{points} pts)" if points > 0 else "Correct",
                "points": points,
                "total_score": _get_current_account_score(),
            },
        }

    return {
        "success": True,
        "data": {
            "status": "incorrect",
            "message": "Incorrect",
            "total_score": _get_current_account_score(),
        },
    }


@prolabs.route("/cves", methods=["GET"])
@authed_only
def cves_listing():
    cves = get_cves()
    for item in cves:
        solved = _get_cve_submissions(item["slug"])
        item["solved"] = "main-flag" in solved
        item["status"] = "Resolved" if item["solved"] else "Unresolved"
    return render_template("cves/list.html", cves=cves)


@prolabs.route("/cves/<slug>", methods=["GET"])
@authed_only
def cves_detail(slug):
    cves = get_cves()
    cve = next((item for item in cves if item["slug"] == slug), None)
    if not cve:
        abort(404)

    solved = _get_cve_submissions(slug)
    cve["solved"] = "main-flag" in solved
    cve["docker_status"] = _build_cve_docker_status(slug, cve)
    return render_template("cves/detail.html", cve=cve)


@prolabs.route("/api/v1/cves/<slug>/container", methods=["GET", "POST"])
@authed_only
def cves_container(slug):
    cves = get_cves()
    cve = next((item for item in cves if item["slug"] == slug), None)
    if not cve:
        return {"success": False, "errors": {"message": "CVE not found"}}, 404

    action = "status"
    if request.method == "POST":
        req = request.form or request.get_json(silent=True) or {}
        action = (req.get("action") or "status").strip().lower()
    else:
        action = (request.args.get("action") or "status").strip().lower()

    if action not in {"status", "start", "stop", "extend"}:
        return {"success": False, "errors": {"message": "Unsupported action"}}, 400

    if not cve.get("docker_enabled"):
        return {"success": False, "errors": {"message": "Docker is disabled for this CVE"}}, 400
    if not cve.get("docker_image"):
        return {"success": False, "errors": {"message": "No Docker image configured for this CVE"}}, 400

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        return {"success": False, "errors": {"message": "Docker plugin is unavailable"}}, 503

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        return {"success": False, "errors": {"message": "Docker host is not configured"}}, 403

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    existing = _clean_expired_cve_container(slug, cve, deps, docker_config, user, team, scope)

    if action == "status":
        return {"success": True, "data": _build_cve_docker_status(slug, cve)}

    if action == "extend":
        if existing is None:
            return {"success": False, "errors": {"message": "No running container to extend."}}, 400

        max_timer = _resolve_machine_timer_cap(cve, docker_config)
        tiers = _timer_tiers_for_cap(max_timer)
        current_tier = (
            max(0, int(existing.revert_time) - int(existing.timestamp))
            if existing.revert_time and existing.timestamp
            else tiers[0]
        )
        next_tier = next((tier for tier in tiers if tier > current_tier), None)
        if next_tier is None:
            return {
                "success": False,
                "errors": {"message": "Maximum allowed timer has been reached for this CVE."},
                "data": _build_cve_docker_status(slug, cve),
            }, 400

        base_ts = int(existing.timestamp) if existing.timestamp else int(datetime.utcnow().timestamp())
        existing.revert_time = base_ts + next_tier
        db.session.commit()
        return {
            "success": True,
            "data": _build_cve_docker_status(slug, cve),
            "message": f"Container extended to {next_tier // 60} minutes.",
        }

    if action == "stop":
        if existing is None:
            return {
                "success": True,
                "data": _build_cve_docker_status(slug, cve),
                "message": "No running container to stop.",
            }

        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {"success": False, "errors": {"message": "Failed to stop container"}}, 500

        return {
            "success": True,
            "data": _build_cve_docker_status(slug, cve),
            "message": "Container stopped.",
        }

    did_revert = False
    if existing is not None:
        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
            did_revert = True
        except Exception:
            db.session.rollback()
            return {"success": False, "errors": {"message": "Failed to revert existing container"}}, 500

    repositories = []
    try:
        repositories = deps["get_repositories"](docker_config, tags=True) or []
    except Exception:
        repositories = []

    image_name = cve.get("docker_image")
    if repositories:
        image_repo = image_name.split(":", 1)[0]
        if image_name not in repositories and image_repo not in repositories:
            return {
                "success": False,
                "errors": {"message": f"Docker image {image_name} is not available on the host"},
            }, 403

    if scope == "team" and team is not None:
        running_count = deps["DockerChallengeTracker"].query.filter_by(team_id=team.id).count()
    else:
        running_count = deps["DockerChallengeTracker"].query.filter_by(user_id=user.id).count()

    if running_count >= 3:
        return {
            "success": False,
            "errors": {
                "message": f"You already have {running_count} running containers. Stop one before spawning a new instance.",
            },
        }, 403

    create_result = deps["create_container"](
        docker_config,
        image_name,
        team.name if scope == "team" and team is not None else user.name,
        deps["get_unavailable_ports"](docker_config),
    )
    if not create_result or not create_result[0] or "Id" not in create_result[0]:
        return {
            "success": False,
            "errors": {"message": "Failed to create Docker container. Verify Docker host and image settings."},
        }, 500

    port_bindings = json.loads(create_result[1]).get("HostConfig", {}).get("PortBindings", {})
    host_ports = []
    for bindings in port_bindings.values():
        if not bindings:
            continue
        host_port = bindings[0].get("HostPort")
        if host_port:
            host_ports.append(host_port)

    for host_port in host_ports:
        try:
            deps["add_port_forward"](host_port, docker_config.display_host)
        except Exception:
            continue

    now = int(datetime.utcnow().timestamp())
    max_timer = _resolve_machine_timer_cap(cve, docker_config)
    tiers = _timer_tiers_for_cap(max_timer)
    initial_timer = tiers[0]
    challenge_key = f"cve:{slug}"
    tracker = deps["DockerChallengeTracker"](
        team_id=team.id if scope == "team" and team is not None else None,
        user_id=user.id if scope != "team" else None,
        docker_image=image_name,
        timestamp=now,
        revert_time=now + initial_timer,
        instance_id=create_result[0]["Id"],
        ports=",".join(host_ports),
        host=(docker_config.display_host or str(docker_config.hostname).split(":")[0]),
        challenge=challenge_key,
    )
    db.session.add(tracker)
    db.session.commit()

    return {
        "success": True,
        "data": _build_cve_docker_status(slug, cve),
        "message": (
            f"Container reverted. Timer set to {initial_timer // 60} minutes."
            if did_revert
            else f"Container started. Timer set to {initial_timer // 60} minutes."
        ),
    }


@prolabs.route("/api/v1/cves/<slug>/submit", methods=["POST"])
@authed_only
def cves_submit(slug):
    req = request.form or request.get_json(silent=True) or {}
    entry_id = (req.get("entry_id") or "main-flag").strip()
    answer = (req.get("answer") or "").strip()

    if not answer:
        return {"success": False, "errors": {"message": "Missing answer"}}, 400

    cves = get_cves()
    cve = next((item for item in cves if item["slug"] == slug), None)
    if not cve:
        return {"success": False, "errors": {"message": "CVE not found"}}, 404

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    if not (ctftime() or is_admin()):
        return {"success": False, "errors": {"message": "Submissions are closed"}}, 403

    scoped_query = CVESubmission.query.filter_by(cve_slug=slug, entry_id=entry_id)
    if scope == "team":
        scoped_query = scoped_query.filter_by(team_id=team.id)
    else:
        scoped_query = scoped_query.filter_by(user_id=user.id)

    existing = scoped_query.first()
    if existing is not None and existing.status == "correct":
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this CVE",
                "total_score": _get_current_account_score(),
            },
        }

    expected = cve.get("flag", "")
    is_correct = expected and answer == expected
    points = _safe_points(cve.get("points", 0))

    if existing is None:
        row = CVESubmission(
            cve_slug=slug,
            entry_id=entry_id,
            provided=answer,
            status="correct" if is_correct else "incorrect",
            ip=get_ip(req=request),
            user_id=user.id,
            team_id=team.id if team else None,
        )
        db.session.add(row)
    else:
        existing.provided = answer
        existing.status = "correct" if is_correct else "incorrect"
        existing.ip = get_ip(req=request)
        existing.user_id = user.id
        existing.team_id = team.id if team else None
        existing.date = datetime.utcnow()

    if is_correct and points > 0:
        db.session.add(
            Awards(
                user_id=user.id,
                team_id=team.id if team else None,
                name=f"{cve['title']} - Flag"[:80],
                description=f"Solved {cve.get('cve_id') or cve['title']}",
                value=points,
                category="CVE Labs",
                icon="fas fa-bug",
            )
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this CVE",
                "total_score": _get_current_account_score(),
            },
        }

    if is_correct:
        if points > 0:
            clear_standings()
        return {
            "success": True,
            "data": {
                "status": "correct",
                "message": f"Correct (+{points} pts)" if points > 0 else "Correct",
                "points": points,
                "total_score": _get_current_account_score(),
            },
        }

    return {
        "success": True,
        "data": {
            "status": "incorrect",
            "message": "Incorrect",
            "total_score": _get_current_account_score(),
        },
    }


@prolabs.route("/sherlocks", methods=["GET"])
@authed_only
def sherlocks_listing():
    sherlocks = get_sherlocks()
    for sherlock in sherlocks:
        sherlock["progress"] = _get_sherlock_progress(sherlock)
    return render_template("sherlocks/list.html", sherlocks=sherlocks)


@prolabs.route("/sherlocks/<slug>", methods=["GET"])
@authed_only
def sherlocks_detail(slug):
    sherlocks = get_sherlocks()
    sherlock = next((item for item in sherlocks if item["slug"] == slug), None)
    if not sherlock:
        abort(404)

    solved = _get_sherlock_submissions(slug)
    sherlock["solved_task_ids"] = [task_id for task_id in solved.keys()]
    sherlock["progress"] = _get_sherlock_progress(sherlock)
    sherlock["docker_status"] = _build_sherlock_docker_status(slug, sherlock)
    return render_template("sherlocks/detail.html", sherlock=sherlock)


@prolabs.route("/api/v1/sherlocks/<slug>/container", methods=["GET", "POST"])
@authed_only
def sherlocks_container(slug):
    sherlocks = get_sherlocks()
    sherlock = next((item for item in sherlocks if item["slug"] == slug), None)
    if not sherlock:
        return {"success": False, "errors": {"message": "Sherlock not found"}}, 404

    action = "status"
    if request.method == "POST":
        req = request.form or request.get_json(silent=True) or {}
        action = (req.get("action") or "status").strip().lower()
    else:
        action = (request.args.get("action") or "status").strip().lower()

    if action not in {"status", "start", "stop", "extend"}:
        return {"success": False, "errors": {"message": "Unsupported action"}}, 400

    if not sherlock.get("docker_enabled"):
        return {"success": False, "errors": {"message": "Docker is disabled for this sherlock"}}, 400
    if not sherlock.get("docker_image"):
        return {"success": False, "errors": {"message": "No Docker image configured for this sherlock"}}, 400

    deps = _get_docker_challenge_dependencies()
    if deps is None:
        return {"success": False, "errors": {"message": "Docker plugin is unavailable"}}, 503

    docker_config = deps["DockerConfig"].query.filter_by(id=1).first()
    if docker_config is None or not docker_config.hostname:
        return {"success": False, "errors": {"message": "Docker host is not configured"}}, 403

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    existing = _clean_expired_sherlock_container(
        slug,
        sherlock,
        deps,
        docker_config,
        user,
        team,
        scope,
    )

    if action == "status":
        return {"success": True, "data": _build_sherlock_docker_status(slug, sherlock)}

    if action == "extend":
        if existing is None:
            return {"success": False, "errors": {"message": "No running container to extend."}}, 400

        max_timer = _resolve_machine_timer_cap(sherlock, docker_config)
        tiers = _timer_tiers_for_cap(max_timer)
        current_tier = (
            max(0, int(existing.revert_time) - int(existing.timestamp))
            if existing.revert_time and existing.timestamp
            else tiers[0]
        )
        next_tier = next((tier for tier in tiers if tier > current_tier), None)
        if next_tier is None:
            return {
                "success": False,
                "errors": {"message": "Maximum allowed timer has been reached for this sherlock."},
                "data": _build_sherlock_docker_status(slug, sherlock),
            }, 400

        base_ts = int(existing.timestamp) if existing.timestamp else int(datetime.utcnow().timestamp())
        existing.revert_time = base_ts + next_tier
        db.session.commit()
        return {
            "success": True,
            "data": _build_sherlock_docker_status(slug, sherlock),
            "message": f"Container extended to {next_tier // 60} minutes.",
        }

    if action == "stop":
        if existing is None:
            return {
                "success": True,
                "data": _build_sherlock_docker_status(slug, sherlock),
                "message": "No running container to stop.",
            }

        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {"success": False, "errors": {"message": "Failed to stop container"}}, 500

        return {
            "success": True,
            "data": _build_sherlock_docker_status(slug, sherlock),
            "message": "Container stopped.",
        }

    did_revert = False
    if existing is not None:
        try:
            deps["delete_container"](docker_config, existing.instance_id, ports_str=existing.ports)
            deps["DockerChallengeTracker"].query.filter_by(id=existing.id).delete()
            db.session.commit()
            did_revert = True
        except Exception:
            db.session.rollback()
            return {"success": False, "errors": {"message": "Failed to revert existing container"}}, 500

    repositories = []
    try:
        repositories = deps["get_repositories"](docker_config, tags=True) or []
    except Exception:
        repositories = []

    image_name = sherlock.get("docker_image")
    if repositories:
        image_repo = image_name.split(":", 1)[0]
        if image_name not in repositories and image_repo not in repositories:
            return {
                "success": False,
                "errors": {"message": f"Docker image {image_name} is not available on the host"},
            }, 403

    if scope == "team" and team is not None:
        running_count = deps["DockerChallengeTracker"].query.filter_by(team_id=team.id).count()
    else:
        running_count = deps["DockerChallengeTracker"].query.filter_by(user_id=user.id).count()

    if running_count >= 3:
        return {
            "success": False,
            "errors": {
                "message": f"You already have {running_count} running containers. Stop one before spawning a new instance.",
            },
        }, 403

    create_result = deps["create_container"](
        docker_config,
        image_name,
        team.name if scope == "team" and team is not None else user.name,
        deps["get_unavailable_ports"](docker_config),
    )
    if not create_result or not create_result[0] or "Id" not in create_result[0]:
        return {
            "success": False,
            "errors": {"message": "Failed to create Docker container. Verify Docker host and image settings."},
        }, 500

    port_bindings = json.loads(create_result[1]).get("HostConfig", {}).get("PortBindings", {})
    host_ports = []
    for bindings in port_bindings.values():
        if not bindings:
            continue
        host_port = bindings[0].get("HostPort")
        if host_port:
            host_ports.append(host_port)

    for host_port in host_ports:
        try:
            deps["add_port_forward"](host_port, docker_config.display_host)
        except Exception:
            continue

    now = int(datetime.utcnow().timestamp())
    max_timer = _resolve_machine_timer_cap(sherlock, docker_config)
    tiers = _timer_tiers_for_cap(max_timer)
    initial_timer = tiers[0]
    challenge_key = f"sherlock:{slug}"
    tracker = deps["DockerChallengeTracker"](
        team_id=team.id if scope == "team" and team is not None else None,
        user_id=user.id if scope != "team" else None,
        docker_image=image_name,
        timestamp=now,
        revert_time=now + initial_timer,
        instance_id=create_result[0]["Id"],
        ports=",".join(host_ports),
        host=(docker_config.display_host or str(docker_config.hostname).split(":")[0]),
        challenge=challenge_key,
    )
    db.session.add(tracker)
    db.session.commit()

    return {
        "success": True,
        "data": _build_sherlock_docker_status(slug, sherlock),
        "message": (
            f"Container reverted. Timer set to {initial_timer // 60} minutes."
            if did_revert
            else f"Container started. Timer set to {initial_timer // 60} minutes."
        ),
    }


@prolabs.route("/api/v1/sherlocks/<slug>/submit", methods=["POST"])
@authed_only
def sherlocks_submit(slug):
    req = request.form or request.get_json(silent=True) or {}
    entry_id = (req.get("entry_id") or "").strip()
    answer = (req.get("answer") or "").strip()

    if not entry_id or not answer:
        return {"success": False, "errors": {"message": "Missing entry_id or answer"}}, 400

    sherlocks = get_sherlocks()
    sherlock = next((item for item in sherlocks if item["slug"] == slug), None)
    if not sherlock:
        return {"success": False, "errors": {"message": "Sherlock not found"}}, 404

    user, team, scope = _get_current_account_scope()
    if user is None:
        return {"success": False, "errors": {"message": "Authentication required"}}, 403

    if not (ctftime() or is_admin()):
        return {"success": False, "errors": {"message": "Submissions are closed"}}, 403

    task = _find_sherlock_task(sherlock, entry_id)
    if task is None:
        return {"success": False, "errors": {"message": "Unknown task"}}, 404

    scoped_query = SherlockSubmission.query.filter_by(sherlock_slug=slug, entry_id=entry_id)
    if scope == "team":
        scoped_query = scoped_query.filter_by(team_id=team.id)
    else:
        scoped_query = scoped_query.filter_by(user_id=user.id)

    existing = scoped_query.first()
    if existing is not None and existing.status == "correct":
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this task",
                "total_score": _get_current_account_score(),
                "progress": _get_sherlock_progress(sherlock),
            },
        }

    expected = task.get("answer", "")
    is_correct = expected and answer == expected
    points = _safe_points(task.get("points", 0))

    if existing is None:
        row = SherlockSubmission(
            sherlock_slug=slug,
            entry_id=entry_id,
            provided=answer,
            status="correct" if is_correct else "incorrect",
            ip=get_ip(req=request),
            user_id=user.id,
            team_id=team.id if team else None,
        )
        db.session.add(row)
    else:
        existing.provided = answer
        existing.status = "correct" if is_correct else "incorrect"
        existing.ip = get_ip(req=request)
        existing.user_id = user.id
        existing.team_id = team.id if team else None
        existing.date = datetime.utcnow()

    if is_correct and points > 0:
        db.session.add(
            Awards(
                user_id=user.id,
                team_id=team.id if team else None,
                name=f"{sherlock['title']} - {task.get('title', entry_id)}"[:80],
                description=f"Solved {entry_id} in {sherlock['title']}",
                value=points,
                category="Sherlocks",
                icon="fas fa-user-secret",
            )
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "success": True,
            "data": {
                "status": "already_solved",
                "message": "Correct but you already solved this task",
                "total_score": _get_current_account_score(),
                "progress": _get_sherlock_progress(sherlock),
            },
        }

    if is_correct:
        if points > 0:
            clear_standings()
        return {
            "success": True,
            "data": {
                "status": "correct",
                "message": f"Correct (+{points} pts)" if points > 0 else "Correct",
                "points": points,
                "total_score": _get_current_account_score(),
                "progress": _get_sherlock_progress(sherlock),
            },
        }

    return {
        "success": True,
        "data": {
            "status": "incorrect",
            "message": "Incorrect",
            "total_score": _get_current_account_score(),
            "progress": _get_sherlock_progress(sherlock),
        },
    }


@prolabs.route("/admin/sherlocks", methods=["GET"])
@admins_only
def sherlocks_admin_list():
    sherlocks = get_sherlocks()
    return render_template("sherlocks/admin_list.html", sherlocks=sherlocks)


@prolabs.route("/admin/sherlocks/add", methods=["GET", "POST"])
@admins_only
def sherlocks_admin_add():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            docker_images, docker_images_error = _get_available_docker_images()
            return render_template(
                "sherlocks/add.html",
                error="Title is required",
                docker_images=docker_images,
                docker_images_error=docker_images_error,
                difficulty_options=SHERLOCK_DIFFICULTY_OPTIONS,
            )

        base_slug = _slugify((request.form.get("slug") or "").strip() or title) or "sherlock"
        sherlocks = _load_raw_config_list(SHERLOCKS_CONFIG_KEY, DEFAULT_SHERLOCKS)
        existing_slugs = {_slugify((item or {}).get("slug", "")) for item in sherlocks if isinstance(item, dict)}
        slug = _ensure_unique_slug(base_slug, existing_slugs)

        template = json.loads(json.dumps(DEFAULT_SHERLOCKS[0] if DEFAULT_SHERLOCKS else {}))
        template["slug"] = slug
        template["title"] = title
        template["difficulty"] = _normalize_sherlock_difficulty(
            request.form.get("difficulty") or template.get("difficulty")
        )
        template["category"] = (request.form.get("category") or template.get("category") or "DFIR").strip()
        template["docker_enabled"] = _as_bool(request.form.get("docker_enabled") or "0")
        template["docker_image"] = (request.form.get("docker_image") or "").strip()
        template["docker_expiry"] = _safe_int(request.form.get("docker_expiry"), 0)

        sherlocks.append(template)
        set_config(SHERLOCKS_CONFIG_KEY, json.dumps(sherlocks))
        return redirect(url_for("prolabs.sherlocks_admin_manage", saved=1, _anchor=f"sherlock-{slug}"))

    docker_images, docker_images_error = _get_available_docker_images()
    return render_template(
        "sherlocks/add.html",
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        difficulty_options=SHERLOCK_DIFFICULTY_OPTIONS,
    )


@prolabs.route("/admin/sherlocks/manage", methods=["GET", "POST"])
@admins_only
def sherlocks_admin_manage():
    if request.method == "POST":
        slugs = request.form.getlist("slug[]")
        titles = request.form.getlist("title[]")
        difficulties = request.form.getlist("difficulty[]")
        categories = request.form.getlist("category[]")
        ratings = request.form.getlist("rating[]")
        rating_counts = request.form.getlist("rating_count[]")
        solves = request.form.getlist("solves[]")
        release_dates = request.form.getlist("release_date[]")
        descriptions = request.form.getlist("description[]")
        tasks_values = request.form.getlist("tasks[]")
        docker_enabled_values = request.form.getlist("docker_enabled[]")
        docker_images = request.form.getlist("docker_image[]")
        docker_expiry_values = request.form.getlist("docker_expiry[]")

        row_count = max(
            len(slugs),
            len(titles),
            len(difficulties),
            len(categories),
            len(descriptions),
            len(tasks_values),
            len(docker_enabled_values),
            len(docker_images),
        )

        sherlocks = []
        for i in range(row_count):
            title = (titles[i] if i < len(titles) else "").strip()
            if not title:
                continue

            slug = _slugify((slugs[i] if i < len(slugs) else "").strip() or title)
            try:
                parsed_tasks = json.loads(tasks_values[i] if i < len(tasks_values) else "[]")
            except Exception:
                parsed_tasks = []

            sherlocks.append(
                {
                    "slug": slug,
                    "title": title,
                    "difficulty": _normalize_sherlock_difficulty(
                        difficulties[i] if i < len(difficulties) else "Very Easy"
                    ),
                    "category": (categories[i] if i < len(categories) else "DFIR").strip(),
                    "rating": float(ratings[i]) if i < len(ratings) and ratings[i] else 0,
                    "rating_count": _safe_int(rating_counts[i] if i < len(rating_counts) else 0, 0),
                    "solves": _safe_int(solves[i] if i < len(solves) else 0, 0),
                    "release_date": (release_dates[i] if i < len(release_dates) else "").strip(),
                    "description": (descriptions[i] if i < len(descriptions) else "").strip(),
                    "tasks": _normalize_sherlock_tasks(parsed_tasks),
                    "docker_enabled": _as_bool(
                        docker_enabled_values[i] if i < len(docker_enabled_values) else "0"
                    ),
                    "docker_image": (docker_images[i] if i < len(docker_images) else "").strip(),
                    "docker_expiry": _safe_int(
                        docker_expiry_values[i] if i < len(docker_expiry_values) else 0,
                        0,
                    ),
                }
            )

        if not sherlocks:
            sherlocks = DEFAULT_SHERLOCKS

        set_config(SHERLOCKS_CONFIG_KEY, json.dumps(sherlocks))
        return redirect(url_for("prolabs.sherlocks_admin_manage", saved=1))

    sherlocks = get_sherlocks()
    docker_images, docker_images_error = _get_available_docker_images()
    return render_template(
        "sherlocks/admin.html",
        sherlocks=sherlocks,
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        difficulty_options=SHERLOCK_DIFFICULTY_OPTIONS,
    )


@prolabs.route("/admin/machines", methods=["GET"])
@admins_only
def machines_admin_list():
    machines = get_boot2root_machines()
    return render_template("machines/admin_list.html", machines=machines)


@prolabs.route("/admin/machines/add", methods=["GET", "POST"])
@admins_only
def machines_admin_add():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            docker_images, docker_images_error = _get_available_docker_images()
            return render_template(
                "machines/add.html",
                error="Title is required",
                docker_images=docker_images,
                docker_images_error=docker_images_error,
                difficulty_options=MACHINE_DIFFICULTY_OPTIONS,
                os_options=MACHINE_OS_OPTIONS,
            )

        base_slug = _slugify((request.form.get("slug") or "").strip() or title) or "machine"
        machines = _load_raw_config_list(MACHINES_CONFIG_KEY, DEFAULT_BOOT2ROOT_MACHINES)
        existing_slugs = {_slugify((item or {}).get("slug", "")) for item in machines if isinstance(item, dict)}
        slug = _ensure_unique_slug(base_slug, existing_slugs)

        template = json.loads(json.dumps(DEFAULT_BOOT2ROOT_MACHINES[0] if DEFAULT_BOOT2ROOT_MACHINES else {}))
        guided_raw = (request.form.get("guided_questions") or "[]").strip()
        try:
            parsed_guided = json.loads(guided_raw)
        except Exception:
            parsed_guided = []

        uploaded_files = request.files.getlist("walkthrough_files[]")
        uploaded_rows = []
        for file_obj in uploaded_files:
            if not file_obj or not getattr(file_obj, "filename", ""):
                continue
            safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", file_obj.filename)
            unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{safe_name}"
            location = f"machines/{slug}-{unique_name}"
            try:
                uploaded = uploads.upload_file(file=file_obj, location=location)
                uploaded_rows.append(
                    {
                        "name": file_obj.filename,
                        "location": uploaded.location,
                    }
                )
            except Exception:
                continue

        template["slug"] = slug
        template["title"] = title
        template["difficulty"] = _normalize_machine_difficulty(
            request.form.get("difficulty") or template.get("difficulty")
        )
        template["os"] = _normalize_os(request.form.get("os") or template.get("os"))
        template["release_date"] = (request.form.get("release_date") or template.get("release_date") or "").strip()
        template["rating"] = _safe_float(request.form.get("rating"), _safe_float(template.get("rating"), 0.0))
        template["rating_count"] = _safe_int(request.form.get("rating_count"), _safe_int(template.get("rating_count"), 0))
        template["user_solves"] = _safe_int(request.form.get("user_solves"), _safe_int(template.get("user_solves"), 0))
        template["root_solves"] = _safe_int(request.form.get("root_solves"), _safe_int(template.get("root_solves"), 0))
        template["user_points"] = _safe_points(request.form.get("user_points") or template.get("user_points", 50))
        template["root_points"] = _safe_points(request.form.get("root_points") or template.get("root_points", 100))
        template["user_flag"] = (request.form.get("user_flag") or "").strip()
        template["root_flag"] = (request.form.get("root_flag") or "").strip()
        template["machine_info"] = (request.form.get("machine_info") or template.get("machine_info") or "").strip()
        template["walkthrough"] = (request.form.get("walkthrough") or template.get("walkthrough") or "").strip()
        template["guided_questions"] = _normalize_guided_questions(parsed_guided)
        template["walkthrough_files"] = uploaded_rows
        template["docker_enabled"] = _as_bool(request.form.get("docker_enabled") or "0")
        template["docker_image"] = (request.form.get("docker_image") or "").strip()
        template["docker_expiry"] = _safe_int(request.form.get("docker_expiry"), 0)

        machines.append(template)
        set_config(MACHINES_CONFIG_KEY, json.dumps(machines))
        return redirect(url_for("prolabs.machines_admin_manage", saved=1, _anchor=f"machine-{slug}"))

    docker_images, docker_images_error = _get_available_docker_images()
    return render_template(
        "machines/add.html",
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        difficulty_options=MACHINE_DIFFICULTY_OPTIONS,
        os_options=MACHINE_OS_OPTIONS,
    )


@prolabs.route("/admin/machines/manage", methods=["GET", "POST"])
@admins_only
def machines_admin_manage():
    if request.method == "POST":
        slugs = request.form.getlist("slug[]")
        titles = request.form.getlist("title[]")
        difficulties = request.form.getlist("difficulty[]")
        os_values = request.form.getlist("os[]")
        ratings = request.form.getlist("rating[]")
        rating_counts = request.form.getlist("rating_count[]")
        user_solves = request.form.getlist("user_solves[]")
        root_solves = request.form.getlist("root_solves[]")
        release_dates = request.form.getlist("release_date[]")
        machine_infos = request.form.getlist("machine_info[]")
        walkthroughs = request.form.getlist("walkthrough[]")
        user_flags = request.form.getlist("user_flag[]")
        root_flags = request.form.getlist("root_flag[]")
        user_points = request.form.getlist("user_points[]")
        root_points = request.form.getlist("root_points[]")
        docker_enabled_values = request.form.getlist("docker_enabled[]")
        docker_images = request.form.getlist("docker_image[]")
        docker_expiry_values = request.form.getlist("docker_expiry[]")
        guided_questions = request.form.getlist("guided_questions[]")
        existing_walkthrough_files = request.form.getlist("existing_walkthrough_files[]")

        row_count = max(
            len(slugs),
            len(titles),
            len(difficulties),
            len(os_values),
            len(machine_infos),
            len(walkthroughs),
            len(user_flags),
            len(root_flags),
            len(docker_enabled_values),
            len(docker_images),
        )

        machines = []
        for i in range(row_count):
            title = (titles[i] if i < len(titles) else "").strip()
            if not title:
                continue

            slug = _slugify((slugs[i] if i < len(slugs) else "").strip() or title)
            existing_files = _normalize_walkthrough_files(
                existing_walkthrough_files[i] if i < len(existing_walkthrough_files) else "[]"
            )

            uploaded_files = request.files.getlist(f"walkthrough_files_{i}[]")
            uploaded_rows = []
            for file_obj in uploaded_files:
                if not file_obj or not getattr(file_obj, "filename", ""):
                    continue
                safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", file_obj.filename)
                unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{safe_name}"
                location = f"machines/{slug}-{unique_name}"
                try:
                    uploaded = uploads.upload_file(file=file_obj, location=location)
                    uploaded_rows.append(
                        {
                            "name": file_obj.filename,
                            "location": uploaded.location,
                        }
                    )
                except Exception:
                    continue

            combined_files = existing_files + uploaded_rows

            try:
                parsed_guided = json.loads(guided_questions[i] if i < len(guided_questions) else "[]")
            except Exception:
                parsed_guided = []

            machine = {
                "slug": slug,
                "title": title,
                "difficulty": _normalize_machine_difficulty(
                    difficulties[i] if i < len(difficulties) else "Easy"
                ),
                "os": _normalize_os(os_values[i] if i < len(os_values) else "Linux"),
                "rating": float(ratings[i]) if i < len(ratings) and ratings[i] else 0,
                "rating_count": _safe_int(rating_counts[i] if i < len(rating_counts) else 0, 0),
                "user_solves": _safe_int(user_solves[i] if i < len(user_solves) else 0, 0),
                "root_solves": _safe_int(root_solves[i] if i < len(root_solves) else 0, 0),
                "release_date": (release_dates[i] if i < len(release_dates) else "").strip(),
                "machine_info": (machine_infos[i] if i < len(machine_infos) else "").strip(),
                "walkthrough": (walkthroughs[i] if i < len(walkthroughs) else "").strip(),
                "walkthrough_files": combined_files,
                "user_flag": (user_flags[i] if i < len(user_flags) else "").strip(),
                "root_flag": (root_flags[i] if i < len(root_flags) else "").strip(),
                "user_points": _safe_points(user_points[i] if i < len(user_points) else 50),
                "root_points": _safe_points(root_points[i] if i < len(root_points) else 100),
                "guided_questions": _normalize_guided_questions(parsed_guided),
                "docker_enabled": _as_bool(
                    docker_enabled_values[i] if i < len(docker_enabled_values) else "0"
                ),
                "docker_image": (docker_images[i] if i < len(docker_images) else "").strip(),
                "docker_expiry": _safe_int(
                    docker_expiry_values[i] if i < len(docker_expiry_values) else 0,
                    0,
                ),
            }
            machines.append(machine)

        if not machines:
            machines = DEFAULT_BOOT2ROOT_MACHINES

        set_config(MACHINES_CONFIG_KEY, json.dumps(machines))
        return redirect(url_for("prolabs.machines_admin_manage", saved=1))

    machines = get_boot2root_machines()
    docker_images, docker_images_error = _get_available_docker_images()
    return render_template(
        "machines/admin.html",
        machines=machines,
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        difficulty_options=MACHINE_DIFFICULTY_OPTIONS,
        os_options=MACHINE_OS_OPTIONS,
    )


@prolabs.route("/admin/cves", methods=["GET"])
@admins_only
def cves_admin_list():
    cves = get_cves()
    return render_template("cves/admin_list.html", cves=cves)


@prolabs.route("/admin/cves/add", methods=["GET", "POST"])
@admins_only
def cves_admin_add():
    docker_images, docker_images_error = _get_available_docker_images()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            return render_template(
                "cves/add.html",
                error="Title is required",
                docker_images=docker_images,
                docker_images_error=docker_images_error,
                severity_options=CVE_SEVERITY_OPTIONS,
            )

        base_slug = _slugify((request.form.get("slug") or "").strip() or title) or "cve"
        cves = _load_raw_config_list(CVES_CONFIG_KEY, DEFAULT_CVES)
        existing_slugs = {_slugify((item or {}).get("slug", "")) for item in cves if isinstance(item, dict)}
        slug = _ensure_unique_slug(base_slug, existing_slugs)

        template = json.loads(json.dumps(DEFAULT_CVES[0] if DEFAULT_CVES else {}))
        template["slug"] = slug
        template["title"] = title
        template["cve_id"] = (request.form.get("cve_id") or "").strip()
        template["severity"] = _normalize_cve_severity(request.form.get("severity") or "Medium")
        template["category"] = (request.form.get("category") or "Web").strip()
        template["cvss"] = _safe_float(request.form.get("cvss"), 0.0)
        template["release_date"] = (request.form.get("release_date") or "").strip()
        template["short_description"] = (request.form.get("short_description") or "").strip()
        template["description"] = (request.form.get("description") or "").strip()
        template["flag"] = (request.form.get("flag") or "").strip()
        template["points"] = _safe_points(request.form.get("points") or 0)
        template["docker_enabled"] = _as_bool(request.form.get("docker_enabled"))
        template["docker_image"] = (request.form.get("docker_image") or "").strip()
        template["docker_expiry"] = _safe_int(request.form.get("docker_expiry"), 0)
        template["references"] = _normalize_cve_references(request.form.get("references") or "[]")

        cves.append(template)
        set_config(CVES_CONFIG_KEY, json.dumps(cves))
        return redirect(url_for("prolabs.cves_admin_manage", saved=1, _anchor=f"cve-{slug}"))

    return render_template(
        "cves/add.html",
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        severity_options=CVE_SEVERITY_OPTIONS,
    )


@prolabs.route("/admin/cves/manage", methods=["GET", "POST"])
@admins_only
def cves_admin_manage():
    if request.method == "POST":
        slugs = request.form.getlist("slug[]")
        titles = request.form.getlist("title[]")
        cve_ids = request.form.getlist("cve_id[]")
        severities = request.form.getlist("severity[]")
        categories = request.form.getlist("category[]")
        cvss_values = request.form.getlist("cvss[]")
        release_dates = request.form.getlist("release_date[]")
        short_descriptions = request.form.getlist("short_description[]")
        descriptions = request.form.getlist("description[]")
        flags = request.form.getlist("flag[]")
        points_values = request.form.getlist("points[]")
        docker_enabled_values = request.form.getlist("docker_enabled[]")
        docker_image_values = request.form.getlist("docker_image[]")
        docker_expiry_values = request.form.getlist("docker_expiry[]")
        references_values = request.form.getlist("references[]")

        row_count = max(
            len(slugs),
            len(titles),
            len(cve_ids),
            len(severities),
            len(categories),
            len(cvss_values),
            len(descriptions),
            len(flags),
            len(points_values),
        )

        cves = []
        for i in range(row_count):
            title = (titles[i] if i < len(titles) else "").strip()
            if not title:
                continue

            slug = _slugify((slugs[i] if i < len(slugs) else "").strip() or title)
            cves.append(
                {
                    "slug": slug,
                    "title": title,
                    "cve_id": (cve_ids[i] if i < len(cve_ids) else "").strip(),
                    "severity": _normalize_cve_severity(
                        severities[i] if i < len(severities) else "Medium"
                    ),
                    "category": (categories[i] if i < len(categories) else "Web").strip(),
                    "cvss": _safe_float(cvss_values[i] if i < len(cvss_values) else 0, 0.0),
                    "release_date": (release_dates[i] if i < len(release_dates) else "").strip(),
                    "short_description": (
                        short_descriptions[i] if i < len(short_descriptions) else ""
                    ).strip(),
                    "description": (descriptions[i] if i < len(descriptions) else "").strip(),
                    "flag": (flags[i] if i < len(flags) else "").strip(),
                    "points": _safe_points(points_values[i] if i < len(points_values) else 0),
                    "docker_enabled": _as_bool(
                        docker_enabled_values[i] if i < len(docker_enabled_values) else False
                    ),
                    "docker_image": (
                        docker_image_values[i] if i < len(docker_image_values) else ""
                    ).strip(),
                    "docker_expiry": _safe_int(
                        docker_expiry_values[i] if i < len(docker_expiry_values) else 0,
                        0,
                    ),
                    "references": _normalize_cve_references(
                        references_values[i] if i < len(references_values) else "[]"
                    ),
                }
            )

        if not cves:
            cves = DEFAULT_CVES

        set_config(CVES_CONFIG_KEY, json.dumps(cves))
        return redirect(url_for("prolabs.cves_admin_manage", saved=1))

    cves = get_cves()
    docker_images, docker_images_error = _get_available_docker_images()
    return render_template(
        "cves/admin.html",
        cves=cves,
        docker_images=docker_images,
        docker_images_error=docker_images_error,
        severity_options=CVE_SEVERITY_OPTIONS,
    )




def _get_dashboard_stats_for_scope(target_user=None):
    """Build dashboard metrics/charts using real account/team data."""
    if target_user is not None:
        user = target_user
        team = None
        scope = "user"
    else:
        user, team, scope = _get_current_account_scope()

    if user is None:
        return None

    account_id = user.id
    account_name = user.name
    scope_filter = {"user_id": user.id}
    if scope == "team" and team is not None:
        account_id = team.id
        account_name = team.name
        scope_filter = {"team_id": team.id}

    def _build_months():
        now = datetime.utcnow()
        items = []
        for i in range(11, -1, -1):
            ref = now - timedelta(days=30 * i)
            items.append((ref.year, ref.month))
        return items

    def _build_timeline(dates):
        months = _build_months()
        counts = {f"{year:04d}-{month:02d}": 0 for year, month in months}
        for dt in dates:
            if not dt:
                continue
            key = f"{dt.year:04d}-{dt.month:02d}"
            if key in counts:
                counts[key] += 1

        labels = []
        values = []
        for year, month in months:
            key = f"{year:04d}-{month:02d}"
            labels.append(datetime(year, month, 1).strftime("%b"))
            values.append(counts.get(key, 0))
        return {"labels": labels, "values": values}

    difficulty_order = ["Very Easy", "Easy", "Medium", "Hard", "Insane"]

    # Core totals
    prolab_correct = ProLabSubmission.query.filter_by(status="correct", **scope_filter).count()
    machine_user_correct = Boot2RootSubmission.query.filter_by(
        status="correct", entry_id="user-flag", **scope_filter
    ).count()
    machine_root_correct = Boot2RootSubmission.query.filter_by(
        status="correct", entry_id="root-flag", **scope_filter
    ).count()
    sherlock_correct = SherlockSubmission.query.filter_by(status="correct", **scope_filter).count()
    cve_correct = CVESubmission.query.filter_by(
        status="correct", entry_id="main-flag", **scope_filter
    ).count()
    challenge_solves = Solves.query.filter_by(**scope_filter).count()

    total_prolabs = len(get_prolabs())
    total_machines = len(get_boot2root_machines())
    total_sherlocks = len(get_sherlocks())
    total_cves = len(get_cves())
    total_challenges = Challenges.query.filter_by(state="visible").count()

    if target_user is not None:
        current_score = max(0, _safe_int(get_user_score(user.id), 0))
    else:
        current_score = _get_current_account_score()

    # Global rank
    global_rank = None
    try:
        standings = get_standings(admin=True)
        for idx, standing in enumerate(standings, start=1):
            if standing.account_id == account_id:
                global_rank = idx
                break
    except Exception:
        global_rank = None

    # Pro labs list + summary (Fortresses intentionally excluded from summary tiles)
    prolabs_data = []
    category_summary = {
        "Pro Labs": {"completed": 0, "total": 0},
        "Mini Pro Labs": {"completed": 0, "total": 0},
        "CVEs": {"completed": 0, "total": 0},
    }
    for lab in get_prolabs():
        slug = lab.get("slug")
        category = lab.get("category", "Pro Labs")
        total_flags = len(lab.get("flags", []))
        solved_flags = ProLabSubmission.query.filter_by(
            lab_slug=slug, status="correct", **scope_filter
        ).count()
        completion = (solved_flags / total_flags * 100) if total_flags > 0 else 0

        if category in category_summary:
            category_summary[category]["total"] += 1
            if completion >= 100:
                category_summary[category]["completed"] += 1

        prolabs_data.append(
            {
                "title": lab.get("title"),
                "slug": slug,
                "category": category,
                "logo_image": lab.get("logo_image", ""),
                "completion": completion,
                "solved": solved_flags,
                "total": total_flags,
            }
        )
    prolabs_data.sort(key=lambda item: item.get("completion", 0), reverse=True)

    # CVE data + graphs (merged into category views and lab row)
    cve_rows = CVESubmission.query.filter_by(
        status="correct", entry_id="main-flag", **scope_filter
    ).all()
    cve_dates = [row.date for row in cve_rows if row.date]
    solved_cve_slugs = {row.cve_slug for row in cve_rows if row.cve_slug}

    cves_data = []
    cve_severity_order = ["Critical", "High", "Medium", "Low"]
    cve_difficulty_totals = {name: 0 for name in cve_severity_order}
    cve_difficulty_solved = {name: 0 for name in cve_severity_order}
    for cve in get_cves():
        slug = cve.get("slug")
        solved = slug in solved_cve_slugs
        severity = (cve.get("severity") or "Medium").strip().title()
        if severity not in cve_difficulty_totals:
            severity = "Medium"

        cves_data.append(
            {
                "title": cve.get("title"),
                "slug": slug,
                "completion": 100 if solved else 0,
                "subtext": cve.get("cve_id") or severity,
                "logo_image": "",
                "category": "CVEs",
                "solved": 1 if solved else 0,
                "total": 1,
            }
        )

        cve_difficulty_totals[severity] += 1
        if solved:
            cve_difficulty_solved[severity] += 1

        category_summary["CVEs"]["total"] += 1
        if solved:
            category_summary["CVEs"]["completed"] += 1

    cves_data.sort(key=lambda item: item.get("completion", 0), reverse=True)
    prolabs_data.extend(cves_data)

    cve_difficulty_completion = []
    for name in cve_severity_order:
        total = cve_difficulty_totals[name]
        solved = cve_difficulty_solved[name]
        cve_difficulty_completion.append(
            {
                "name": name,
                "solved": solved,
                "total": total,
                "percentage": (solved / total * 100) if total > 0 else 0,
            }
        )

    # Machines data + graphs
    machine_rows = Boot2RootSubmission.query.filter_by(
        status="correct", entry_id="user-flag", **scope_filter
    ).all()
    solved_machine_slugs = {row.machine_slug for row in machine_rows}

    machines_data = []
    machine_difficulty_totals = {name: 0 for name in difficulty_order}
    machine_difficulty_solved = {name: 0 for name in difficulty_order}
    for machine in get_boot2root_machines():
        slug = machine.get("slug")
        user_solved = slug in solved_machine_slugs
        root_solved = (
            Boot2RootSubmission.query.filter_by(
                machine_slug=slug,
                entry_id="root-flag",
                status="correct",
                **scope_filter,
            ).first()
            is not None
        )
        completion = 100 if (user_solved and root_solved) else (50 if (user_solved or root_solved) else 0)
        machines_data.append(
            {
                "title": machine.get("title"),
                "slug": slug,
                "completion": completion,
                "subtext": "User + Root" if completion == 100 else "Progress",
            }
        )

        difficulty = (machine.get("difficulty") or "Easy").strip()
        if difficulty in machine_difficulty_totals:
            machine_difficulty_totals[difficulty] += 1
            if user_solved:
                machine_difficulty_solved[difficulty] += 1
    machines_data.sort(key=lambda item: item.get("completion", 0), reverse=True)

    machine_difficulty_completion = []
    for name in difficulty_order:
        total = machine_difficulty_totals[name]
        solved = machine_difficulty_solved[name]
        machine_difficulty_completion.append(
            {
                "name": name,
                "solved": solved,
                "total": total,
                "percentage": (solved / total * 100) if total > 0 else 0,
            }
        )

    # Sherlock data + graphs
    sherlock_rows = SherlockSubmission.query.filter_by(status="correct", **scope_filter).all()
    sherlock_dates = [row.date for row in sherlock_rows if row.date]

    sherlocks_data = []
    sherlock_difficulty_totals = {name: 0 for name in difficulty_order}
    sherlock_difficulty_solved = {name: 0 for name in difficulty_order}
    for sherlock in get_sherlocks():
        slug = sherlock.get("slug")
        total_tasks = len(sherlock.get("tasks", []))
        solved_tasks = SherlockSubmission.query.filter_by(
            sherlock_slug=slug, status="correct", **scope_filter
        ).count()
        completion = (solved_tasks / total_tasks * 100) if total_tasks > 0 else 0
        sherlocks_data.append(
            {
                "title": sherlock.get("title"),
                "slug": slug,
                "completion": completion,
                "subtext": f"{solved_tasks}/{total_tasks} tasks",
            }
        )

        difficulty = (sherlock.get("difficulty") or "Easy").strip()
        if difficulty in sherlock_difficulty_totals:
            sherlock_difficulty_totals[difficulty] += 1
            if completion >= 100:
                sherlock_difficulty_solved[difficulty] += 1
    sherlocks_data.sort(key=lambda item: item.get("completion", 0), reverse=True)

    sherlock_difficulty_completion = []
    for name in difficulty_order:
        total = sherlock_difficulty_totals[name]
        solved = sherlock_difficulty_solved[name]
        sherlock_difficulty_completion.append(
            {
                "name": name,
                "solved": solved,
                "total": total,
                "percentage": (solved / total * 100) if total > 0 else 0,
            }
        )

    # Challenge data + graphs
    visible_challenges = Challenges.query.filter_by(state="visible").all()
    solve_rows = Solves.query.filter_by(**scope_filter).all()
    solved_challenge_ids = {row.challenge_id for row in solve_rows if row.challenge_id is not None}
    challenge_dates = [row.date for row in solve_rows if row.date]

    challenges_data = []
    challenge_difficulty_totals = {name: 0 for name in difficulty_order}
    challenge_difficulty_solved = {name: 0 for name in difficulty_order}
    for chal in visible_challenges:
        solved = chal.id in solved_challenge_ids
        challenges_data.append(
            {
                "title": chal.name,
                "slug": str(chal.id),
                "completion": 100 if solved else 0,
                "subtext": chal.category or "Challenge",
            }
        )

        difficulty = (chal.difficulty or "Easy").strip()
        if difficulty in challenge_difficulty_totals:
            challenge_difficulty_totals[difficulty] += 1
            if solved:
                challenge_difficulty_solved[difficulty] += 1
    challenges_data.sort(key=lambda item: item.get("completion", 0), reverse=True)

    challenge_difficulty_completion = []
    for name in difficulty_order:
        total = challenge_difficulty_totals[name]
        solved = challenge_difficulty_solved[name]
        challenge_difficulty_completion.append(
            {
                "name": name,
                "solved": solved,
                "total": total,
                "percentage": (solved / total * 100) if total > 0 else 0,
            }
        )

    total_flags_solved = (
        prolab_correct
        + machine_user_correct
        + machine_root_correct
        + sherlock_correct
        + cve_correct
        + challenge_solves
    )

    # Category switch payload for frontend interactions
    category_views = {
        "machines": {
            "title": "Machines Completed",
            "subtitle": "Boot2Root progress over last 12 months",
            "counter": {"done": machine_user_correct, "total": total_machines},
            "timeline": _build_timeline([row.date for row in machine_rows if row.date]),
            "difficulty": machine_difficulty_completion,
            "list": machines_data,
        },
        "sherlocks": {
            "title": "Sherlocks Completed",
            "subtitle": "Investigation progress over last 12 months",
            "counter": {"done": sherlock_correct, "total": total_sherlocks},
            "timeline": _build_timeline(sherlock_dates),
            "difficulty": sherlock_difficulty_completion,
            "list": sherlocks_data,
        },
        "challenges": {
            "title": "Challenges Completed",
            "subtitle": "Challenge solves over last 12 months",
            "counter": {"done": challenge_solves, "total": total_challenges},
            "timeline": _build_timeline(challenge_dates),
            "difficulty": challenge_difficulty_completion,
            "list": challenges_data,
        },
        "cves": {
            "title": "CVEs Completed",
            "subtitle": "CVE solves over last 12 months",
            "counter": {"done": cve_correct, "total": total_cves},
            "timeline": _build_timeline(cve_dates),
            "difficulty": cve_difficulty_completion,
            "list": cves_data,
        },
    }

    return {
        "user": user,
        "team": team,
        "scope": scope,
        "account_name": account_name,
        "global_rank": global_rank,
        "current_score": current_score,
        "flags_solved": total_flags_solved,
        "prolabs": {
            "completed": prolab_correct,
            "total": total_prolabs,
            "percentage": (prolab_correct / total_prolabs * 100) if total_prolabs > 0 else 0,
            "data": prolabs_data,
            "categories": category_summary,
        },
        "machines": {
            "user_flags": machine_user_correct,
            "root_flags": machine_root_correct,
            "total": total_machines,
            "percentage": (machine_user_correct / total_machines * 100) if total_machines > 0 else 0,
        },
        "sherlocks": {
            "completed": sherlock_correct,
            "total": total_sherlocks,
            "percentage": (sherlock_correct / total_sherlocks * 100) if total_sherlocks > 0 else 0,
        },
        "challenges": {
            "completed": challenge_solves,
            "total": total_challenges,
            "percentage": (challenge_solves / total_challenges * 100) if total_challenges > 0 else 0,
        },
        "cves": {
            "completed": cve_correct,
            "total": total_cves,
            "percentage": (cve_correct / total_cves * 100) if total_cves > 0 else 0,
        },
        "category_views": category_views,
    }


@prolabs.route("/dashboard", methods=["GET"])
@authed_only
def player_dashboard():
    """Player dashboard showing stats and progress"""
    stats = _get_dashboard_stats_for_scope()
    if stats is None:
        abort(401)
    
    return render_template("prolabs/dashboard.html", stats=stats)


@prolabs.route("/admin/player-dashboard", methods=["GET"])
@admins_only
def admin_player_dashboard_list():
    users = Users.query.order_by(Users.id.asc()).all()

    rank_map = {}
    try:
        standings = get_standings(admin=True)
        for idx, standing in enumerate(standings, start=1):
            rank_map[standing.account_id] = idx
    except Exception:
        rank_map = {}

    players = []
    for user in users:
        score = max(0, _safe_int(get_user_score(user.id), 0))
        players.append(
            {
                "id": user.id,
                "name": user.name,
                "score": score,
                "rank": rank_map.get(user.id),
            }
        )

    players.sort(key=lambda item: (-item["score"], item["name"].lower()))
    return render_template("prolabs/admin_player_dashboard_list.html", players=players)


@prolabs.route("/admin/player-dashboard/<int:user_id>", methods=["GET"])
@admins_only
def admin_player_dashboard_detail(user_id):
    user = Users.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)

    stats = _get_dashboard_stats_for_scope(target_user=user)
    if stats is None:
        abort(404)

    return render_template("prolabs/dashboard.html", stats=stats, admin_view=True)


@prolabs.route("/admin/prolabs/submissions", methods=["GET"])
@admins_only
def prolab_admin_submissions():
    """Display all ProLab submissions."""
    page = abs(request.args.get("page", 1, type=int))
    submissions = ProLabSubmission.query.order_by(ProLabSubmission.date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    labs = {lab["slug"]: lab["title"] for lab in get_prolabs()}
    
    return render_template(
        "prolabs/admin_submissions.html",
        submissions=submissions,
        labs=labs,
        type="ProLabs",
        prev_page=request.endpoint and url_for(request.endpoint, page=submissions.prev_num) or "#",
        next_page=request.endpoint and url_for(request.endpoint, page=submissions.next_num) or "#",
    )


@prolabs.route("/admin/machines/submissions", methods=["GET"])
@admins_only
def machines_admin_submissions():
    """Display all Machine submissions."""
    page = abs(request.args.get("page", 1, type=int))
    submissions = Boot2RootSubmission.query.order_by(Boot2RootSubmission.date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    machines = {m["slug"]: m["title"] for m in get_boot2root_machines()}
    
    return render_template(
        "machines/admin_submissions.html",
        submissions=submissions,
        machines=machines,
        type="Machines",
        prev_page=request.endpoint and url_for(request.endpoint, page=submissions.prev_num) or "#",
        next_page=request.endpoint and url_for(request.endpoint, page=submissions.next_num) or "#",
    )


@prolabs.route("/admin/sherlocks/submissions", methods=["GET"])
@admins_only
def sherlocks_admin_submissions():
    """Display all Sherlock submissions."""
    page = abs(request.args.get("page", 1, type=int))
    submissions = SherlockSubmission.query.order_by(SherlockSubmission.date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    sherlocks = {s["slug"]: s["title"] for s in get_sherlocks()}
    
    return render_template(
        "sherlocks/admin_submissions.html",
        submissions=submissions,
        sherlocks=sherlocks,
        type="Sherlocks",
        prev_page=request.endpoint and url_for(request.endpoint, page=submissions.prev_num) or "#",
        next_page=request.endpoint and url_for(request.endpoint, page=submissions.next_num) or "#",
    )


@prolabs.route("/admin/cves/submissions", methods=["GET"])
@admins_only
def cves_admin_submissions():
    """Display all CVE submissions."""
    page = abs(request.args.get("page", 1, type=int))
    submissions = CVESubmission.query.order_by(CVESubmission.date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    cves = {c["slug"]: c["title"] for c in get_cves()}

    return render_template(
        "cves/admin_submissions.html",
        submissions=submissions,
        cves=cves,
        type="CVEs",
        prev_page=request.endpoint and url_for(request.endpoint, page=submissions.prev_num) or "#",
        next_page=request.endpoint and url_for(request.endpoint, page=submissions.next_num) or "#",
    )


def load(app):
    with app.app_context():
        db.create_all()
    app.register_blueprint(prolabs)
    register_admin_plugin_menu_bar("Pro Labs", "/admin/prolabs")
    register_admin_plugin_menu_bar("Pro Lab Levels", "/admin/prolabs/levels")
    register_admin_plugin_menu_bar("Pro Lab Submissions", "/admin/prolabs/submissions")
    register_admin_plugin_menu_bar("Machines", "/admin/machines")
    register_admin_plugin_menu_bar("Machine Submissions", "/admin/machines/submissions")
    register_admin_plugin_menu_bar("Sherlocks", "/admin/sherlocks")
    register_admin_plugin_menu_bar("Sherlock Submissions", "/admin/sherlocks/submissions")
    register_admin_plugin_menu_bar("CVEs", "/admin/cves")
    register_admin_plugin_menu_bar("CVE Submissions", "/admin/cves/submissions")
    register_admin_plugin_menu_bar("Player Dashboards", "/admin/player-dashboard")

    @app.context_processor
    def inject_prolab_level_helpers():
        level_rules = get_level_rules()
        return {
            "prolab_level_rules": level_rules,
            "get_level_name_for_score": lambda score: get_level_name_for_score(
                score, level_rules=level_rules
            ),
        }
