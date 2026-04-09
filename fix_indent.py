import re

with open('CTFd/CTFd/plugins/page_visibility/__init__.py', 'r') as f:
    text = f.read()

text = text.replace(\"@page_visibility_bp.route('/admin/page_visibility', methods=['GET'])\", \"    @page_visibility_bp.route('/admin/page_visibility', methods=['GET'])\")

with open('CTFd/CTFd/plugins/page_visibility/__init__.py', 'w') as f:
    f.write(text)
