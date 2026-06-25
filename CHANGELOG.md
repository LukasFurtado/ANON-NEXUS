# Changelog

## [2.0.0] - 2026-06-25

### Marco institucional

- Consolidada a versão `2.0.0` do ANON como plataforma local de anonimização documental com foco em consistência, auditoria, rastreabilidade e operação institucional.
- Fortalecido o NCE como camada de coordenação do processamento, articulando parser, regras determinísticas, IA local, validação, substituição, exportação e histórico.
- Reforçado o princípio operacional do ANON: substituir identificadores sensíveis sem interpretar, resumir ou reescrever o conteúdo documental.

### Adicionado

- Sincronização de anonimização por pacote interno JSON, permitindo reutilizar em nova demanda os mesmos termos e os mesmos marcadores de uma anonimização anterior.
- Botão de download do pacote de sincronização em cada resultado processado, separado dos produtos externos e tratado como artefato interno restrito.
- Caixa de importação de pacote de sincronização na tela de processamento para reaplicar marcadores já usados em outro arquivo ou outra solicitação.
- Suporte inicial à leitura de log TXT de reanálise dirigida quando houver dados suficientes para reconstruir pares de substituição.
- Log próprio da reanálise dirigida, com termos aplicados, termos não encontrados, marcador usado, ocorrências substituídas, hashes e orientação de revisão.
- Reanálise dirigida acumulativa, permitindo informar vários termos antes de reprocessar.
- Janela de carregamento da reanálise dirigida durante a geração do novo produto.
- Botão de download do novo produto e do log da reanálise no próprio painel.
- Detecção de possível CPF incompleto por remoção de zero inicial, com aviso específico para revisão humana.
- Testes de regressão para sincronização de anonimização, reanálise dirigida, detecção de CPF com zero inicial ausente e validação pós-anonimização.

### Alterado

- Campo de marcador da reanálise dirigida deixou de ser opcional e passou a funcionar como complemento informado pelo operador.
- O tipo escolhido monta automaticamente o marcador completo; por exemplo, tipo `Pessoa` e complemento `123` geram `[PESSOA_123]`.
- Menu de tipo da reanálise recebeu correção visual para evitar fundo branco com texto ilegível.
- Painel de processamento passa a exibir somente mensagens informativas em transição, sem texto fixo concorrente.
- Conjunto de mensagens rotativas do processamento foi ampliado para orientar o operador sobre extração, regras, IA local, preservação documental, hashes, auditoria e revisão humana.
- A reanálise dirigida deixa de registrar como substituição bem-sucedida termos que não foram encontrados no texto extraído.
- Produtos gerados pela reanálise carregam hashes próprios e preservam o registro original da solicitação anterior.
- Importação de pacote de sincronização pré-carrega o dicionário de substituições e força a detecção dos termos sincronizados no novo documento.

### Corrigido

- Corrigida situação em que termos adicionados manualmente poderiam aparecer como controlados mesmo sem ocorrência real no texto reprocessado.
- Melhorada a rastreabilidade de correções posteriores ao processamento inicial, permitindo unir o resultado final corrigido em um pacote reutilizável.
- Adicionado alerta de CPF possivelmente incompleto quando um valor de 10 dígitos, em contexto de CPF, se torna válido ao recolocar zero inicial.
- Evitada exposição do número suspeito no aviso de CPF incompleto, mantendo apenas indicação de linha e quantidade para revisão.

### Auditoria e segurança

- Pacotes de sincronização são gerados como artefatos internos e não como produto externo para compartilhamento.
- O pacote de sincronização contém correspondências necessárias à consistência entre demandas e deve ser tratado como material restrito.
- Logs de reanálise indicam explicitamente que o texto informado pelo operador deve ser exatamente igual ao texto extraído pelo ANON.
- Resultados históricos em `data/exports` não foram regravados para preservar a versão real que gerou cada auditoria anterior.

## [1.8.39] - 2026-06-24

### Adicionado

- Janela de processamento passa a exibir monitor local de recursos em tempo real, com uso de processador, GPU quando detectada e consumo de memoria.
- Backend passa a disponibilizar leitura local de metricas do sistema sem envio de dados para a internet.

## [1.8.38] - 2026-06-24

### Corrigido

