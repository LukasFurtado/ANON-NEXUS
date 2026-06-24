# Changelog

Todas as alterações relevantes do NEXUS ANON devem ser registradas neste arquivo. A partir desta versão, toda atualização funcional, visual ou documental deve incrementar a versão do projeto.

## [1.6.2] - 2026-06-24

### Alterado

- Contrato do Ollama reforcado: a IA local passa a ser orientada explicitamente a atuar apenas como detector de entidades sensiveis, sem reescrever, resumir, interpretar, gerar documentos ou produzir texto anonimizado.
- Backend passa a descartar entidades retornadas pela IA quando `text`, `start` e `end` nao correspondem exatamente ao trecho literal do documento original.
- Arquitetura documentada em changelog como fluxo de substituicao controlada: deterministico primeiro, IA apenas para contexto semantico residual, substituicao/exportacao sempre pelo backend.

## [1.6.1] - 2026-06-24

### Adicionado

- Arquivos de entrada `.csv` agora tambem geram produto anonimizado em `.csv`, preservando o conteudo tabular anonimizado sem cabecalho institucional ou tabela de controle.
- Botao **CSV** passa a aparecer automaticamente apenas quando o backend informa que o produto CSV existe.
- Log PDF do conjunto passa a registrar tambem o hash SHA-256 do produto CSV quando aplicavel.

## [1.6.0] - 2026-06-24

### Adicionado

- Processamento em lote real para ate 3 arquivos, com dicionario unico de substituicoes para manter a mesma entidade com o mesmo identificador anonimo em todos os arquivos da solicitacao.
- Tabela de Controle de Anonimizacao ao final dos produtos internos TXT, DOCX e PDF, listando valor original, tipo, identificador anonimo e quantidade de ocorrencias efetivamente substituidas.
- Log PDF do conjunto processado, com numero IP/nome da solicitacao, arquivos tratados, hashes SHA-256 originais e hashes dos produtos TXT, DOCX e PDF, registro de data/hora, host cliente e identificacao da maquina local quando disponivel.
- Botao **Log PDF** no historico da solicitacao, com validacao de SHA-256 antes do download.

### Alterado

- Janela de regras passa a se chamar **⚠ Regras institucionais de uso e Avisos ⚠**, com lista reduzida de avisos essenciais, alerta vermelho sobre fase de testes e recomendacao expressa de anonimizacao manual quando houver falha automatica.
- Quadro de regras passa a exibir a logo da PCPE na lateral direita.

### Corrigido

- Logo da PCPE no PDF exportado agora e centralizada no cabecalho.

## [1.5.8] - 2026-06-24

### Corrigido

- Exportação TXT deixa de quebrar linhas delimitadas de CSV/RIF, preservando cabeçalhos e linhas com ponto e vírgula.
- Detector CSV do perfil RIF passa a ter prioridade sobre regex genéricas, evitando que contas bancárias em coluna `contaEnvolvido` sejam classificadas como telefone.

## [1.5.7] - 2026-06-23

### Adicionado

- Suporte à anexação e extração de arquivos `.csv`, formato primordial para RIF/COAF e exportações Siscoaf.
- Leitura local de CSV com tentativas de codificação `utf-8-sig`, `utf-8`, `cp1252` e `latin-1`, preservando delimitadores e linhas para o perfil estratégico RIF.

## [1.5.6] - 2026-06-23

### Corrigido

- Fila de arquivos anexados e hashes locais agora são limpos automaticamente ao final do processamento, deixando a tela pronta para nova solicitação.

## [1.5.5] - 2026-06-23

### Alterado

- Janela **Regras institucionais de uso** atualizada com observações baseadas na Portaria Normativa DG/PCPE nº 29/2026, incluindo PIGIA, revisão humana qualificada, sigilo, LGPD, minimização de dados, rastreabilidade, responsabilidade funcional e vedação à automação decisória.

## [1.5.4] - 2026-06-23

### Corrigido

- Coluna lateral esquerda deixou de ter limite fixo de altura e rolagem interna, passando a acompanhar integralmente a altura do conteúdo da página.

## [1.5.3] - 2026-06-23

### Alterado

- Bloco lateral **NEXUS ANON / Anonimização institucional offline** centralizado e tipografia ampliada em aproximadamente 10%.

