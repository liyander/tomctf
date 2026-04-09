from flask import Blueprint, render_template
from CTFd.utils.decorators import admins_only
from CTFd.plugins import register_plugin_assets_directory, register_admin_plugin_menu_bar

def load(app):
    page_visibility_bp = Blueprint('page_visibility', __name__, template_folder='templates')

    @page_visibility_bp.route('/admin/page_visibility', methods=['GET'])
    @admins_only
    def view_page_visibility_config():
        return render_template('admin/page_visibility.html')

    app.register_blueprint(page_visibility_bp)
    
    register_admin_plugin_menu_bar("Page Visibility", "/admin/page_visibility")
