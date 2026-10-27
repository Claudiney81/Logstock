# Validação de rascunhos e edição de técnicos

Os testes usam bancos temporários e dados fictícios. Nenhum deles deve apontar para produção.

Testes de servidor e regras de edição:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Regressão da importação de notas:

```powershell
node tests/nota_fiscal_importacao.test.cjs
```

Testes completos no Chrome instalado, com servidor e banco temporários criados pelo próprio teste:

```powershell
pip install playwright
python tests/browser_drafts.py
```

Para usar outro navegador instalado pelo Playwright, defina `DRAFT_TEST_BROWSER` com o canal desejado. Os testes usam as mesmas bibliotecas CDN da aplicação. Em ambientes sem acesso à CDN, `DRAFT_TEST_ASSET_DIR` pode apontar para cópias das versões exatas: `bootstrap-test.js` (Bootstrap 5.3.0 bundle) e `signature-pad-test.js` (Signature Pad 4.0.0).

Cobertura: recuperação após atualizar ou navegar, itens e totais, erros de validação, limpeza após gravação, descarte explícito, inventários, baixas desktop e mobile, requisições mobile, ferramentas, assinaturas, fotos, separação entre usuários, conflitos entre abas e reconstrução segura dos rascunhos.

A importação também é verificada com arquivos `.xlsx` e `.xls` reais, com a rede externa bloqueada: seleção da prévia, códigos com zeros à esquerda, cabeçalhos abreviados, valores em reais, recuperação da prévia e mensagens de erro.

`browser_handoff.py` reproduz a nota em uma aba, o cadastro real de item em outra e o F5 na nota, tanto antes quanto depois do login. O preenchimento iniciado antes do login fica restrito à aba e é transferido à conta na atualização, sem faixas de confirmação na tela.
