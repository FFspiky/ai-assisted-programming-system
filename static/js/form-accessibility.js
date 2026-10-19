(() => {
    function clear(input) {
        input.removeAttribute('aria-invalid');
        const id = input.id + '-error';
        document.getElementById(id)?.remove();
        const ids = (input.getAttribute('aria-describedby') || '').split(' ').filter(x => x && x !== id);
        if (ids.length) input.setAttribute('aria-describedby', ids.join(' '));
        else input.removeAttribute('aria-describedby');
    }
    function error(input, text) {
        clear(input);
        const note = document.createElement('div');
        note.id = input.id + '-error'; note.className = 'field-error'; note.textContent = text;
        input.insertAdjacentElement('afterend', note);
        input.setAttribute('aria-invalid', 'true');
        input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), note.id].filter(Boolean).join(' '));
        input.focus();
    }
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('invalid', event => {
            event.preventDefault();
            if (event.target === form.querySelector(':invalid')) error(event.target, event.target.validationMessage);
        }, true);
        form.addEventListener('input', event => clear(event.target));
    });
    window.FormAccessibility = {error};
})();
