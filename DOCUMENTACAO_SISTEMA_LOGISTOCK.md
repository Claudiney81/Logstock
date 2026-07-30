# Documentação do Sistema LogiStock

**Data:** 15/06/2026  
**Sistema:** LogiStock - Controle de Estoque, Técnicos, Materiais, Frota e Operações  
**Finalidade:** documentação funcional para apresentação técnica e entrega à empresa.

---

## 1. Visão Geral

O LogiStock é um sistema web desenvolvido para controlar materiais, estoque, notas fiscais, movimentações, técnicos, baixas de campo, ferramentas, EPIs, frota e registros operacionais da empresa.

O sistema centraliza informações que antes poderiam ficar dispersas em planilhas, papéis ou conversas, permitindo maior controle sobre entrada, saída, localização, responsabilidade e histórico dos materiais. Ele também oferece telas para uso administrativo e telas mobile para técnicos e aprovadores.

De forma resumida, o LogiStock ajuda a empresa a responder perguntas como:

- Quais materiais existem em estoque?
- Qual material está com cada técnico?
- Quais itens estão abaixo do mínimo?
- Quais materiais entraram por nota fiscal?
- Quais materiais foram movimentados, baixados ou devolvidos?
- Quais baixas ainda dependem de aprovação?
- Quais ferramentas e EPIs estão com cada colaborador?
- Qual o histórico de veículos, abastecimentos, manutenções e vistorias?
- Quais documentos e relatórios podem ser apresentados em auditorias ou conferências internas?

---

## 2. Objetivos do Sistema

O sistema foi criado para apoiar a operação da empresa nos seguintes objetivos:

- Controlar o estoque físico e financeiro de materiais.
- Registrar entradas de materiais por notas fiscais.
- Controlar movimentações entre empresa, técnicos, clientes, obras e ordens de serviço.
- Dar rastreabilidade aos materiais em posse dos técnicos.
- Facilitar baixas de materiais usados em campo.
- Registrar aprovação, recusa e correção de baixas.
- Controlar ferramentas e EPIs entregues aos técnicos.
- Gerar termos, históricos, relatórios e arquivos de conferência.
- Apoiar inventários periódicos do estoque e dos técnicos.
- Controlar frota, documentos, manutenções, abastecimentos e vistorias.
- Permitir acesso mobile para técnicos e aprovadores.
- Reduzir perdas, divergências de estoque e falta de materiais.

---

## 3. Perfis de Usuário

O LogiStock possui controle de acesso por usuário e perfil.

### Administrador

Perfil com acesso amplo ao sistema. Pode cadastrar usuários, gerenciar cadastros, consultar históricos e acessar as rotinas administrativas.

### Estoque

Perfil voltado ao setor de estoque/almoxarifado. Atua nos cadastros de materiais, saldo, notas fiscais, movimentações, requisições, inventários, baixas e relatórios.

### Área Técnica

Perfil voltado para análise e atendimento de solicitações técnicas, incluindo requisições recebidas e acompanhamento operacional.

### Técnico

Perfil usado principalmente no ambiente mobile. Permite que o técnico acesse suas rotinas, registre baixas, acompanhe pendências e altere sua senha.

### Supervisor/Aprovador

Perfil ou fluxo de acesso usado para aprovar ou recusar baixas realizadas pelo técnico, principalmente no módulo mobile de aprovação.

---

## 4. Tela Inicial e Painel de Controle

Após o login administrativo, o sistema apresenta uma tela inicial com indicadores e movimentações recentes.

O painel exibe informações como:

- Total de itens cadastrados.
- Técnicos ativos.
- Itens com estoque baixo.
- Requisições pendentes.
- Baixas pendentes.
- Notas fiscais registradas nos últimos 30 dias.
- Movimentações recentes.
- Notas fiscais recentes.
- Baixas recentes.

Essa visão oferece ao responsável uma leitura rápida da situação operacional do estoque e das pendências.

---

## 5. Gestão de Estoque

