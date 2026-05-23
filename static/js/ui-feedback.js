(function () {
    function apiErrorMessage(result, fallback = '请求失败') {
        if (!result) return fallback;
        if (typeof result.error === 'string') return result.error;
        if (result.error && result.error.message) return result.error.message;
        if (result.message) return result.message;
        return fallback;
    }

    function setButtonLoading(button, loadingText, isLoading) {
        if (!button) return;
        if (isLoading) {
            button.dataset.originalText = button.textContent;
            button.disabled = true;
            button.textContent = loadingText;
            return;
        }
        button.disabled = false;
        button.textContent = button.dataset.originalText || button.textContent;
        delete button.dataset.originalText;
    }

    function renderMessage(element, type, message) {
        if (!element) return;
        element.className = `message ${type}`;
        element.textContent = message;
    }

    function renderRetry(element, message, retryLabel, onRetry) {
        if (!element) return;
        element.innerHTML = `
            <div class="message error" style="display:block;">
                <span>${escapeHtml(message)}</span>
                <button type="button" class="secondary-btn" style="margin-top:0.75rem;">${escapeHtml(retryLabel || '重试')}</button>
            </div>
        `;
        element.querySelector('button')?.addEventListener('click', onRetry);
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
    }

    window.UIFeedback = {
        apiErrorMessage,
        escapeHtml,
        renderMessage,
        renderRetry,
        setButtonLoading,
    };
})();
