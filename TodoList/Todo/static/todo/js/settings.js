const settingsForm = document.querySelector('[data-autosubmit-settings]');

settingsForm?.addEventListener('change', () => {
    settingsForm.requestSubmit();
});