- Corrigida a causa-raiz da contamina??o do campo `Indexador` em CSV/RIF: valores num?ricos curtos n?o s?o mais propagados globalmente por substitui??o textual.
- Adicionado bloqueio anti double-hit para impedir duas substitui??es sobre o mesmo intervalo textual.
- Entidades p?blicas e institui??es operacionais passam a ser preservadas no perfil `rif`.
- Avisos repetidos de preserva??o do perfil `extrato_bancario` passam a ser consolidados, evitando relat?rios extensos e pouco acion?veis.
- A Tabela de Controle de Anonimiza??o deixa de ser anexada aos produtos finais TXT, DOCX e PDF; agora ? gerada como arquivo separado `controle_interno.pdf`.
- Removido o ap?ndice interno revers?vel do PDF fac-s?mile para impedir vazamento de valores originais no documento anonimizado.

### Adicionado

- Novo download complementar `CONTROLE`, destinado exclusivamente a auditoria interna e cadeia de cust?dia.
- Testes de regress?o para `Indexador`, sobreposi??o de entidades, preserva??o de entidades p?blicas no RIF e consolida??o de avisos DELOS.

## [1.8.37] - 2026-06-24

### Corrigido

- Corrigida a acentua??o dos textos vis?veis da interface, da janela de regras institucionais, do guia de instala??o e do README.
- Normalizados textos UTF-8 que apareciam como caracteres quebrados em navegadores e documentos de orienta??o.

## [1.8.36] - 2026-06-24

### Alterado

- `qwen3:32b` passa a ser o único modelo local padrão do ANON e da IA NEXUS.
- `NEXUS-anon:latest` deixou de ser recomendado, criado pelo instalador ou exibido como opção selecionável quando detectado no Ollama.
- A especialização antes concentrada no Modelfile passa a ficar no próprio ecossistema do ANON: prompts, perfis JSON, regras determinísticas, validador, corretor de JSON, classificador de qualidade e resumo seguro.
- Formalizado o `NCE-ANON`, Núcleo de Comportamento Especializado do ANON, com documentação própria em `docs/COMPORTAMENTO_ESPECIALIZADO.md`.
- Chamadas ao `qwen3:32b` para detecção passam a enviar `temperature=0`, `top_p=0.9`, `repeat_penalty=1.1`, `think=false`, `/no_think` e `format=json`.
- `scripts/create-anonrif2-model.ps1` passa a verificar a presença do `qwen3:32b`, sem recriar modelo derivado.
- Documentação do Ollama atualizada para tratar o Modelfile como referência técnica arquivada, não como etapa obrigatória de instalação.

### Auditoria

- Mantida a avaliação da comunicação IA/JSON: blocos enviados à IA, blocos recusados por JSON não aproveitável, tentativas de correção e correções aceitas.
- Essas métricas seguem registradas nos metadados do resultado e no arquivo complementar de avisos para revisão humana.

## [1.8.35] - 2026-06-24

### Adicionado

- Perfis documentais estruturados em JSON para `RIF/COAF`, `Extrato bancario` e `Relatorio investigativo`, com regras de preservacao, anonimização, campos ambiguos, falsos positivos e criterios de validacao.
- Carregador central de perfis documentais para alimentar prompt local, regras internas e contexto seguro da IA NEXUS.
- Resumo seguro por documento, persistido localmente sem texto original, com métricas agregadas, tipos de entidades, hashes, avisos sanitizados e etapas concluídas.
- Classificador automático de qualidade (`Bom`, `Revisar`, `Atenção crítica`) exibido no histórico com janela explicativa.
- Emissor de estado do pipeline, registrando etapas como parser, regex, IA local, validação, substituição e exportação.
- Endpoints locais para consulta de resumo seguro e estado do processamento.
- Painel visual de estado do processamento dentro do resumo operacional.
- Scripts `install.py` e `install_check.py` para facilitar instalação e diagnóstico do ecossistema em outro computador.
- Testes unitários para carregamento de perfis, resumo seguro, classificação de qualidade e estado do pipeline.

### Alterado

- IA NEXUS passa a receber apenas contexto seguro persistido, sem conteúdo original do documento.
- Chat institucional passa a ocultar nomes de arquivos, caminhos, formatos internos de resposta, eventos internos, logs e estrutura interna do ANON.
- Prompt enviado ao Ollama passa a incorporar o contexto estruturado do perfil documental selecionado.
- Regras determinísticas foram reforçadas para RIF/COAF, incluindo contexto de empresas, envolvidos, comunicantes e chaves PIX por e-mail.
- O manifesto de integridade passa a abranger os novos módulos críticos de comunicação, perfil, resumo seguro, qualidade e instalação.

