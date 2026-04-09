from flask import Blueprint, render_template, request, redirect, url_for, jsonify, abort
from CTFd.utils.decorators import admins_only
from CTFd.utils import get_config
from CTFd.utils.user import is_admin
from CTFd.plugins import register_plugin_assets_directory, register_admin_plugin_menu_bar

def load(app):
    page_visibility_bp = Blueprint('page_visibility', __name__, template_folder='templates')

    @app.before_request
    def block_hidden_pages():
        path = request.path

        visibility_map = {
            '/dashboard': 'dashboard_visible',
            '/challenges': 'challenges_visible',
            '/api/v1/challenges': 'challenges_visible',
            '/ctfs': 'hosted_ctf_visible',
            '/api/v1/ctfs': 'hosted_ctf_visible',
            '/pro-red-team-labs': 'pro_red_team_labs_visible',
            '/machines': 'machines_visible',
            '/adversary-operations': 'adversary_operations_visible',
            '/cves': 'cves_visible',
            '/sherlocks': 'sherlocks_visible',
            '/api/v1/sherlocks': 'sherlocks_visible',
            '/credits': 'credits_visible',
        }

        # Let the admin fetch from API (e.g., config data/creation)
        if is_admin() and path.startswith('/api/v1/'):
            return

        for prefix, config_key in visibility_map.items():
            if path.startswith(prefix) and not path.startswith('/admin'):
                val = str(get_config(config_key)).lower()
                if val == 'false':
                    if path.startswith('/api/v1/'):
                        return jsonify({"success": False, "message": "Hidden"}), 403
                    abort(404)

    @page_visibility_bp.route('/admin/page_visibility', methods=['GET'])
    @admins_only
    def view_page_visibility_config():
        return render_template('admin/page_visibility.html')

    app.register_blueprint(page_visibility_bp)

    register_admin_plugin_menu_bar("Page Visibility", "/admin/page_visibility")