## [1.5.2] - 2026-06-23

### Alterado

- Perfil estratégico **RIF / COAF** aperfeiçoado com regras do Modelfile AnonRIF final para exportações Siscoaf, CSVs de Comunicações, Envolvidos e Ocorrências.
- Perfil RIF passa a orientar preservação de colunas, delimitadores, linhas, campos vazios, indicadores operacionais e classificações como `tipoEnvolvido`, PEP e servidor público.
- Regex do perfil RIF ampliado para campos como `idComunicacao`, `idOcorrencia`, `NumeroOcorrenciaBC`, `cpfCnpjComunicante`, `cpfCnpjEnvolvido`, `agenciaEnvolvido` e `contaEnvolvido`.
- Texto de ciência alterado para **Eu estou ciente das regras de uso e concordo.**
- Textos da janela **Regras institucionais de uso** ajustados para formatação justificada.

### Removido

- Texto auxiliar **Obrigatório para liberar a anonimização.**

## [1.5.1] - 2026-06-23

### Adicionado

- Ciência obrigatória de regras institucionais antes de liberar o botão **Anonimizar**.
- Janela modal com regras de uso, sigilo, validação humana, cadeia de custódia e responsabilidade operacional.

### Alterado

- Checkbox **Usar Ollama local** substituído por **Eu estou ciente das regras de uso.**
- Botão **Anonimizar** agora exige arquivo, nome da solicitação e confirmação das regras de uso.

## [1.5.0] - 2026-06-23

### Adicionado

- Campo **Perfil documental estratégico** passa a alterar efetivamente a estratégia do pipeline.
- Novo módulo de estratégias por perfil documental, com instruções específicas para RIF/COAF, inquérito, relatório, ofício, administrativo e automático.
- Prompt enviado ao Qwen3 agora recebe instruções específicas do perfil selecionado.
- Regex passa a incluir padrões adicionais conforme o perfil documental.
- Validação passa a aplicar critérios protegidos por perfil, incluindo preservação reforçada de valores, datas e termos financeiros no RIF.
- Exportações passam a registrar o perfil documental usado no resumo operacional.

### Alterado

- O campo de perfil documental deixou de ser apenas metadado e passou a influenciar anonimização, reconhecimento e validação.

## [1.4.4] - 2026-06-23

### Alterado

- Logo da PCPE no canto superior esquerdo ampliada em mais 20%, com ajuste proporcional da caixa institucional.

## [1.4.3] - 2026-06-23

### Corrigido

- Anexar arquivos em seleções separadas agora adiciona novos documentos à fila existente, em vez de substituir o arquivo anterior.
- Mantido o limite de 3 arquivos por solicitação, com aviso quando o limite for ultrapassado.
- Arquivos repetidos passam a ser recusados com aviso específico.

## [1.4.2] - 2026-06-23

### Alterado

- Página inicial passa a exibir **Resumo operacional - Última solicitação**.
- Resumo operacional informa a data e hora de registro da solicitação vinculada.

## [1.4.1] - 2026-06-23

### Alterado

- Chamadas ao Qwen3 via Ollama passam a enviar `/no_think` e `think: false`.
- Modelfile `AnonRIF2.modelfile` atualizado para proibir pensamento visível, tags `<think>` e justificativas internas.
- Serviço local agora remove preventivamente blocos `<think>...</think>` antes de interpretar a resposta JSON.

## [1.4.0] - 2026-06-23

### Adicionado

- Exportação auditada: PDF, DOCX e TXT agora são baixados após conferência local do SHA-256 informado na interface.
- Confirmação de exclusão irreversível para solicitações salvas no histórico.
- Texto de etapa momentânea durante o processamento local.
- Limite operacional de 3 arquivos por solicitação.
- Seção única e destacada para hashes SHA-256 do original e dos produtos exportáveis.
- Resumo operacional incorporado aos arquivos TXT, DOCX e PDF gerados.

### Alterado

- DOCX exportado passa a usar corpo alinhado à esquerda.
- Barra de exportação passa a indicar com mais precisão que o arquivo é o produto final de anonimização.
- Logo PCPE do topo foi centralizada e ampliada dentro da caixa institucional.
- Resumo operacional passa a destacar o Número IP / Nome solicitação e o arquivo consultado.