O módulo de estoque é a base do sistema. Ele permite cadastrar, consultar, importar, exportar e acompanhar materiais da empresa.

### Principais funcionalidades

- Cadastro de itens com código, descrição, unidade, valor, categoria e tipo de serviço.
- Cadastro de quantidade disponível em estoque.
- Controle de quantidade mínima por item.
- Definição de endereço/localização do material.
- Separação entre estoque da empresa e estoque vinculado a cliente.
- Vinculação do estoque a tipo de serviço.
- Controle de condição do material, quando aplicável.
- Listagem geral dos itens.
- Consulta de saldo de estoque.
- Alerta de materiais abaixo do mínimo.
- Atualização de mínimos e endereços.
- Importação de itens via planilha Excel.
- Exportação de itens cadastrados em Excel.
- Exportação de saldo de estoque em Excel.
- Exportação de alertas em Excel e PDF.

### Benefícios

- Evita falta de materiais essenciais.
- Ajuda no planejamento de compras.
- Facilita conferências de almoxarifado.
- Melhora a localização física dos itens.
- Dá visibilidade sobre materiais críticos.

---

## 6. Tipos de Serviço

O sistema permite cadastrar tipos de serviço para organizar materiais e operações.

Cada tipo de serviço pode ser vinculado ao estoque da empresa ou ao estoque de cliente, permitindo maior controle sobre a origem e o destino dos materiais.

Exemplos de uso:

- Separar materiais por contrato, operação ou área de atendimento.
- Filtrar itens disponíveis conforme o serviço executado.
- Controlar materiais que pertencem à empresa ou que pertencem ao cliente.

---

## 7. Notas Fiscais de Entrada

O módulo de nota fiscal registra a entrada formal de materiais no sistema.

### Funcionalidades

- Cadastro de nota fiscal de entrada.
- Registro de fornecedor.
- Vinculação a cliente, ordem de serviço e tipo de serviço, quando necessário.
- Inclusão de vários itens na mesma nota.
- Controle de quantidade e valor unitário por item.
- Cálculo de valor total.
- Histórico de notas fiscais.
- Pesquisa de notas fiscais.
- Detalhamento individual da nota.
- Exportação da nota em PDF.
- Exportação da nota em Excel.
- Histórico de valores de entrada.
- Exportação do histórico de valores em Excel.

### Benefícios

- Garante rastreabilidade da entrada dos materiais.
- Facilita conferência entre nota fiscal e estoque.
- Permite histórico de preço dos materiais.
- Ajuda na análise de custo e reposição.

---

## 8. Movimentação de Estoque

O módulo de movimentação registra transferências e deslocamentos de materiais entre origens e destinos.

### Funcionalidades

- Nova movimentação de estoque.
- Origem e destino configuráveis.
- Movimentação entre estoque, técnicos, clientes e ordens de serviço.
- Registro de categoria e tipo de movimentação.
- Controle de retorno e motivo de retorno.
- Inclusão de itens, quantidades, valores e condição do material.
- Registro de responsável e observações.
- Assinatura quando aplicável.
- Histórico de movimentações.
- Detalhamento de cada movimentação.
- Exportação do histórico em Excel.
- Geração de PDF da movimentação.
- Possibilidade de envio de e-mail com PDF, conforme configuração.

### Benefícios

- Cria histórico confiável de saída, entrada e transferência.
- Reduz divergência entre estoque físico e sistema.
- Permite identificar quem recebeu ou movimentou cada item.
- Ajuda a comprovar movimentações em auditorias internas.

---

## 9. Técnicos

O módulo de técnicos controla os colaboradores que recebem materiais, ferramentas, EPIs ou executam serviços em campo.

### Funcionalidades

- Cadastro de técnico.
- Registro de matrícula, CPF, telefone, e-mail, função e status.
- Vinculação a tipo de serviço.
- Criação de usuário técnico quando aplicável.
- Listagem de técnicos cadastrados.
- Alteração de status do técnico.
- Geração de link de acesso mobile.
- Geração de QR Code para acesso do técnico.

### Benefícios

