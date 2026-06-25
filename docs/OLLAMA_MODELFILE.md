# Ollama e modelo local do ANON

## Padrão atual

O ANON usa `qwen3:32b` como modelo local padrão.

```powershell
ollama pull qwen3:32b
```

A especialização institucional não depende mais de um modelo derivado chamado `NEXUS-anon:latest`. As regras especializadas são aplicadas dentro do próprio ANON por:

- prompt obrigatório enviado ao Ollama;
- perfis documentais JSON;
- regras determinísticas por perfil;
- validador de preservação documental;
- corretor de resposta JSON;
- classificador de qualidade;
- resumo seguro e arquivo complementar de avisos.

## Sobre o Modelfile arquivado

O arquivo `backend/resources/ollama/AnonRIF2.modelfile` permanece no repositório como referência técnica do comportamento desejado: pensamento visível desligado, resposta em JSON, offsets exatos e foco exclusivo em entidades sensíveis.

Ele não deve ser usado para recriar `NEXUS-anon:latest` no fluxo padrão. Criar outro modelo derivado aumenta risco de incompatibilidade entre máquinas.

## Comunicação IA e JSON

O ANON avalia cada resposta do modelo local e registra métricas objetivas:

- blocos de texto enviados à IA;
- blocos recusados por JSON não aproveitável;
- tentativas de correção solicitadas ao próprio modelo;
- correções aproveitadas;
- entidades aceitas depois da validação.

Essas métricas são incluídas nos metadados do processamento e no arquivo complementar de avisos, sem expor conteúdo sensível do documento.