### Corrigido

- Regra de nomes em transações financeiras ajustada para preservar expressões como “transferência PIX para” e anonimizar somente o destinatário.

## [1.3.5] - 2026-06-23

### Adicionado

- Aviso institucional em vermelho na janela de processamento informando que anonimização local de documentos extensos pode exigir alto poder computacional.

## [1.3.4] - 2026-06-23

### Corrigido

- Removida a barra de rolagem interna da área verde de arquivos anexados.
- A rolagem dos anexos passa a ser feita pela barra lateral inteira, evitando aparência de botão truncado.

## [1.3.3] - 2026-06-23

### Corrigido

- Corrigido o upload quando o usuário remove um arquivo e tenta anexar o mesmo arquivo novamente.
- O campo interno de seleção de arquivos agora é limpo após anexar ou remover arquivos, permitindo nova seleção do mesmo item.

## [1.3.2] - 2026-06-23

### Corrigido

- Corrigida a responsividade geral para evitar tela truncada em navegador embutido ou janelas menores.
- Adicionada rolagem própria na barra lateral em telas altas/estreitas.
- Ajustadas larguras mínimas de painéis, listas, hashes e blocos de auditoria para evitar corte horizontal.

## [1.3.1] - 2026-06-23

### Alterado

- Campo **Nome da solicitação** renomeado para **Número IP / Nome solicitação**.
- Botão **Anonimizar** agora permanece bloqueado até que o usuário informe o número/nome da solicitação.

## [1.3.0] - 2026-06-23

### Adicionado

- Painel de controle de sigilo e integridade na aba **Processamento**.
- Cálculo local de SHA-256 dos arquivos anexados antes da anonimização.
- Exibição do hash original ainda na fila de arquivos anexados.
- Botão para copiar hash SHA-256 antes do processamento.
- Painel central com modelo, quantidade de arquivos e hashes originais da solicitação.

### Alterado

- Aba **Processamento** passa a usar a mesma lógica visual/informativa de auditoria aplicada ao histórico.
- Informações sensíveis continuam fora da tela principal; a interface prioriza rastreabilidade, integridade e status operacional.

## [1.2.9] - 2026-06-23

### Adicionado

- Bloco de auditoria no resultado com selo **DOCUMENTO PROCESSADO COM SUCESSO**.
- Hash SHA-256 do arquivo original enviado.
- Hash SHA-256 de cada produto exportado: PDF, DOCX e TXT.
- Botões para copiar hashes individualmente.
- Tempo total de processamento no resultado.
- Informação sobre uso de OCR.
- Informação de preservação estrutural.
- Status de validação.

### Alterado

- Página **Histórico de anonimização** deixou de exibir cards de datas e valores.
- Resumo operacional prioriza informações institucionais de auditoria e integridade.

## [1.2.8] - 2026-06-23

### Adicionado

- Detector automatico de modelos locais instalados no Ollama.
- Botao **Detectar** na secao **Modelo local**.
- Consulta ao endpoint local do Ollama `/api/tags` pelo backend.
- Exibicao do estado da deteccao de modelos na interface.

### Alterado

- A lista de modelos da interface deixou de ser fixa e passa a usar os modelos detectados localmente.
- A rota `/api/models` agora retorna modelos recomendados, instalados, lista consolidada e estado de disponibilidade do Ollama.

## [1.2.7] - 2026-06-23

### Corrigido

- Corrigida a integração com o modelo Ollama especializado: o app agora aponta para `NEXUS-anon:latest`, que já existe localmente e deriva de `qwen3:32b`.
- Corrigido erro da rota `/api/models`, que podia retornar erro interno por tipagem incompatível da resposta.
- Reforçada a detecção local para nomes em construções comuns, como “Nome Completo, CPF ...” e transferências “para Nome Completo”.
- Adicionada detecção local de endereço em expressões como “residente na Rua ..., nº ...”.

### Alterado

- Exportação DOCX passa a usar o modelo institucional `modelo_raf.docx` como base.
- Exportação PDF passa a ter cabeçalho institucional, logo e formatação coerente com o padrão documental.
- Exportação TXT passa a organizar linhas e metadados de origem.
- A tela deixou de exibir o texto integral original/anonimizado em caixas longas, passando a mostrar resumo operacional com estatísticas e exportações.
- “Solicitações de anonimização” foi alterado para “Histórico de anonimização”.
- Adicionada opção de nomear uma solicitação antes do processamento.
- Adicionada opção de renomear solicitações já existentes.