- Centraliza os dados dos técnicos.
- Facilita entrega e rastreio de materiais.
- Permite acesso mobile individual.
- Ajuda a controlar técnicos ativos e inativos.

---

## 10. Saldo Técnico

O saldo técnico mostra os materiais que estão sob responsabilidade de cada técnico.

### Funcionalidades

- Consulta de técnicos ativos.
- Visualização detalhada do saldo por técnico.
- Filtros por tipo de serviço, estoque da empresa, estoque de cliente, cliente e ordem de serviço.
- Agrupamento de itens por código, descrição e quantidade.
- Controle de quantidade mínima do técnico.
- Exportação do saldo técnico em Excel.

### Benefícios

- Mostra exatamente quais materiais estão com cada técnico.
- Ajuda a evitar perda ou acúmulo indevido de materiais.
- Facilita reposição e devolução.
- Permite conferência antes e depois de serviços.

---

## 11. Requisições de Técnicos

O sistema permite que técnicos ou áreas responsáveis solicitem materiais, com acompanhamento pelo estoque.

### Funcionalidades

- Nova requisição mobile.
- Registro de solicitante, técnico, tipo de serviço e origem do estoque.
- Vinculação a cliente e ordem de serviço.
- Inclusão de endereço, bairro, código de imóvel e responsável do projeto.
- Inclusão de itens solicitados.
- Registro de assinatura.
- Requisições recebidas pelo estoque.
- Atendimento de requisições.
- Histórico de requisições.
- Detalhamento da requisição.
- Exportação em PDF.
- Contador de pendências no menu.

### Benefícios

- Organiza pedidos de materiais.
- Reduz solicitações informais.
- Mantém histórico de atendimento.
- Dá visibilidade ao estoque sobre demandas pendentes.

---

## 12. Baixas Técnicas

O módulo de baixas controla materiais utilizados em campo pelos técnicos.

### Funcionalidades administrativas

- Cadastro de nova baixa.
- Seleção de técnico, cliente, ordem de serviço e tipo de serviço.
- Seleção dos itens disponíveis no saldo do técnico.
- Registro de quantidade utilizada.
- Baixas pendentes.
- Detalhamento da baixa.
- Aprovação total ou parcial.
- Recusa com motivo.
- Correção e reenvio de baixa recusada.
- Histórico de baixas.
- Baixas realizadas.
- Exportação de baixa em Excel.
- Exportação de baixa em PDF.
- Contador de baixas pendentes no menu.

### Funcionalidades mobile

- Formulário mobile para técnico registrar baixa.
- Consulta de pendências.
- Visualização de detalhe da baixa.
- Aprovação mobile por aprovador.
- Recusa mobile com motivo.
- Portal mobile de baixas.
- Login de aprovador.
- Upload de fotos da execução ou evidência.

### Benefícios

- Controla o consumo real dos materiais.
- Evita baixa sem aprovação.
- Permite análise por supervisor ou responsável.
- Registra evidências e histórico.
- Atualiza o saldo técnico após aprovação.

---

## 13. Inventário de Estoque

O inventário de estoque permite conferir o estoque físico contra o saldo registrado no sistema.

### Funcionalidades

- Início de inventário por responsável.
- Filtros por tipo de estoque, cliente e tipo de serviço.
- Registro da quantidade existente no sistema.
- Registro da quantidade contada fisicamente.
- Finalização do inventário.
- Histórico de inventários.
- Detalhamento de inventário.
- Exportação de inventário em Excel.

### Benefícios

- Identifica sobras e faltas.
- Ajuda a corrigir divergências.
- Gera documento de conferência.
- Fortalece controle patrimonial e operacional.

---

## 14. Inventário Técnico

O inventário técnico permite conferir os materiais que estão com os técnicos.

### Funcionalidades

- Criação de inventário por técnico e tipo de serviço.
- Formulário de contagem.
- Registro de quantidade existente e quantidade contada.
- Histórico de inventários técnicos.
- Detalhamento do inventário.
- Exportação em Excel.
- Devolução de materiais ao estoque.

