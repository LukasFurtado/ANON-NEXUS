# NCE-ANON: Núcleo de Comportamento Especializado do ANON

## O que é

O NCE-ANON é a camada que transforma o `qwen3:32b` puro em um operador institucional de anonimização documental, sem criar um modelo derivado no Ollama.

Ele não fica dentro do peso do modelo. Ele fica no próprio ANON.

## Onde fica

- `backend/app/services/ollama.py`: prompt base, contrato de resposta e parâmetros determinísticos enviados ao Ollama.
- `backend/resources/knowledge/anon_operational_knowledge.json`: regras gerais de comunicação, contrato JSON, protocolo entre células e conhecimento operacional.
- `backend/resources/profiles/*.json`: perfis documentais estratégicos, como RIF/COAF, extrato bancário e relatório investigativo.
- `backend/app/pipeline/regex_rules.py`: regras determinísticas e reconhecimento estruturado.
- `backend/app/pipeline/validator.py`: bloqueio de falsos positivos e preservação de datas, valores, termos técnicos e estrutura.
- `backend/app/services/ollama.py`: avaliação da resposta JSON, segunda chamada de correção e registro de recusas.
- `backend/app/core/quality_classifier.py`: classificação objetiva do resultado.
- `backend/app/core/safe_summary.py`: resumo seguro sem conteúdo sensível.

## Como ele é alimentado

O ANON monta a comunicação com a IA local em camadas:

1. Prompt base obrigatório.
2. Núcleo NCE-ANON.
3. Contrato JSON.
4. Perfil documental selecionado.
5. Conhecimento operacional do perfil.
6. Texto extraído do documento.

O modelo local recebe apenas a tarefa de identificar entidades sensíveis. O backend faz substituição, validação, auditoria, hashes e exportação.

## Parâmetros atuais enviados ao Ollama

```json
{
  "temperature": 0,
  "top_p": 0.9,
  "repeat_penalty": 1.1
}
```

Também são enviados `think: false`, `/no_think` e `format: json`.

## Como expandir

Para ampliar a capacidade do ANON, o caminho correto é:

- criar ou melhorar perfis em `backend/resources/profiles`;
- adicionar termos protegidos e exemplos em `anon_operational_knowledge.json`;
- reforçar regex e regras estruturadas por perfil;
- melhorar validação e falsos positivos;
- adicionar testes com documentos reais anonimizados;
- medir recusas JSON e ajustar o contrato de resposta.

Não é recomendado criar outro modelo derivado enquanto o objetivo for padronização institucional em `qwen3:32b`.
