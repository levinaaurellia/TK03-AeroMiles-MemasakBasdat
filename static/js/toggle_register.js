const roleMember = document.getElementById('roleMember');
const roleStaf = document.getElementById('roleStaf');
const stafFields = document.getElementById('stafFields');
const kodeMaskapai = document.getElementById('kode_maskapai');

function toggleFields() {
    if (roleStaf.checked) {
        stafFields.style.display = 'block';
        kodeMaskapai.setAttribute('required', '');
    } else {
        stafFields.style.display = 'none';
        kodeMaskapai.removeAttribute('required');
    }
}

roleMember.addEventListener('change', toggleFields);
roleStaf.addEventListener('change', toggleFields);