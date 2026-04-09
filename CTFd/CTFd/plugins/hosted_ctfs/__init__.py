from flask import Blueprint, render_template, request, url_for, redirect
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.models import db
from CTFd.utils import set_config, get_config
from CTFd.plugins import register_plugin_assets_directory, register_user_page_menu_bar, register_admin_plugin_menu_bar

def load(app):
    hosted_ctfs_bp = Blueprint('hosted_ctfs', __name__, template_folder='templates')
    
    @hosted_ctfs_bp.route('/admin/hosted_ctfs', methods=['GET', 'POST'])
    @admins_only
    def admin_dashboard():
        if request.method == 'POST':
            set_config('hosted_ctf_tab_name', request.form.get('tab_name', 'CTFs'))
            set_config('hosted_ctf_hero_name', request.form.get('hero_name', 'Hosted CTFs'))
            set_config('hosted_ctf_hero_desc', request.form.get('hero_desc', 'Join ongoing competitions'))
            set_config('hosted_ctf_category', request.form.get('category_filter', 'CTF'))
            set_config('hosted_ctf_visible', request.form.get('is_visible', 'true'))
            set_config('hosted_ctf_sidebar_icon', request.form.get('sidebar_icon', 'fas fa-flag-checkered'))
            return redirect(url_for('hosted_ctfs.admin_dashboard'))
            
        configs = {
            'tab_name': get_config('hosted_ctf_tab_name', 'CTFs'),
            'hero_name': get_config('hosted_ctf_hero_name', 'Hosted CTFs'),
            'hero_desc': get_config('hosted_ctf_hero_desc', 'Join ongoing competitions'),
            'category_filter': get_config('hosted_ctf_category', 'CTF'),
            'is_visible': get_config('hosted_ctf_visible', 'true'),
            'sidebar_icon': get_config('hosted_ctf_sidebar_icon', 'fas fa-flag-checkered')
        }
        return render_template('admin/hosted_ctfs.html', configs=configs)
        
    @hosted_ctfs_bp.route('/ctfs', methods=['GET'])
    @authed_only
    def user_dashboard():
        configs = {
            'tab_name': get_config('hosted_ctf_tab_name', 'CTFs'),
            'hero_name': get_config('hosted_ctf_hero_name', 'Hosted CTFs'),
            'hero_desc': get_config('hosted_ctf_hero_desc', 'Join ongoing competitions'),
            'category_filter': get_config('hosted_ctf_category', 'CTF')
        }
        return render_template('user/ctfs.html', ctfs_configs=configs)

    register_admin_plugin_menu_bar('Hosted CTFs', '/admin/hosted_ctfs')
    app.register_blueprint(hosted_ctfs_bp)
