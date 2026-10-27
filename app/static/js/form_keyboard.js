/* Avoid implicit writes when Enter is pressed while filling out a form. */
(() => {
  'use strict';

  document.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.isComposing) return;

    const field = event.target;
    if (!(field instanceof HTMLElement)) return;
    const form = field.form || field.closest('form');
    if (!form || form.method.toLowerCase() === 'get') return;

    // Keep explicit keyboard activation and multiline editing accessible.
    if (field.closest('button, a[href], textarea') || field.isContentEditable) return;
    if (field instanceof HTMLInputElement &&
        ['submit', 'button', 'reset', 'image'].includes(field.type)) return;

    // Login forms retain their usual Enter-to-sign-in behavior.
    if (form.querySelector('input[type="password"]') &&
        !form.querySelector('input[autocomplete="new-password"]')) return;

    // Do not stop propagation: item lookups and quantity shortcuts still run.
    event.preventDefault();
  });
})();
