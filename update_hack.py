import sys

files = [
    r'C:\Users\Liyander\Downloads\TomCTF\CTFd\CTFd\themes\admin\templates\challenges\new.html',
    r'C:\Users\Liyander\Downloads\TomCTF\CTFd\CTFd\themes\admin\templates\challenges\challenge.html'
]

replacement = '''document.addEventListener("DOMContentLoaded", function() {
    const hostedCategory = "{{ Configs.hosted_ctf_category or 'CTF' }}";

    setInterval(() => {
        const catInput = document.querySelector('input[name="category"]');
        if (catInput && !document.getElementById('hosted-ctf-toggle-wrapper')) {
            const hiddenCatInput = document.createElement('input');
            hiddenCatInput.type = 'hidden';
            hiddenCatInput.name = 'category';
            catInput.removeAttribute('name');
            catInput.parentNode.insertBefore(hiddenCatInput, catInput);

            const wrapper = document.createElement('div');
            wrapper.id = 'hosted-ctf-toggle-wrapper';
            wrapper.className = 'form-group border rounded p-3 bg-light mt-3 mb-3';
            wrapper.innerHTML = 
<div style="display: flex; align-items: center; gap: 10px;">
    <span id="hosted-ctf-toggle-switch" style="display:inline-block;width:3rem;height:1.5rem;border-radius:2rem;background:#adb5bd;position:relative;cursor:pointer;transition:background .2s;" data-on="false">
        <span style="position:absolute;top:2px;left:2px;width:calc(1.5rem - 4px);height:calc(1.5rem - 4px);border-radius:50%;background:#fff;transition:transform .2s;" id="hosted-ctf-toggle-knob"></span>
    </span>
    <label style="margin:0;cursor:pointer;" onclick="document.getElementById('hosted-ctf-toggle-switch').click()">
        <strong>Is this a Hosted CTF Challenge?</strong>
    </label>
</div>
<small class="form-text text-muted mt-2">Checking this pushes the challenge to the Hosted CTF board rather than the normal map.</small>
;

            catInput.closest('.form-group').parentNode.insertBefore(wrapper, catInput.closest('.form-group'));

            const toggleSwitch = document.getElementById('hosted-ctf-toggle-switch');
            const knob = document.getElementById('hosted-ctf-toggle-knob');

            function setToggle(on) {
                toggleSwitch.setAttribute('data-on', on ? 'true' : 'false');
                if (on) {
                    toggleSwitch.style.background = '#007bff';
                    knob.style.transform = 'translateX(1.5rem)';
                } else {
                    toggleSwitch.style.background = '#adb5bd';
                    knob.style.transform = 'translateX(0)';
                }
            }

            function syncHiddenCategory() {
                let cleanValue = catInput.value.replace(/\s*\[Hosted CTF\]/g, '').trim();
                let isOn = toggleSwitch.getAttribute('data-on') === 'true';
                if (isOn) {
                    hiddenCatInput.value = cleanValue + ' [Hosted CTF]';
                } else {
                    hiddenCatInput.value = cleanValue;
                }
            }

            if (catInput.value.endsWith(' [Hosted CTF]')) {
                catInput.value = catInput.value.replace(/\s*\[Hosted CTF\]/g, '').trim();
                setToggle(true);
            }
            syncHiddenCategory();

            toggleSwitch.addEventListener('click', function() {
                let isOn = this.getAttribute('data-on') === 'true';
                setToggle(!isOn);
                syncHiddenCategory();
            });

            catInput.addEventListener('input', syncHiddenCategory);
            catInput.addEventListener('blur', function() {
                catInput.value = catInput.value.replace(/\s*\[Hosted CTF\]/g, '').trim();
                syncHiddenCategory();
            });
        }
    }, 500);
});
</script>'''

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    start_idx = content.find('document.addEventListener("DOMContentLoaded", function() {')
    end_idx = content.find('</script>', start_idx) + 9

    if start_idx != -1 and end_idx != -1:
        new_content = content[:start_idx] + replacement + content[end_idx:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file_path}")
    else:
        print(f"Failed to find block in {file_path}")
