import re

with open('CTFd/CTFd/plugins/page_visibility/__init__.py', 'r') as f:
    content = f.read()

new_block = '''    @app.before_request
    def block_hidden_pages():
        from flask import request, redirect, url_for, jsonify
        from CTFd.utils.user import is_admin

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

        # Allow admins to access API endpoints because the Admin Panel relies on them
        if is_admin() and path.startswith('/api/v1/'):
            return

        for prefix, config_key in visibility_map.items():
            if path.startswith(prefix) and not path.startswith('/admin'):
                val = str(get_config(config_key)).lower()
                if val == 'false':
                    if path.startswith('/api/v1/'):
                        return jsonify({'success': False, 'message': 'Hidden'}), 403
                    return redirect('/')
'''

content = re.sub(r'    @app\.before_request\n\s*def block_hidden_pages\(\):[\s\S]*?return redirect\(url_for\(\'views\.static_html\', route=\'/\'\)\)\s+', new_block, content)

with open('CTFd/CTFd/plugins/page_visibility/__init__.py', 'w') as f:
    f.write(content)
