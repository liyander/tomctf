import re

p1 = 'CTFd/CTFd/themes/admin/templates/challenges/new.html'
p2 = 'CTFd/CTFd/themes/admin/templates/challenges/challenge.html'

for p in [p1, p2]:
    with open(p, 'r', encoding='utf-8') as f:
        t = f.read()
    
    # We strip out the entire wrapper.innerHTML injection block and event listeners and replace it entirely
    t = re.sub(
        r"wrapper\.innerHTML = [\s\S]+?catInput\.addEventListener\('blur', function\(\) \{[\s\S]+?\}\);\n\s+\}",
        '''wrapper.innerHTML = 
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

            if (catInput.value.endsWith(' [Hosted CTF]')) {
                setToggle(true);
            }

            toggleSwitch.addEventListener('click', function() {
                let isOn = this.getAttribute('data-on') === 'true';
                isOn = !isOn;
                setToggle(isOn);
                
                if (isOn) {
                    if (!catInput.value.endsWith(' [Hosted CTF]')) { catInput.value = catInput.value.trim() + ' [Hosted CTF]'; }
                } else {
                    catInput.value = catInput.value.replace(' [Hosted CTF]', '').trim();
                }
            });
            catInput.addEventListener('blur', function() {
                if (toggleSwitch.getAttribute('data-on') === 'true' && !catInput.value.endsWith(' [Hosted CTF]')) {
                    catInput.value = catInput.value.trim() + ' [Hosted CTF]';
                }
            });
        }''', t)

    with open(p, 'w', encoding='utf-8') as f:
        f.write(t)
