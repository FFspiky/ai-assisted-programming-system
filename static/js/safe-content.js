(function () {
    function escape(value) {
        return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    // Escape first; only the fixed formatting tags below can enter the DOM.
    function markdown(value) {
        return String(value ?? '').split(/(```[\s\S]*?```)/g).map(part => {
            if (part.startsWith('```') && part.endsWith('```')) {
                return '<pre><code>' + escape(part.replace(/^```[^\n]*\n?/, '').slice(0, -3)) + '</code></pre>';
            }
            return escape(part)
                .replace(/^#{1,6}\s+(.+)$/gm, '<h4>$1</h4>')
                .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
                .replace(/`([^`\n]+)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        }).join('');
    }
    window.SafeContent = {escape, markdown};
})();
