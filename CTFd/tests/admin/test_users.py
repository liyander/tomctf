#!/usr/bin/env python
# -*- coding: utf-8 -*-

from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from CTFd.models import UserFieldEntries
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_field,
    gen_tracking,
    gen_user,
    login_as_user,
)


def test_admin_user_ip_search():
    """Can an admin search user IPs"""
    app = create_ctfd()
    with app.app_context():
        u1 = gen_user(app.db, name="user1", email="user1@examplectf.com")
        gen_tracking(app.db, user_id=u1.id, ip="1.1.1.1")

        u2 = gen_user(app.db, name="user2", email="user2@examplectf.com")
        gen_tracking(app.db, user_id=u2.id, ip="2.2.2.2")

        u3 = gen_user(app.db, name="user3", email="user3@examplectf.com")
        gen_tracking(app.db, user_id=u3.id, ip="3.3.3.3")

        u4 = gen_user(app.db, name="user4", email="user4@examplectf.com")
        gen_tracking(app.db, user_id=u4.id, ip="3.3.3.3")
        gen_tracking(app.db, user_id=u4.id, ip="4.4.4.4")

        with login_as_user(app, name="admin", password="password") as admin:
            r = admin.get("/admin/users?field=ip&q=1.1.1.1")
            resp = r.get_data(as_text=True)
            assert "user1" in resp
            assert "user2" not in resp
            assert "user3" not in resp

            r = admin.get("/admin/users?field=ip&q=2.2.2.2")
            resp = r.get_data(as_text=True)
            assert "user1" not in resp
            assert "user2" in resp
            assert "user3" not in resp

            r = admin.get("/admin/users?field=ip&q=3.3.3.3")
            resp = r.get_data(as_text=True)
            assert "user1" not in resp
            assert "user2" not in resp
            assert "user3" in resp
            assert "user4" in resp
    destroy_ctfd(app)


def _xlsx_text(response):
    with ZipFile(BytesIO(response.data)) as workbook:
        worksheet = ElementTree.fromstring(
            workbook.read("xl/worksheets/sheet1.xml")
        )
    return " ".join(value or "" for value in worksheet.itertext())


def test_admin_can_export_users_to_xlsx():
    app = create_ctfd()
    with app.app_context():
        visible = gen_user(
            app.db,
            name="visible-user",
            email="visible@examplectf.com",
            affiliation="Example University",
        )
        gen_user(
            app.db,
            name="hidden-user",
            email="hidden@examplectf.com",
            hidden=True,
        )
        register_number = gen_field(
            app.db,
            name="Register Number",
            type="user",
            required=False,
            public=False,
            editable=True,
        )
        app.db.session.add(
            UserFieldEntries(
                user_id=visible.id,
                field_id=register_number.id,
                value="REG-001",
            )
        )
        app.db.session.commit()

        with login_as_user(app, name="admin", password="password") as admin:
            response = admin.get("/admin/users/export.xlsx")
            assert response.status_code == 200
            assert response.mimetype == (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            assert response.headers["Content-Disposition"].endswith(".xlsx")
            exported = _xlsx_text(response)
            assert "visible-user" in exported
            assert "hidden-user" in exported
            assert "Register Number" in exported
            assert "REG-001" in exported

            response = admin.get("/admin/users/export.xlsx?exclude_hidden=1")
            exported = _xlsx_text(response)
            assert "visible-user" in exported
            assert "hidden-user" not in exported
    destroy_ctfd(app)


def test_user_cannot_export_users_to_xlsx():
    app = create_ctfd()
    with app.app_context():
        gen_user(app.db, name="regular-user", email="regular@examplectf.com")
        with login_as_user(
            app, name="regular-user", password="password"
        ) as regular_user:
            response = regular_user.get("/admin/users/export.xlsx")
            assert response.status_code == 302
            assert response.location.startswith("/login")
    destroy_ctfd(app)
