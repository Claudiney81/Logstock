document.addEventListener('DOMContentLoaded', () => {
  if (!window.bootstrap?.Tooltip) return;
  document.querySelectorAll('.fin-workspace [data-fin-help]').forEach(source => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'fin-help no-print';
    button.textContent = 'i';
    button.setAttribute('aria-label', 'Ajuda');
    source.hidden = true;
    const label = source.previousElementSibling;
    const panel = source.closest('.fin-panel');
    const heading = panel?.querySelector('h2');
    if (source.tagName === 'SMALL') {
      const fieldLabel = source.parentElement.querySelector('label');
      (fieldLabel || source.parentElement).append(button);
    } else if (label?.matches('h2, h3')) {
      label.append(button);
    } else if (heading && !source.closest('form')) {
      heading.append(button);
    } else if (source.parentElement.classList.contains('fin-workspace') || source.closest('.fin-directory-intro')) {
      document.querySelector('.fin-head h1')?.append(button);
      if (source.closest('.fin-directory-intro')) source.closest('.fin-directory-intro').hidden = true;
    } else {
      source.before(button);
    }
    const tooltip = new bootstrap.Tooltip(button, {
      title: () => source.textContent.trim(),
      placement: 'top', container: 'body', trigger: 'hover focus',
      customClass: 'fin-help-tooltip', delay: { show: 180, hide: 0 },
    });
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') { tooltip.hide(); button.blur(); }
    });
    button.addEventListener('click', () => button.focus());
  });
});
