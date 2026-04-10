import re

with open('CTFd/CTFd/themes/admin/templates/challenges/new.html', 'r', encoding='utf-8') as f:
    text = f.read()

new_block = '''            wrapper.innerHTML = \
                <div class="custom-control custom-switch" style="display:flex; align-items:center;">
                    <span id="hosted-ctf-toggle" data-checked="false" style="cursor:pointer; display:inline-block; width:40px; height:20px; background:#ddd; border-radius:20px; position:relative; vertical-align:middle; margin-right:10px;">
                        <span id="hosted-ctf-knob" style="width:16px; height:16px; background:#fff; border-radius:50%; position:absolute; top:2px; left:2px; transition:0.2s;"></span>
                    </span>
                    <label style="cursor:pointer; vertical-align:middle; margin-bottom:0;" onclick="document.getElementById('hosted-ctf-toggle').click()">
                        <strong>Is this a Hosted CTF Challenge?</strong>        
                    </label>
                </div>
                <small class="form-text text-muted mt-2">Checking this pushes the challenge to the Hosted CTF board rather than the normal map.</small>
            \;

            catInput.closest('.form-group').parentNode.insertBefore(wrapper, catInput.closest('.form-group'));

            const toggle = document.getElementById('hosted-ctf-toggle');        
            const knob = document.getElementById('hosted-ctf-knob');

            function setToggleState(state) {
                toggle.setAttribute('data-checked', state);
                if(state) {
                    toggle.style.background = '#007bff';
                    knob.style.left = '22px';
                } else {
                    toggle.style.background = '#ddd';
                    knob.style.left = '2px';
                }
            }

            if (catInput.value.endsWith(' [Hosted CTF]')) {
                setToggleState(true);
            }
            
            toggle.addEventListener('click', function() {
                let isChecked = this.getAttribute('data-checked') === 'true';
                isChecked = !isChecked;
                setToggleState(isChecked);

                if (isChecked) {
                    if (!catInput.value.endsWith(' [Hosted CTF]')) { catInput.value = catInput.value.trim() + ' [Hosted CTF]'; }
                } else {
                    catInput.value = catInput.value.replace(' [Hosted CTF]', '').trim();
                }
            });
            catInput.addEventListener('blur', function() {
                let isChecked = toggle.getAttribute('data-checked') === 'true';
                if (isChecked && !catInput.value.endsWith(' [Hosted CTF]')) {
                    catInput.value = catInput.value.trim() + ' [Hosted CTF]';   
                }
            });
        }
    }, 500);'''

text = re.sub(r'            wrapper\.innerHTML = \n\s*<div class="custom-control custom-switch">[\s\S]*?            }\n        }\n    \}, 500\);', new_block, text)

with open('CTFd/CTFd/themes/admin/templates/challenges/new.html', 'w', encoding='utf-8') as f:
    f.write(text)

with open('CTFd/CTFd/themes/admin/templates/challenges/challenge.html', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'            wrapper\.innerHTML = \n\s*<div class="custom-control custom-switch">[\s\S]*?            }\n        }\n    \}, 500\);', new_block, text)
with open('CTFd/CTFd/themes/admin/templates/challenges/challenge.html', 'w', encoding='utf-8') as f:
    f.write(text)