## [1.8.34] - 2026-06-24

### Alterado

- Mensagens do usuário nos chats passam a ser identificadas como `Anonymous`.
- Adicionado avatar local `anonymous-avatar.png` para representar o usuário Anonymous no chat da solicitação e no balão temporário da IA NEXUS.

## [1.8.33] - 2026-06-24

### Alterado

- IA NEXUS volta a consultar o modelo local fixo definido em `NEXUS_ANON_NEXUS_ASSISTANT_MODEL`.
- Chat da solicitação informa que está vinculado à IA local e passa a responder sobre ANON, características do produto anonimizado, revisão humana obrigatória e condutas gerais diante de erro.
- Balão temporário durante processamento também pode consultar a IA local para orientações institucionais, mesmo antes de existir produto final.
- Prompt da IA NEXUS foi restringido para não expor nomes de arquivos, caminhos, código, JSON, backend, eventos internos, logs internos ou estrutura interna do sistema.

## [1.8.32] - 2026-06-24

### Alterado

- Balão flutuante da IA NEXUS passa a aparecer somente durante o processamento iniciado pelo botão `Anonimizar`.
- Ao encerrar o carregamento/processamento, o balão flutuante da IA NEXUS é fechado automaticamente.
- Conversas após o processamento ficam concentradas no chat individual de cada solicitação.
- Chat da solicitação recebeu visual mais próximo de conversa com IA, com identidade da IA NEXUS, bolhas, atalhos institucionais, rolagem automática e campo de mensagem mais destacado.

## [1.8.31] - 2026-06-24

### Corrigido

- Histórico passa a recuperar automaticamente arquivos presos em `processando` quando não há execução ativa.
- Arquivos interrompidos antes de retornar resultado são marcados como `erro` com mensagem operacional para reprocessamento e auditoria.
- IA NEXUS passa a responder somente orientações institucionais sobre finalidade, sigilo, preservação documental e revisão humana.
- Chat deixa de expor JSON, eventos internos, nomes de arquivos, falhas técnicas, logs ou detalhes da estrutura interna do ANON.

## [1.8.30] - 2026-06-24

### Adicionado

- Chat flutuante da IA NEXUS passa a exibir a opção `Cancelar` enquanto a última mensagem estiver em processamento.
- Cancelamento interrompe a consulta local em andamento e registra aviso de cancelamento pelo operador.

## [1.8.29] - 2026-06-24

### Alterado

- Campo de conversa do painel de diagnóstico passa a exibir `Fale com a IA NEXUS.`

## [1.8.28] - 2026-06-24

### Alterado

- IA NEXUS passa a usar um modelo local fixo e próprio, definido por `NEXUS_ANON_NEXUS_ASSISTANT_MODEL`.
- O modelo escolhido pelo operador para anonimização dos documentos não altera mais a IA que responde no chat.
- Contexto técnico do diagnóstico mantém o modelo de anonimização apenas como informação do processamento, não como motor de resposta da IA NEXUS.

## [1.8.27] - 2026-06-24

### Alterado

- Chat flutuante da IA NEXUS passa a rolar automaticamente para a última mensagem.
- Janela da IA NEXUS foi ampliada para melhorar leitura de respostas longas.
- Fonte padrão da conversa foi aumentada.
- Adicionados controles `A-`, `A` e `A+` para ajustar o tamanho da fonte da conversa.
- Removidas falas técnicas com o termo `backend` das respostas voltadas ao operador.

## [1.8.26] - 2026-06-24

### Corrigido

- Timer da janela de processamento deixa de depender de incremento acumulado e passa a calcular o tempo pelo horário real de início.
- Re-renderizações da interface durante a anonimização não reiniciam mais a contagem visual do tempo.

## [1.8.25] - 2026-06-24

### Alterado

- Indicador de resposta da IA NEXUS deixa de exibir `...` estático e passa a usar pontos animados em sequência.
- Painel técnico de diagnóstico usa o mesmo indicador animado durante análise de resposta.

## [1.8.24] - 2026-06-24

