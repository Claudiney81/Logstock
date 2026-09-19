const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../app/templates/nota_fiscal/nova.html'), 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    innerHTML: '', hidden: false, value: '', children: [], events: {},
    addEventListener(name, handler) { this.events[name] = handler; },
    appendChild(row) { this.children.push(row); },
    querySelectorAll() { return []; },
  });
  return elements.get(id);
}
let matrix = [];
const alerts = [];
const context = vm.createContext({
  console: { warn() {}, error() {} }, Uint8Array,
  alert: message => alerts.push(message),
  document: {
    getElementById: element, addEventListener() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    createElement() { return { innerHTML: '' }; },
  },
  FileReader: class {
    readAsArrayBuffer() { this.onload({ target: { result: new ArrayBuffer(0) } }); }
  },
  XLSX: {
    read() { return { SheetNames: ['Itens'], Sheets: { Itens: {} } }; },
    utils: { sheet_to_json() { return matrix; } },
  },
});
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) vm.runInContext(match[1], context);
const run = code => vm.runInContext(code, context);
function importRows(rows) {
  matrix = rows;
  element('importarExcel').events.change({ target: { files: [{ name: 'materiais.xlsx' }], value: 'arquivo' } });
}
run('itensNotaLote = [{codigo: "CAB-01", descricao: "Cabo elétrico"}]');
importRows([
  ['Orçamento'], ['Item', 'Qtd.', 'Valor estimado'],
  ['Cabo eletrico', '2 UN', 'R$ 1.234,56'], ['Novo <item>', 3, 12.5],
  ['Quantidade inválida', 1.5, 10], ['Total', 5, 2500],
]);
assert.equal(run('itensImportadosPendentes.length'), 2);
assert.equal(run('itensImportadosPendentes[0].codigo'), 'CAB-01');
assert.equal(run('itensImportadosPendentes[0].valor'), '1234.56');
assert.match(run('itensImportadosPendentes[1].codigo'), /^IMP-/);
assert.equal(element('tabela-itens').children.length, 0, 'Importar deve aguardar seleção');
assert.match(element('itensImportadosPendentes').innerHTML, /Novo &lt;item&gt;/);
run('alternarImportadoPendente(1, false); adicionarImportadosSelecionados()');
assert.equal(element('tabela-itens').children.length, 1);
assert.match(element('tabela-itens').children[0].innerHTML, /name="valor\[\]" value="1234.56"/);
assert.equal(run('itensImportadosPendentes.length'), 1);
run('marcarTodosImportados(false); adicionarImportadosSelecionados()');
assert.equal(element('tabela-itens').children.length, 1);
run('marcarTodosImportados(true); adicionarImportadosSelecionados()');
assert.equal(element('tabela-itens').children.length, 2);
assert.match(element('tabela-itens').children[1].innerHTML, /Novo &lt;item&gt;/);
assert.equal(element('itensImportadosPendentes').hidden, true);
importRows([['Código', 'Descrição', 'Quantidade', 'Valor Unitário'], ['00012', 'Parafuso', 4, 5.25]]);
assert.equal(run('itensImportadosPendentes[0].codigo'), '00012');
assert.equal(run('itensImportadosPendentes[0].valor'), '5.25');
run('itemJaNaNota = codigo => codigo === "00012"');
run('adicionarImportadosSelecionados()');
assert.equal(element('tabela-itens').children.length, 2, 'Código existente não deve ser adicionado novamente');
importRows([['Item', 'Qtd', 'Valor'], ['Sem saldo', 0, 10]]);
assert.equal(run('itensImportadosPendentes.length'), 0);
assert.equal(element('itensImportadosPendentes').hidden, true);
assert.equal(run('numeroExcel("R$ 1.234,56")'), 1234.56);
assert.equal(run('numeroExcel(12.5)'), 12.5);
console.log('OK: prévia, seleção, cabeçalhos QA e Start, valores, descrição cadastrada, código gerado, duplicados e escape HTML.');
