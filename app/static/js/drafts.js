/* Local operation drafts. Never submit, replay requests, or change stock here. */
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('logistock-draft-config').textContent);
  const prefix = 'logistock:draft:v1:';
  const anonymous = config.user.startsWith('anon-');
  const storageFor = key => key.startsWith(prefix + 'anon-') ? sessionStorage : localStorage;
  const pending = new Set();
  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    const task = originalFetch.apply(this, args);
    const body = task.then(r => r.clone().arrayBuffer()).catch(() => {});
    pending.add(body);
    body.finally(() => pending.delete(body));
    return task;
  };
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function settled() {
    // Include response parsing and chained catalogue requests; never wait forever.
    const end = Date.now() + 12000;
    do {
      if (pending.size) await Promise.race([Promise.all([...pending]), pause(100)]);
      await pause(40);
    } while (pending.size && Date.now() < end);
  }
  let database;
  function fileStore(mode, action) {
    if (!database) database = new Promise((resolve, reject) => {
      const req = indexedDB.open('logistock-draft-files', 1);
      req.onupgradeneeded = () => req.result.createObjectStore('files');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return database.then(db => new Promise((resolve, reject) => {
      const tx = db.transaction('files', mode);
      const req = action(tx.objectStore('files'));
      tx.oncomplete = () => resolve(req.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    }));
  }
  for (const key of config.completed) {
    try {
      storageFor(key).removeItem(key);
      storageFor(key).setItem(key + ':completed', String(Date.now()));
    } catch (_) { /* reported by form status */ }
    fileStore('readwrite', s => s.delete(key)).catch(() => {});
  }

  // Rebuild only harmless form/table elements, never scripts or arbitrary HTML.
  const tags = new Set('TABLE THEAD TBODY TR TD TH DIV SPAN INPUT SELECT OPTION TEXTAREA BUTTON I STRONG SMALL LABEL BR P IMG H6'.split(' '));
  const attrs = /^(id|class|name|type|value|title|placeholder|readonly|required|multiple|min|max|step|colspan|rowspan|hidden|data-[\w-]+|aria-[\w-]+)$/;
  const actions = new Set(['removerLinha', 'inserirLinha', 'removerItem', 'removerItemResumo', 'preencherCampos', 'removerFoto']);
  function safeAction(code) {
    const match = /^(\w+)\((this|true|false|\d+)?(?:,\s*(true|false))?\)\s*;?$/.exec(code || '');
    return match && actions.has(match[1]) ? code : null;
  }
  function pack(node) {
    if (node.nodeType === 3) return node.textContent;
    if (!tags.has(node.tagName)) return null;
    const attributes = {};
    for (const a of node.attributes) {
      if (attrs.test(a.name) || (/^on(click|change)$/.test(a.name) && safeAction(a.value))) attributes[a.name] = a.value;
    }
    return {tag: node.tagName, attributes, value: node.type === 'file' ? '' : node.value,
      checked: node.checked, children: [...node.childNodes].map(pack).filter(n => n !== null)};
  }
  function unpack(data) {
    if (typeof data === 'string') return document.createTextNode(data);
    if (!data || !tags.has(data.tag)) return document.createTextNode('');
    const node = document.createElement(data.tag);
    for (const [name, value] of Object.entries(data.attributes || {})) {
      if (attrs.test(name) || (/^on(click|change)$/.test(name) && safeAction(value))) node.setAttribute(name, value);
    }
    node.replaceChildren(...(data.children || []).map(unpack));
    if (data.value !== undefined && node.type !== 'file') node.value = data.value;
    if (data.checked !== undefined) node.checked = data.checked;
    return node;
  }
  function controlKeys(form) {
    // One pass also keeps large inventory counts responsive while typing.
    const counts = new Map(), keys = new Map();
    for (const el of form.querySelectorAll('input,select,textarea')) {
      const row = el.closest('tr');
      const rowId = row && (row.dataset.itemId || row.dataset.id || row.dataset.codigo || row.dataset.resumoKey ||
        row.querySelector('input[name="item_id[]"]')?.value || row.querySelector('input[name="codigo[]"]')?.value);
      const name = el.id || el.name || el.className;
      const index = counts.get(name) || 0;
      counts.set(name, index + 1);
      keys.set(el, `${name}|${rowId || el.dataset.id || el.dataset.codigo || index}`);
    }
    return keys;
  }
  function regions(form) {
    // Explicit regions include empty summaries and paired hidden submit fields.
    return [...form.querySelectorAll('[data-draft-region]')];
  }
  function controls(form, includeRegions = false) {
    return [...form.querySelectorAll('input,select,textarea')].filter(el =>
      (el.name || el.id || el.dataset.id || el.dataset.codigo || el.closest('tr[data-codigo],tr[data-item-id],tr[data-id]')) && !['password', 'submit', 'button', 'reset'].includes(el.type) &&
      !/csrf|token|^_draft_key$/.test(el.name || '') && (includeRegions || !el.closest('[data-draft-region]')));
  }
  document.addEventListener('DOMContentLoaded', async () => {
    if (!config.user) return;
    const forms = [...document.forms].filter(form => form.method.toLowerCase() === 'post' &&
      !form.querySelector('input[type="password"]') && !form.hasAttribute('data-draft-off') &&
      (controls(form).filter(el => el.type !== 'hidden').length >= 2 ||
       form.querySelector('textarea,input[type="number"],input[type="file"],input[type="text"]')));
    await Promise.all(forms.map(async (form, index) => {
      const identity = location.pathname + location.search + ':' + (form.id || index);
      let tabId = sessionStorage.getItem('logistock:draft-tab-id');
      if (!tabId) {
        tabId = crypto.randomUUID();
        sessionStorage.setItem('logistock:draft-tab-id', tabId);
      }
      const key = prefix + config.user + ':' + identity + (anonymous ? ':tab:' + tabId : '');
      const storage = storageFor(key);
      const handoffKey = 'logistock:draft-handoff:' + identity;
      const marker = document.createElement('input');
      marker.type = 'hidden'; marker.name = '_draft_key'; marker.value = key;
      form.appendChild(marker);
      const banner = document.createElement('div');
      banner.className = 'alert alert-warning';
      banner.hidden = true;
      banner.dataset.draftUi = '';
      const status = document.createElement('span'); status.setAttribute('role', 'status');
      const discard = document.createElement('button');
      discard.type = 'button'; discard.className = 'btn btn-link btn-sm text-secondary ms-auto';
      discard.textContent = 'Limpar preenchimento'; discard.hidden = true;
      discard.dataset.draftUi = '';
      banner.append(status); form.prepend(banner); form.append(discard);
      function showIssue(message) { banner.hidden = false; status.textContent = message; }
      let restoring = true, active = false, conflict = false, remoteConflict = false, fileTimer, lastContent, restoreWarning = '', savingFiles = Promise.resolve();
      const opened = Date.now();
      const reload = document.createElement('button');
      reload.type = 'button'; reload.className = 'btn btn-sm btn-primary';
      reload.textContent = 'Carregar versão atual'; reload.hidden = true;
      reload.addEventListener('click', () => location.reload());
      banner.append(reload);
      window.addEventListener('storage', event => {
        if (event.key !== key || restoring) return;
        conflict = true;
        remoteConflict = true;
        showIssue('Esta operação foi alterada em outra aba. Carregue a versão atual antes de continuar.');
        reload.hidden = false;
      });
      form.addEventListener('submit', event => {
        if (!conflict) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        alert('A operação foi alterada em outra aba. Clique em Carregar versão atual.');
      }, true);
      const adapter = () => window.logistockDraftAdapter;
      function capture() {
        const keys = controlKeys(form);
        const fileInfo = file => ({name: file.name, size: file.size, modified: file.lastModified});
        return {version: 1, updated: Date.now(), fileInfo: controls(form, true).filter(el => el.type === 'file').map(el => [...el.files].map(fileInfo)),
        fileExtra: (adapter()?.files?.() || []).map(fileInfo), fields: controls(form).filter(x => x.type !== 'file').map(el => ({
          key: keys.get(el), value: el.value, checked: el.checked
        })), regions: regions(form).map(el => ({id: el.dataset.draftRegion, children: [...el.childNodes].map(pack).filter(n => n !== null)})),
        extra: adapter()?.capture?.() || null};
      }
      function collectFiles() {
        const keys = controlKeys(form);
        return {fields: controls(form, true).filter(el => el.type === 'file').map(el => ({key: keys.get(el), files: [...el.files]})),
          extra: adapter()?.files?.() || null};
      }
      function saveFiles() {
        if (conflict) return;
        const data = collectFiles();
        savingFiles = savingFiles.catch(() => {}).then(() => fileStore('readwrite', s => s.put(data, key)));
        savingFiles.catch(() => { showIssue('Os campos estão salvos; não foi possível guardar os anexos neste navegador.'); });
      }
      function save() {
        if (restoring || !active || conflict) return;
        try {
          if (Number(storage.getItem(key + ':completed') || 0) > opened) return;
          const snapshot = capture();
          const content = JSON.stringify({...snapshot, updated: 0});
          if (content === lastContent) return;
          storage.setItem(key, JSON.stringify(snapshot));
          lastContent = content;
        } catch (_) { showIssue('Não foi possível preservar o preenchimento. Mantenha esta página aberta.'); }
      }
      discard.addEventListener('click', async () => {
        if (remoteConflict) { location.reload(); return; }
        if (!confirm('Descartar os dados desta operação e começar novamente?')) return;
        restoring = true;
        clearTimeout(fileTimer);
        await savingFiles.catch(() => {});
        try {
          storage.removeItem(key);
          await fileStore('readwrite', s => s.delete(key));
          location.reload();
        } catch (_) { restoring = false; showIssue('Não foi possível limpar o preenchimento.'); }
      });
      async function restore(snapshot) {
        const desired = new Map(snapshot.fields.map(field => [field.key, field]));
        let keys = controlKeys(form);
        // Restore dependent selectors in DOM order, after each catalogue loads.
        for (const el of controls(form)) {
          const field = desired.get(keys.get(el));
          if (!field || el.type === 'file') continue;
          el.value = field.value; el.checked = field.checked;
          if (el.tagName === 'SELECT' && !/submit|aplicarFiltros|location/.test(el.getAttribute('onchange') || '')) {
            el.dispatchEvent(new Event('change', {bubbles: true}));
            await settled();
          }
        }
        await adapter()?.restore?.(snapshot.extra);
        await settled();
        for (const region of snapshot.regions || []) {
          const target = regions(form).find(el => el.dataset.draftRegion === region.id);
          if (target) target.replaceChildren(...region.children.map(unpack));
        }
        // Async handlers may reset text fields. Reapply values without new requests.
        keys = controlKeys(form);
        for (const el of controls(form)) {
          const field = desired.get(keys.get(el));
          if (field && el.type !== 'file') { el.value = field.value; el.checked = field.checked; }
        }
        try {
          const attachments = await fileStore('readonly', s => s.get(key));
          if (!attachments && ((snapshot.fileInfo || []).some(files => files.length) || snapshot.fileExtra?.length)) {
            restoreWarning = 'Rascunho recuperado. Selecione novamente os anexos que não puderam ser guardados.';
          }
          for (const entry of attachments?.fields || []) {
            const el = controls(form, true).find(x => keys.get(x) === entry.key);
            if (!el || el.type !== 'file') continue;
            const transfer = new DataTransfer();
            entry.files.forEach(file => transfer.items.add(file));
            el.files = transfer.files;
            if (el.classList.contains('foto-input') && entry.files.length) el.dispatchEvent(new Event('change', {bubbles: true}));
          }
          await adapter()?.restoreFiles?.(attachments?.extra);
        } catch (_) { restoreWarning = 'Rascunho recuperado. Confira e selecione novamente os anexos.'; }
        form.querySelectorAll('.quantidade-contada').forEach(el => el.dispatchEvent(new Event('input', {bubbles: true})));
        form.dispatchEvent(new CustomEvent('draft:restored', {bubbles: true}));
        await settled();
      }
      let saved;
      form.inert = true;
      try {
        await settled();
        saved = JSON.parse(storage.getItem(key) || 'null');
        const previous = sessionStorage.getItem(handoffKey);
        let transferFrom;
        // A page can be opened before login, then authenticated in another tab.
        // Transfer only that tab's unowned work; never another account's draft.
        if (!saved && !anonymous && previous?.startsWith(prefix + 'anon-')) {
          const unowned = sessionStorage.getItem(previous);
          if (unowned) {
            saved = JSON.parse(unowned);
            storage.setItem(key, unowned);
            transferFrom = previous;
            try {
              const files = await fileStore('readonly', s => s.get(previous));
              if (files) await fileStore('readwrite', s => s.put(files, key));
            } catch (_) { restoreWarning = 'Confira e selecione novamente os anexos que não puderam ser recuperados.'; }
          }
        }
        if (saved?.version === 1) {
          await restore(saved);
          lastContent = JSON.stringify({...capture(), updated: 0});
          if (restoreWarning) showIssue(restoreWarning);
          active = true;
          discard.hidden = false;
          if (transferFrom) {
            sessionStorage.removeItem(transferFrom);
            fileStore('readwrite', s => s.delete(transferFrom)).catch(() => {});
          }
        }
        sessionStorage.setItem(handoffKey, key);
      } catch (_) {
        showIssue(saved ? 'Não foi possível recuperar todos os dados. Carregue a versão atual para tentar novamente.' : 'Não foi possível acessar o preenchimento salvo. Mantenha esta página aberta.');
        if (saved) { conflict = true; reload.hidden = false; discard.hidden = false; }
      }
      finally { restoring = false; form.inert = false; }
      const changed = (event) => {
        if (restoring) return;
        discard.hidden = false;
        active = true; save();
        clearTimeout(fileTimer);
        if (event?.target?.type === 'file') saveFiles();
        else fileTimer = setTimeout(saveFiles, 150);
      };
      form.addEventListener('input', changed);
      form.addEventListener('change', changed);
      form.addEventListener('pointerup', () => setTimeout(changed, 0));
      form.addEventListener('touchend', () => setTimeout(changed, 0), {passive: true});
      form.addEventListener('click', event => {
        if (event.target.closest('[data-draft-ui]')) return;
        setTimeout(changed, 0);
      });
      new MutationObserver(records => {
        if (records.some(r => !r.target.closest?.('[data-draft-ui]'))) save();
      }).observe(form, {childList: true, subtree: true});
      form.addEventListener('submit', () => { active = true; save(); saveFiles(); });
      const nativeSubmit = HTMLFormElement.prototype.submit;
      form.submit = function () {
        if (conflict) {
          alert('A operação foi alterada em outra aba. Clique em Carregar versão atual.');
          return;
        }
        active = true; save(); saveFiles();
        nativeSubmit.call(form);
      };
      window.addEventListener('pagehide', save);
      window.addEventListener('pageshow', event => {
        if (event.persisted && Number(storage.getItem(key + ':completed') || 0) > opened) location.reload();
      });
      document.addEventListener('visibilitychange', () => { if (document.hidden) save(); });
      // Programmatic changes to hidden fields and signature pads do not emit input.
      setInterval(save, 2000);
    }));
  });
})();