### Corrigido

- IA NEXUS passa a responder localmente perguntas simples sobre tempo, duração e demora do processamento, sem encaminhar a consulta ao Ollama.
- Chat flutuante passa a ter limite de espera na consulta técnica ao backend, evitando permanência indefinida no estado `...`.
- Painel técnico formal também passa a enviar o tempo de processamento ao diagnóstico local.
- Diagnóstico backend responde perguntas de tempo diretamente com os metadados do processamento quando disponíveis.

## [1.8.23] - 2026-06-24

### Adicionado

- Criado barramento local de comunicação operacional entre as células do ANON.
- Cada etapa do pipeline passa a registrar eventos seguros: arquivo recebido, hash de origem, extração textual, OCR, regex, IA local, validação, anonimização e exportação.
- Resultado da anonimização passa a retornar `communication_events` e `communication_summary` para alimentar a IA NEXUS e o painel de diagnóstico.
- Assistente IA NEXUS passa a informar quantos eventos internos foram registrados e qual foi o último estágio observado.
- Diagnóstico local passa a responder perguntas sobre comunicação interna, células envolvidas e distribuição dos eventos.
- Base operacional local passa a documentar o protocolo de células: o que cada uma precisa e o que cada uma oferece ao ecossistema ANON.

### Alterado

- Arquivos complementares de auditoria passam a incluir resumo da comunicação interna quando disponível.
- Proteção de integridade passa a abranger o novo barramento de comunicação.

## [1.8.22] - 2026-06-24

### Adicionado

- Chat flutuante **IA NEXUS** para acompanhar o processamento enquanto a anonimização está em andamento.
- A IA NEXUS anuncia o início do processamento, explica a fase atual, orienta o operador a aguardar e permanece disponível para perguntas.
- Ao final do processamento, a IA NEXUS resume substituições, avisos, produtos disponíveis e métricas de JSON recusado/correções aproveitadas.
- Perguntas feitas durante o processamento recebem respostas operacionais locais sem expor o conteúdo dos documentos.
- Base operacional local passa a documentar o papel, limites e condutas da IA NEXUS como observadora institucional do processamento.

### Alterado

- O fluxo visual de processamento passa a ter uma camada ativa de comunicação com o operador, sem substituir o painel formal de diagnóstico da solicitação.

## [1.8.21] - 2026-06-24

### Adicionado

- Base operacional local `ANON-OPERATIONAL-KNOWLEDGE-v1` para alinhar contrato JSON, perfis documentais, termos protegidos, validação e diagnóstico técnico.
- Serviço interno de conhecimento para reutilizar as mesmas regras entre prompt do Ollama, correção de JSON, validação e painel de diagnóstico.
- Assistente técnico local na página da solicitação para explicar recusas de JSON, avisos, uso da IA local e métricas de comunicação ANON/Ollama.
- Contrato JSON explícito nos prompts enviados ao Ollama e na chamada local de correção de resposta.
- Arquivo `Avisos` passa a registrar também o contrato JSON operacional exigido da IA local.

### Alterado

- Validação por perfil passa a consultar a base operacional de termos protegidos além das regras fixas do código.
- Proteção de integridade passa a incluir a base operacional e o serviço de conhecimento.
- Textos novos do painel de comunicação ANON/IA local foram revisados com acentuação.

## [1.8.20] - 2026-06-24

### Alterado

- Avisos de validação deixam de ser inseridos dentro dos documentos anonimizados TXT e PDF.
- Quando houver avisos, o ANON gera um produto complementar para download chamado `Avisos`.
- O arquivo `Avisos` referencia a solicitação, arquivo de origem, hashes, modelo, versão, avisos registrados e considerações finais.
- O ANON passa a registrar métricas da resposta JSON da IA local: blocos processados, blocos recusados por JSON não aproveitável, tentativas de correção e correções aproveitadas.
- Log PDF do conjunto passa a registrar também o hash do produto complementar de avisos quando existir.

## [1.8.19] - 2026-06-24

### Corrigido

- Avisos de erro deixam de permanecer no topo global do `Histórico de anonimização` ao trocar de solicitação.
- Erros de processamento passam a ficar vinculados ao arquivo/solicitação correspondente dentro do histórico.
- Botão `Baixar log de erros` foi mantido dentro do aviso contextual do arquivo com falha.