### Adicionado

- Modelfile anexado incorporado em `backend/resources/ollama/AnonRIF2.modelfile`.
- Modelo DOCX anexado incorporado em `backend/resources/templates/modelo_raf.docx`.
- Script `scripts/create-anonrif2-model.ps1` para recriar localmente o modelo `NEXUS-anon:latest` a partir do Modelfile.
- Documentação `docs/OLLAMA_MODELFILE.md`.

## [1.2.6] - 2026-06-23

### Adicionado

- Persistência local das solicitações no navegador, evitando perda do histórico ao sair ou atualizar a página.
- Aba **Solicitações** para consultar grupos de anonimização já executados.
- Agrupamento de múltiplos arquivos enviados juntos como uma única solicitação.
- Consulta individual de arquivos dentro de cada solicitação.
- Visualização do produto da anonimização por arquivo.
- Upload múltiplo de arquivos.
- Recomendação operacional para anexar arquivos da mesma extensão e do mesmo trabalho investigativo.
- Destaque verde para arquivos anexados corretamente.
- Opção para remover arquivo já anexado antes do processamento.
- Janela de processamento com nome do arquivo atual, contador de tempo e botão de cancelamento.
- Indicação de arquivo atual no formato “arquivo X de Y”.
- Aviso institucional para arquivos extensos: processamento pode levar mais tempo.
- Botões nos painéis de comparação:
  - Copiar;
  - TXT;
  - DOCX;
  - PDF.
- Rodapé institucional com copyright, uso interno, criador e versão.
- Logo da Polícia Civil de Pernambuco no topo esquerdo.

### Alterado

- Título principal alterado para **Anonimização Forense de Documentos**.
- Botão **Anonimizar** alterado para tom dourado institucional.
- Interface visual redesenhada com identidade escura, azul institucional e detalhes dourados.
- Cabeçalhos dos painéis **Original** e **Anonimizado** ficaram mais visíveis.
- Placeholders dos painéis foram substituídos por mensagens mais institucionais:
  - “O conteúdo extraído do documento será exibido aqui.”
  - “O documento desidentificado será exibido aqui após o processamento.”
- Textos de layout foram ajustados para alinhamento justificado onde adequado.
- Rodapé atualizado para: “Criador: Lukas Furtado - Polícia Civil do Estado de Pernambuco.”
- Janela de processamento passou a exibir: “Processando solicitação, aguarde.”
- Textos visíveis da interface foram revisados para correção de acentuação.

### Técnico

- Frontend validado com TypeScript após as alterações.
- Histórico de solicitações salvo em `localStorage` com a chave `nexus-anon.requests.v1`.
- Ação de cancelamento implementada com `AbortController`.
- Logo institucional copiado para `frontend/public/logo_pcpe_header.png`.
- Estrutura de componentes do frontend expandida para suportar solicitações, grupos, arquivos e produtos.

## [1.0.0] - 2026-06-23

### Adicionado

- MVP inicial do NEXUS ANON.
- Backend local com FastAPI.
- Pipeline modular de anonimização:
  - identificação de formato;
  - extração de texto;
  - OCR opcional;
  - regex;
  - integração com Ollama;
  - validação;
  - exportação.
- Integração com modelo local via Ollama, com `qwen3:32b` como padrão.
- Suporte inicial a PDF, DOCX, DOC, TXT e RTF.
- Detecção por regex para identificadores sensíveis, incluindo CPF, CNPJ, e-mail, telefone, CEP, placa, IP, MAC, contas, agências, PIX, processos e protocolos.
- Exportação em TXT, DOCX e PDF.
- Banco SQLite inicial para histórico básico do backend.
- Interface React + TypeScript.
- Configuração desktop com Tauri.
- Documentação inicial de arquitetura, roadmap e execução local.

### Técnico

- Separação de dependências principais e OCR opcional.
- Scripts de inicialização para backend, frontend e desktop.
- Configuração local/offline com API em `127.0.0.1:8000`.
- Integração prevista com Ollama em `127.0.0.1:11434`.