### Benefícios

- Confere materiais em campo.
- Identifica divergência no saldo do técnico.
- Facilita devoluções.
- Ajuda na prestação de contas por colaborador.

---

## 15. Ferramentas e EPIs

O módulo de ferramentas e EPIs controla itens entregues aos técnicos que precisam de rastreio individual ou termo de responsabilidade.

### Funcionalidades

- Registro de entrega.
- Registro de devolução.
- Registro de ocorrência.
- Transferência de ferramentas e EPIs.
- Consulta de saldo por técnico.
- Histórico de movimentações.
- Detalhes da movimentação.
- Geração de termo em PDF.
- Armazenamento de assinatura do técnico e da logística.
- Exportação de saldo em Excel.
- Exportação de relatório gerencial.
- Envio de e-mail, quando configurado.

### Benefícios

- Controla responsabilidade sobre ferramentas e EPIs.
- Gera evidência formal de entrega.
- Ajuda em cobranças, devoluções e substituições.
- Oferece relatório gerencial para acompanhamento.

---

## 16. Clientes, Fornecedores e Ordens de Serviço

O módulo de empresas permite controlar clientes, fornecedores/parceiros e ordens de serviço.

### Funcionalidades

- Cadastro de clientes.
- Cadastro de fornecedores.
- Listagem separada de clientes e fornecedores.
- Edição de cadastro.
- Exclusão controlada.
- Exportação de cadastros em Excel.
- Criação de ordem de serviço para cliente.
- Listagem de ordens de serviço por cliente.
- Edição de ordem de serviço.
- Exportação de ordens de serviço em Excel.

### Benefícios

- Organiza cadastros comerciais e operacionais.
- Vincula materiais e movimentações a clientes específicos.
- Permite rastrear estoque por ordem de serviço.

---

## 17. Gestão de Frota

O módulo de frota controla veículos utilizados pela operação.

### Funcionalidades

- Cadastro de veículo.
- Listagem de veículos.
- Edição e exclusão.
- Registro de marca, modelo, placa, ano, cor, tipo, quilometragem, responsável e status.
- Registro de manutenções.
- Histórico de manutenções.
- Registro de abastecimentos.
- Histórico de abastecimentos.
- Controle de documentos da frota.
- Upload de documentos e imagens.
- Exportação de histórico de manutenções em PDF.
- Exportação de histórico de abastecimentos em PDF.

### Benefícios

- Centraliza dados da frota.
- Controla custos de manutenção e combustível.
- Mantém documentos importantes vinculados ao veículo.
- Ajuda no acompanhamento da vida útil e uso dos veículos.

---

## 18. Vistorias de Veículos

O módulo de vistorias registra inspeções dos veículos da empresa.

### Funcionalidades

- Nova vistoria.
- Seleção de veículo e técnico.
- Registro de tipo de vistoria.
- Registro de quilometragem, combustível e local.
- Checklist de itens verificados.
- Observações gerais.
- Upload de fotos.
- Assinatura do técnico e do responsável.
- Histórico de vistorias.
- Detalhamento de vistoria.
- Formulário para impressão.
- Exportação de histórico em PDF.
- Exportação de vistoria individual em PDF.

### Benefícios

- Documenta o estado do veículo.
- Ajuda a identificar avarias e responsabilidades.
- Gera evidência para controle interno.
- Facilita acompanhamento preventivo.

---

## 19. Acesso Mobile

O sistema possui telas mobile voltadas para técnicos e aprovadores.

### Funcionalidades mobile

- Login técnico.
- Página inicial do técnico.
- Alteração de senha.
- Registro de baixa técnica.
- Consulta de pendências.
- Requisição de materiais.
- Acesso por link e QR Code.
- Portal mobile de baixas.
- Login de aprovador.
- Aprovação ou recusa de baixas.

### Benefícios

- Permite uso em campo pelo celular.
- Reduz dependência do escritório.
- Agiliza registros operacionais.
- Melhora a comunicação entre técnico, estoque e aprovação.

---