## [1.8.18] - 2026-06-24

### Corrigido

- Quando o Ollama responde em formato inadequado, o ANON realiza uma segunda chamada local solicitando a correção da resposta para JSON estruturado.
- Parser de entidades ficou mais flexível para aceitar mapas por categoria, como `{"PERSON":["Nome"]}`, além de listas e objetos com `entities`.
- Resposta da IA local ainda não aproveitável deixa de bloquear a solicitação e passa a gerar aviso de revisão.
- Produtos TXT e PDF passam a incluir, ao final, a seção `Avisos de validação - revisão obrigatória`, com justificativa quando a resposta da IA não for aproveitável.

## [1.8.17] - 2026-06-24

### Corrigido

- Resposta malformada do modelo local deixa de bloquear a solicitação quando o Ollama respondeu; o processamento segue com regras locais de apoio e aviso de revisão.
- Prompt enviado ao Ollama passa a exigir objeto JSON com chave `entities`, formato mais estável para o modo JSON do Ollama.
- Texto base do prompt da IA foi normalizado em ASCII para evitar instruções com acentuação corrompida.
- Tempo limite padrão do Ollama ampliado para 3600 segundos, evitando falhas prematuras em modelos grandes sem criar espera infinita.

## [1.8.16] - 2026-06-24

### Adicionado

- Criado mecanismo institucional de verificação de integridade por manifesto SHA-256 dos arquivos críticos do ANON.
- Processamento e downloads passam a ser bloqueados quando a proteção de dados identifica alteração não autorizada em arquivos sensíveis do sistema.
- Adicionada rota local `/api/integrity` para consulta do estado de integridade institucional.
- O pacote de instalação passa a gerar o manifesto de integridade automaticamente antes da compactação.

## [1.8.15] - 2026-06-24

### Adicionado

- Adicionada proteção técnica de dados e integridade nos produtos exportados, vinculada à versão do ANON, ao arquivo de origem e à solicitação processada.
- DOCX e PDF passam a receber metadados internos de proteção de dados institucional.
- TXT, PDF, DOCX e log PDF passam a indicar `Protecao de dados: ativa` no resumo operacional quando aplicável.
- O log acumulativo de erros informa apenas a situação `Protecao de dados: ativa`, sem registrar detalhes internos do mecanismo.

## [1.8.14] - 2026-06-24

### Alterado

- Log de erros reforçado como arquivo acumulativo único, mantendo registros sucessivos de diferentes solicitações.
- Cada erro passa a registrar contexto técnico ampliado: rota local chamada, URL do Ollama, status de detecção do Ollama, modelos locais detectados e se o modelo selecionado estava instalado.
- Erros de processamento passam a incluir diagnóstico dos arquivos temporários envolvidos, com nome, extensão, tamanho em bytes e hash SHA-256, sem gravar o conteúdo integral dos documentos.
- O cabeçalho do log informa que o arquivo não substitui revisão humana e é destinado a suporte técnico e auditoria operacional local.

## [1.8.13] - 2026-06-24

### Adicionado

- Criado log local permanente de erros em `data/logs/anon_erros.txt`, atualizado automaticamente quando uma falha ocorre.
- Adicionada rota local `/api/logs/errors` para baixar o arquivo `ANON_log_erros.txt` pelo navegador.
- A faixa de erro da interface passa a exibir o botão `Baixar log de erros`, facilitando o envio do diagnóstico para suporte.
- O log registra data e hora, versão do ANON, etapa, modelo local, perfil documental, arquivos envolvidos, mensagem exibida e rastreamento técnico resumido.

## [1.8.12] - 2026-06-24

### Corrigido

- Leitura da resposta do Ollama ficou mais flexível para aceitar entidades em campos como `resultado`, `dados`, `entidades_detectadas`, `response` e `answer`.
- Itens de entidade retornados com nomes de campos em português, como `tipo`, `texto`, `valor`, `inicio` e `fim`, agora são normalizados antes da validação.
- Entidades sem offsets explícitos passam a ser localizadas pelo próprio texto literal, reduzindo falhas quando o modelo identifica a informação sensível mas não informa posições exatas.
- Versão exibida na interface, documentação e pacote de instalação atualizada para `1.8.12`.

## [1.8.11] - 2026-06-24

### Corrigido

