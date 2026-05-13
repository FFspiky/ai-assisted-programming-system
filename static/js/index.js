document.addEventListener('DOMContentLoaded', function () {
    UserSession.init();

    document.querySelectorAll('.btn-run, .btn-ai').forEach((button) => {
        button.addEventListener('click', () => {
            window.location.href = '/problem_selector.html';
        });
    });
});