## 20. Relatórios, Exportações e Evidências

O LogiStock gera documentos úteis para conferência, prestação de contas e auditoria.

### Exportações disponíveis

- Itens cadastrados em Excel.
- Saldos de estoque em Excel.
- Alertas de estoque em Excel e PDF.
- Notas fiscais em PDF e Excel.
- Histórico de valores de entrada em Excel.
- Histórico de movimentações em Excel.
- Detalhes de movimentação em PDF.
- Saldo técnico em Excel.
- Baixas em PDF e Excel.
- Requisições em PDF.
- Inventário de estoque em Excel.
- Inventário técnico em Excel.
- Saldo de ferramentas e EPIs em Excel.
- Relatório gerencial de ferramentas e EPIs em Excel.
- Termos de responsabilidade de ferramentas e EPIs em PDF.
- Histórico de manutenções em PDF.
- Histórico de abastecimentos em PDF.
- Histórico e detalhes de vistorias em PDF.
- Ordens de serviço em Excel.
- Clientes e fornecedores em Excel.

### Evidências armazenadas

- Assinaturas digitais.
- Fotos de baixas.
- Documentos de frota.
- Fotos de vistorias.
- Histórico com data e hora.
- Usuário responsável por registros.
- Status de aprovação, recusa e pendência.

---

## 21. Segurança e Controle

O sistema possui mecanismos de segurança e controle de acesso.

### Recursos de segurança

- Login com e-mail e senha.
- Senhas armazenadas com hash.
- Perfis de usuário.
- Restrição de cadastro de usuários ao administrador.
- Logout de sessão.
- Redefinição de senha por link com validade.
- Cabeçalhos de segurança na aplicação.
- Separação do acesso técnico mobile do acesso administrativo.
- Uso de variáveis de ambiente para configurações sensíveis.

---

## 22. Backup

O projeto possui rotina de backup do banco de dados e integração com Google Drive, quando configurada.

### Funcionalidades

- Geração de backup do banco.
- Envio de backup ao Google Drive.
- Configuração por credenciais e pasta do Google Drive.
- Comando administrativo para auditoria e execução de backup.
- Rota protegida para execução de backup por usuários autorizados.

### Benefícios

- Reduz risco de perda de dados.
- Facilita cópia externa de segurança.
- Mantém histórico de proteção da informação.

---

## 23. Tecnologia Utilizada

O sistema foi desenvolvido como aplicação web.

### Principais tecnologias

- Python.
- Flask.
- SQLAlchemy.
- Flask-Login.
- Flask-Migrate.
- Banco SQLite em ambiente local ou PostgreSQL em ambiente publicado.
- Bootstrap para interface.
- Pandas, OpenPyXL e XlsxWriter para planilhas.
- ReportLab e PDFKit para geração de PDFs.
- Google Drive API para backup.
- Brevo/SMTP para envio de e-mails, quando configurado.

---

## 24. Benefícios para a Empresa

O LogiStock contribui diretamente para a gestão da operação.

### Benefícios principais

- Mais controle sobre estoque e materiais em campo.
- Menos perda de materiais.
- Menos retrabalho com planilhas.
- Melhor rastreabilidade por técnico, cliente e ordem de serviço.
- Maior transparência sobre entradas e saídas.
- Agilidade para registrar uso de materiais pelo celular.
- Relatórios para tomada de decisão.
- Evidências para auditorias e conferências.
- Controle de ferramentas, EPIs e frota em um único sistema.
- Organização das pendências de aprovação.

---

## 25. Conclusão

O LogiStock é uma ferramenta de controle operacional que reúne em uma única plataforma os principais processos ligados a estoque, materiais, técnicos, baixas, inventários, ferramentas, EPIs, notas fiscais, clientes, ordens de serviço e frota.

Com o uso do sistema, a empresa passa a ter maior rastreabilidade, segurança, organização e capacidade de acompanhamento das operações diárias. A documentação gerada pelo sistema, como relatórios, PDFs, planilhas, termos e históricos, contribui para uma gestão mais profissional e confiável.