- Aumentado o tempo limite de resposta do Ollama para modelos locais grandes, reduzindo falhas em carregamento/inferencia do Qwen 32B.
- Resposta do Ollama passa a aceitar lista JSON pura, objeto com `entities`, bloco `json` e JSON embutido em texto, evitando erro quando o modelo retorna a lista em formato envolvido.
- Quando a IA local responde validamente com lista vazia, o processamento segue com regras locais de apoio e registra aviso para revisão, em vez de bloquear a solicitação.

## [1.8.10] - 2026-06-24

### Alterado

- Removidos os indicadores laterais de modelo local e quantidade de arquivos do cabeçalho da solicitação.
- Cabeçalho da solicitação passa a manter foco em renomeação, Log PDF e exclusão, sem chips redundantes.

## [1.8.9] - 2026-06-24

### Alterado

- Tooltip dos produtos exportados deixa de exibir texto tecnico sobre verificacao de hash e passa a indicar `Arquivo [TIPO] anonimizado gerado.`
- Area de exportacao passa a destacar `Produtos gerados para download`, identificando melhor que os botoes correspondem aos arquivos anonimizados do arquivo em consulta.
- Botoes de download passam a mostrar tipo do arquivo e descricao `Arquivo anonimizado`.
- Botao `Log PDF` fica maior, mais destacado e identificado como `Auditoria do conjunto`.

## [1.8.8] - 2026-06-24

### Corrigido

- Removido BOM dos arquivos JSON do frontend, corrigindo falha do Vite/PostCSS com `Unexpected token` ao iniciar a interface.
- Validado que `package.json`, `package-lock.json`, `tsconfig.json` e `tauri.conf.json` iniciam diretamente com `{` e podem ser lidos pelo Node sem erro.

## [1.8.7] - 2026-06-24

### Alterado

- Removidos os perfis documentais `Inquerito policial`, `Relatorio`, `Oficio`, `Administrativo` e `Automatico` do contrato do backend e da interface.
- O ANON passa a exigir escolha explicita do perfil documental antes de liberar a anonimizacao.
- Historicos locais com perfis documentais removidos deixam de ser carregados como grupos validos na interface.
- Adicionado o perfil `Relatorio investigativo`, com prompt, regras regex e criterios de validacao proprios.

### Adicionado

- Perfil `Relatorio investigativo` orientado a relatorios policiais, ministeriais, administrativos e de controle, preservando estrutura, fundamentos, datas, valores, referencias procedimentais, orgaos publicos, unidades, bancos/plataformas como fontes de dados, municipios, estados e dados tecnicos nao pessoais.
- Regras especificas para anonimizar pessoas, autoridades individualizadas, matriculas, CPF, RG, CNH, passaporte, CNPJ de empresas privadas investigadas, telefones, e-mails, enderecos, contas, PIX, placas, usuarios de redes sociais e IPs individuais.

## [1.8.6] - 2026-06-24

### Corrigido

- Corrigida acentuação da interface principal, janela de regras, avisos, histórico, mensagens de processamento e alertas.
- Removidos trechos com mojibake visual, como `ç`, `ã`, `ó` e variações semelhantes, preservando UTF-8 correto.

## [1.8.5] - 2026-06-24

### Alterado

- Perfil `extrato_bancario` passa a priorizar saida unica em PDF quando o arquivo de entrada tambem for PDF.
- Exportacao de extrato bancario em PDF deixa de gerar TXT/DOCX para evitar produtos com formatacao inferior ao fac-simile preservado.
- Cada solicitacao passa a registrar a versao do ANON usada no resumo, selo de auditoria e log do conjunto.
- Mensagem de downloads passa a orientar analise individual dos produtos gerados e escolha do arquivo que melhor sintetiza os dados.

### Corrigido

- Integrado dicionario operacional DELOS para preservar coluna `Doc.`, identificadores `Requisicao` e `Numero de Caso`, codigos `Inst.`, ISPB/COMPE, placeholders nulos e historicos operacionais bancarios.
- Detector de extrato bancario passa a tratar o titular como entidade ancora e buscar variacoes em campos como `Nome Benef/Depos` e `POR [NOME]`.
- Reduzidos falsos positivos que classificavam historicos bancarios, agencias, contas operacionais e identificadores de transacao como pessoas, telefones ou identificadores pessoais.

## [1.8.4] - 2026-06-24

### Alterado

- IA local passa a ser obrigatória em todo processamento de anonimização.
- O backend deixa de seguir apenas por regex quando Ollama/modelo local não estiver disponível.
- Documentos longos passam a ser enviados ao Ollama em blocos, permitindo análise da íntegra do texto extraído, não apenas dos primeiros 12 mil caracteres.
- Prompt do modelo foi ajustado para que a IA também indique entidades evidentes, ainda que possam ser detectadas por regras determinísticas.
- Tela de processamento passa a indicar **IA local obrigatória**.

### Corrigido

- Caso a IA local não retorne entidades em documento onde regras de apoio detectaram dados sensíveis, o processamento é bloqueado com erro operacional claro.

## [1.8.3] - 2026-06-24

### Corrigido

- Falhas de comunicação com Ollama/modelo local deixam de ser silenciosas.
- Quando a IA local não responder, retornar JSON inválido ou o modelo estiver indisponível, o resultado passa a registrar aviso explícito de que a execução seguiu apenas com regras automáticas locais.
- Interface passa a explicar esse aviso em linguagem operacional, orientando verificar Ollama aberto e modelo instalado.

## [1.8.2] - 2026-06-24

### Corrigido

- Anonimização passa a executar uma segunda verificação determinística, substituindo ocorrências residuais dos valores já aprovados na tabela de controle pelo mesmo identificador anônimo.
- Reduzido o risco de um mesmo nome ou identificador permanecer no corpo quando apenas parte das ocorrências foi detectada inicialmente por posição.

### Adicionado

- Exportação PDF passa a tentar modo **fac-símile redigido** para PDFs de origem: o arquivo original é usado como base e os dados sensíveis localizados são cobertos/substituídos diretamente nas páginas.
- Quando o modo fac-símile é bem-sucedido, o PDF preserva a paginação e o layout original e recebe apêndice de auditoria ao final.
- Caso o modo fac-símile não esteja disponível no ambiente local, a exportação recai automaticamente para o modo textual anterior.

## [1.8.1] - 2026-06-24

### Corrigido

- Tela de recuperação do Chrome não apaga mais o histórico diretamente; agora oferece recarregamento sem exclusão e reparo com backup automático do histórico.
- Histórico local inválido passa a ser colocado em quarentena antes de qualquer remoção, preservando possibilidade de recuperação.
- Exportação DOCX passa a respeitar orientação paisagem quando o PDF original de entrada estiver deitado.
- Avisos de validação passam a ficar agrupados em painel recolhível, com explicações resumidas para leitura leiga.

## [1.8.0] - 2026-06-24

### Adicionado

- Perfil documental estratégico **Extrato bancário**, calibrado para anexos bancários detalhados e consolidados, com preservação de colunas, valores, datas, históricos, totais e estrutura operacional.
- Regras determinísticas adicionais para titular, CPF/CNPJ, agência, conta, requisição, número de caso e contrapartes em extratos bancários.
- Detecção da orientação do PDF original para exportar o PDF anonimizado em paisagem quando o documento de entrada estiver deitado.

### Alterado

- Título do navegador alterado para **ANON - ANONIMIZADOR**.
- Rodapé passa a linkar **Lukas Furtado** ao GitHub do criador e a versão ao repositório do NEXUS ANON.
- Removido o aviso superior **Produto disponível para consulta** quando a aplicação não está processando.
- Pacote de instalação passa a ser gerado como versão 1.8.0.

Todas as alterações relevantes do NEXUS ANON devem ser registradas neste arquivo. A partir desta versão, toda atualização funcional, visual ou documental deve incrementar a versão do projeto.

## [1.7.6] - 2026-06-24

### Corrigido

- README revisado e regravado com acentuacao correta em portugues.
- Corrigidos trechos com mojibake e palavras sem acento na documentacao principal.
- Pacote de instalacao passa a ser gerado como versao 1.7.6.
## [1.7.5] - 2026-06-24

### Alterado

- Janela **Regras institucionais de uso e Avisos** ampliada para ocupar melhor a altura disponivel da tela.
- Espacamentos internos da janela de regras compactados para reduzir rolagem sem perder legibilidade.
- Pacote de instalacao passa a ser gerado como versao 1.7.5.
## [1.7.4] - 2026-06-24

### Corrigido

- Corrigida falha que podia deixar o Chrome exibindo apenas o fundo da aplicacao quando o bundle JavaScript quebrava por operadores internos corrompidos.
- Adicionada tela de recuperacao de carregamento com opcao para limpar dados locais antigos do Chrome e recarregar a interface.
- Historico salvo no navegador passa por validacao antes de ser usado, evitando tela vazia por dados locais antigos ou incompletos.
- Pacote de instalacao passa a ser gerado como versao 1.7.4.
## [1.7.3] - 2026-06-24

### Corrigido

- Layout principal ajustado para melhor compatibilidade com Google Chrome, evitando corte visual em larguras intermediarias e zoom diferente de 100%.
- Sidebar passa a ter largura adaptavel, viewport usa `100dvh` e o modo responsivo e ativado mais cedo.
- Pacote de instalacao passa a ser gerado como versao 1.7.3.
## [1.7.2] - 2026-06-24

### Alterado

- Titulo do bloco inicial do guia de instalacao alterado para **Tutorial simplificado de instalacao NEXUS ANON**.
- Pacote de instalacao passa a ser gerado como versao 1.7.2.
## [1.7.1] - 2026-06-24

### Alterado

- Guia `INSTALACAO_NEXUS_ANON.html` atualizado com links oficiais para Python, Node.js, Ollama, qwen3:32b, Tesseract OCR e LibreOffice.
- Pacote de instalacao passa a ser gerado como versao 1.7.1.
## [1.7.0] - 2026-06-24

### Adicionado

- Instalador assistido `INSTALAR_NEXUS_ANON.bat` para preparar backend, frontend, dependencias locais, Ollama e atalho na Area de Trabalho.
- Inicializador `ABRIR_NEXUS_ANON.bat` para ligar os servicos locais e abrir automaticamente a interface no navegador.
- Link local `NEXUS_ANON.url` apontando para `http://localhost:5173/`.
- Gerador de pacote `GERAR_PACOTE_NEXUS_ANON.bat`, com ZIP limpo sem `.venv`, `node_modules`, dados locais, logs ou cache.
- Documento visual `INSTALACAO_NEXUS_ANON.html` com requisitos, passo a passo, observacoes sobre qwen3:32b, Ollama, OCR e problemas comuns.

### Alterado

- Scripts de inicializacao passam a evitar reinstalacao diaria desnecessaria quando `.venv` e `node_modules` ja existem.
## [1.6.7] - 2026-06-24

### Corrigido

- Textos da interface revisados para remover caracteres corrompidos em acentuação portuguesa.
- Janela **Regras institucionais de uso e Avisos** consolidada em uma única versão com acentuação correta.
- Rodapé institucional e mensagens de resumo ajustados para exibição correta no frontend.
## [1.6.6] - 2026-06-24

### Corrigido

- Removido BOM UTF-8 de arquivos de configuração do frontend e Tauri para corrigir erro do Vite/PostCSS ao ler `package.json`.

## [1.6.5] - 2026-06-24

### Alterado

- Modelfile `AnonRIF2.modelfile` reestruturado e reduzido de aproximadamente 4.150 linhas para cerca de 123 linhas.
- Modelo `NEXUS-anon:latest` passa a ser descrito exclusivamente como detector local de entidades sensiveis, com saida JSON e offsets exatos.
- Removidas instrucoes conflitantes que orientavam a IA a devolver documento anonimizado ou mencionavam `gemma4:31b`.
- Documentacao do Ollama atualizada para refletir a arquitetura atual: substituicao, validacao, hashes e exportacao sao responsabilidades do backend.
- Rodape institucional revisado com acentuacao correta.

## [1.6.4] - 2026-06-24

### Corrigido

- Exportacao de CSV deixa de falhar quando o DOCX institucional nao possui o estilo interno `Table Grid`.
- Tabela de controle no PDF passa a compactar valores originais muito longos, evitando falhas de layout em CSVs extensos de RIF.
- Erros de comunicacao com o backend passam a exibir mensagem mais clara quando o servico local nao responder.

## [1.6.3] - 2026-06-24

### Corrigido

- Campo de renomeacao do grupo no Historico de anonimizacao ampliado para ocupar melhor a area direita disponivel.
- Janela **Regras institucionais de uso e Avisos** substituida por versao com textos acentuados corretamente.

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
