# PLAN.md — SyncAssist: secretaria digital Trello ↔ projetos

Data de consolidação: 14/09/2026. Documento de especificação e execução futura.

**Situação atual:** somente o planejamento foi produzido. Nenhum item de implementação abaixo está concluído. O agente implementador deverá marcar uma tarefa apenas depois de executar e validar o comportamento correspondente.

**Instrução ao próximo agente:** implementar este plano em etapas, preservar os arquivos existentes e registrar evidências de validação. Não reinterpretar decisões já acordadas como perguntas pendentes. Não criar commits sem autorização explícita. Este documento não autoriza experimentar alterações em cards de produção durante o desenvolvimento; usar dados simulados e, para validação real, uma lista de teste indicada pelo responsável.

## 1. Resumo executivo

O usuário organiza vários projetos em um único quadro do Trello. Cada lista representa um projeto e cada card representa uma demanda. O SyncAssist será um script Python copiado para a pasta de cada projeto. A execução sincronizará a lista configurada com arquivos Markdown na pasta `PLAN/`, permitindo que humanos e agentes leiam o planejamento, editem os campos permitidos e registrem a conclusão das tarefas.

O produto deverá ser pequeno na distribuição: um `sync.py`, configuração em `.env` e nenhuma dependência externa. A sincronização bidirecional, porém, exige identidade estável, comparação com uma versão-base e tratamento explícito de conflitos e falhas parciais. Essas garantias fazem parte do MVP; não devem ser omitidas para reduzir linhas.

### 1.1. Decisões já acordadas

| Tema | Decisão |
| --- | --- |
| Tecnologia | Python 3, somente biblioteca padrão. |
| Distribuição | Um script portátil por projeto. |
| Correspondência projeto/lista | `TRELLO_LIST_ID` no `.env`; nomes não determinam identidade. |
| Operação | Execução manual, automática e sem perguntas interativas. |
| Volume esperado | Até aproximadamente 200 cards por lista; histórico e anexos podem aumentar a quantidade de dados. |
| Sistemas | Windows, Linux e macOS. |
| Direção | Bidirecional para os campos editáveis acordados. |
| Conteúdo editável | Título, descrição, checklists, associação de labels e status de conclusão. |
| Demais dados | Importar como referência somente leitura, dentro do que a API e as permissões disponibilizarem. |
| Identidade do card | ID completo nos metadados do Markdown. |
| Estado de sincronização | No próprio Markdown; sem banco nem arquivo global de estado. |
| Status | `done-` corresponde à presença da label configurada; `todo-`, à ausência. |
| Movimento de cards | Nunca mover cards para representar conclusão. |
| Nome do arquivo | Título curto e sanitizado, atualizado automaticamente. |
| ID no nome | Somente em colisões ou quando não houver texto útil. |
| Alterações simultâneas | Preservar as versões e solicitar resolução explícita para aquele card. |
| Card apagado ou movido | Retirar seu arquivo do conjunto ativo de `PLAN/`, com as salvaguardas de remoção abaixo. |
| Arquivo apagado localmente | Recriar a partir do Trello; não apagar nem arquivar o card. |
| Falha isolada | Continuar cards independentes, informar falha e retornar código diferente de zero. |
| Segurança | `.env` fora do Git, configuração validada e logs sem credenciais ou corpo dos cards. |

### 1.2. Refinamentos técnicos deste documento

Os itens seguintes fecham lacunas do rascunho anterior e são padrões de implementação, preservando as decisões do usuário:

- Python mínimo: 3.11; não utilizar funcionalidades exclusivas de versões posteriores.
- Metadados em JSON delimitado no início do Markdown, chamado aqui de front matter JSON. Não depender de YAML.
- Uma fonte editável por informação: título e IDs das labels nos metadados, descrição e checklists em regiões delimitadas, status no prefixo.
- Snapshot-base completo da projeção editável, além do hash. Hashes sozinhos não preservam a versão necessária à resolução de conflitos.
- Resolução de conflitos por campo explícito nos metadados, vinculado à versão remota revisada. Apagar o artefato não autoriza sobrescrita.
- Remoções locais recuperáveis em `PLAN/.removed/`; essa pasta não participa da sincronização ativa.
- Arquivar um card não significa concluí-lo nem excluí-lo. Cards arquivados ainda pertencentes à lista continuam representados, com o campo de arquivamento somente leitura.
- Não criar cards a partir de arquivos locais novos sem identidade remota.
- Labels editáveis significam associar/desassociar labels existentes do quadro. Renomear ou criar uma label global do quadro fica fora do MVP.
- Um pequeno registro de operações pendentes no próprio card local protege retomadas depois de falhas durante múltiplas chamadas HTTP.
- O conteúdo importado é dado de planejamento; não é comando a executar nem autorização para um agente alterar o projeto.

## 2. Objetivo, limites e entregáveis

### 2.1. Resultado esperado

- [ ] Permitir copiar o script para um projeto, preencher `.env` e executar `python sync.py`.
- [ ] Criar automaticamente `PLAN/` após validar a configuração e o acesso remoto.
- [ ] Gerar um Markdown por card da lista configurada.
- [ ] Preservar títulos e descrições completos, independentemente do nome curto do arquivo.
- [ ] Permitir que alterações locais autorizadas retornem ao Trello na execução seguinte.
- [ ] Refletir alterações remotas localmente sem perder edições locais concorrentes.
- [ ] Manter uma execução sem mudanças idempotente: nenhuma escrita remota, nenhum arquivo regravado e nenhum timestamp local alterado apenas pela passagem do tempo.
- [ ] Apresentar relatório que um humano ou agente consiga usar para identificar pendências.

### 2.2. O que importar

- [ ] Campos públicos do objeto card retornados pela API: identidade, título, descrição, URLs, posições, datas, conclusão de prazo, arquivamento, capa, badges e demais propriedades disponíveis.
- [ ] Todas as checklists e seus itens, com IDs, nomes, posições, estados e outros campos disponibilizados.
- [ ] Labels associadas e catálogo de labels do quadro para interpretação dos IDs.
- [ ] Comentários e histórico de ações acessíveis pelos endpoints oficiais, percorrendo todas as páginas disponíveis.
- [ ] Membros associados e dados de identificação necessários para exibir os nomes.
- [ ] Anexos, capas e imagens como metadados e links, sem download dos binários.
- [ ] Valores e definições de campos personalizados quando o quadro e o token permitirem.
- [ ] Stickers, votos e dados compartilhados de Power-Ups expostos ao token, como somente leitura.
- [ ] Preservar campos desconhecidos do retorno em um snapshot JSON somente leitura, evitando descartar informações simplesmente por não haver um renderizador específico.
- [ ] Informar recursos não expostos, não suportados ou inacessíveis; não prometer histórico completo de tudo que já aconteceu no Trello.
- [ ] Diferenciar recurso vazio de recurso cuja consulta falhou.

### 2.3. Fora do MVP

- [ ] Não implementar daemon, agendamento, webhooks, interface gráfica, painel web ou API própria.
- [ ] Não adicionar dependências, SDK do Trello, banco de dados ou empacotador de executável.
- [ ] Não criar, mover, apagar ou arquivar cards a partir de comandos locais.
- [ ] Não editar comentários, membros, datas, anexos, capa, votos, campos personalizados ou dados de Power-Ups remotamente.
- [ ] Não usar OCR, baixar imagens ou consultar URLs presentes em títulos e descrições.
- [ ] Não implementar `--dry-run` nem confirmação interativa, conforme a escolha de execução automática.
- [ ] Não implementar mesclagem automática por linha ou por campo entre duas versões editáveis divergentes.
- [ ] Não impor limite artificial de 200 cards: esse número é a escala de referência, não um ponto de truncamento.

### 2.4. Artefatos futuros

```text
raiz-do-projeto/
├── sync.py                  # implementação distribuível
├── .env                     # preenchido localmente; nunca versionar
├── .env.example             # apenas nomes das variáveis e exemplos não sensíveis
├── .gitignore               # regras mescladas às existentes
├── README.md                # instalação, contrato de edição e operação
├── PLAN.md                  # este roteiro de implementação
├── test_sync.py             # testes locais com biblioteca padrão
└── PLAN/                    # gerado na execução do produto
    ├── todo-titulo-curto.md
    ├── done-outro-titulo.md
    ├── .conflicts/          # versões e instruções para revisão
    ├── .removed/            # arquivos retirados do conjunto ativo, recuperáveis
    └── .sync.lock           # somente enquanto uma execução estiver ativa
```

`PLAN.md` é o planejamento do SyncAssist. `PLAN/` é a pasta que o produto gerará para os cards. São objetos distintos. Neste trabalho de documentação, criar somente `PLAN.md`; todos os demais artefatos acima pertencem à implementação futura.

## 3. Riscos e mitigações obrigatórias

| Risco concreto | Comportamento exigido |
| --- | --- |
| Sobrescrever texto editado nos dois lados | Comparação de três versões: base, local e remota; conflito bloqueia apenas o card. |
| Exclusão em massa após falha de listagem | Separar falha de consulta de lista vazia; desabilitar remoções se o inventário não estiver completo. |
| Confundir 404 com exclusão | Não tratar 404 isolado como prova; exigir inventário íntegro e retirar de forma recuperável quando a identidade não estiver mais acessível. |
| Repetir criação de checklist após timeout | Persistir intenção antes da chamada; não repetir POST de resultado incerto automaticamente. |
| Perder IDs de subtarefas | Usar identificadores explícitos para checklists e itens, nunca casar somente por texto. |
| Usar slug como identidade | Localizar pelo ID completo do card no front matter. |
| Colisões e nomes incompatíveis com Windows | Sanitizar, truncar, comparar sem distinção de caixa e acrescentar ID somente quando necessário. |
| Alterar o arquivo enquanto o script trabalha | Revalidar bytes antes da substituição; não sobrescrever edição concorrente. |
| Dois processos na mesma pasta | Lock local exclusivo; segunda execução encerra antes de qualquer mutação. |
| Alteração remota entre leitura e escrita | Releitura imediatamente antes do envio e confirmação depois; documentar que chamadas REST separadas não formam uma transação. |
| Expor segredos em exceções | Autenticação centralizada, mensagens redigidas e sem dump de request/response. |
| Vazamento dos próprios cards pelo Git | Documentar que `PLAN/` contém dados privados; ignorar a pasta por padrão no modelo distribuído. |
| HTML ou instruções maliciosas no card | Armazenar como dados, escapar representações geradas e nunca executar conteúdo. |
| Histórico grande e rate limit | Paginação real, chamadas sequenciais e backoff limitado. |
| Mudança de `.env` apontar para outra lista | Arquivos com binding diferente são preservados e bloqueados, nunca reenviados nem apagados. |

## 4. Implementação em blocos e mini tarefas

### Bloco 0 — Preparar o trabalho e confirmar contratos externos

Arquivos-alvo futuros: `sync.py`, `test_sync.py`, `.env.example`, `.gitignore` e `README.md`.

- [ ] Ler este documento integralmente antes de implementar.
- [ ] Inspecionar instruções locais e arquivos existentes novamente no início da implementação.
- [ ] Considerar o estado observado em 14/09/2026: a pasta continha apenas `ideia.txt` e não era um repositório Git inicializado.
- [ ] Não inicializar Git, instalar pacotes ou criar uma arquitetura de módulos como requisito para começar.
- [ ] Confirmar Python 3.11 ou superior no ambiente usado para testes.
- [ ] Consultar os contratos oficiais dos endpoints abaixo, principalmente campos de checklist, filtros de arquivamento e paginação.
- [ ] Usar os parâmetros documentados de cada endpoint; não aplicar genericamente `page`, `limit` ou `before` onde não forem suportados.
- [ ] Fixar o formato v1 descrito neste plano antes de gerar os primeiros arquivos de card.
- [ ] Implementar funções pequenas dentro do mesmo script, com separação lógica entre HTTP, parsing, normalização, decisão e aplicação.
- [ ] Manter execução dentro de `main()` e proteger a entrada para que importar o módulo em testes não realize rede ou escrita.
- [ ] Evitar interfaces abstratas, factories, registries ou classes que apenas encapsulem uma única função.

**Saída verificável do bloco:** contratos externos consultados e responsabilidades internas claras; ainda não é necessário conectar a uma conta real.

### Bloco 1 — Configuração, raiz e binding do projeto

#### 1.1. Variáveis

```dotenv
TRELLO_API_KEY=
TRELLO_TOKEN=
TRELLO_LIST_ID=
TRELLO_DONE_LABEL_ID=
```

- [ ] Resolver a raiz pela localização real de `sync.py`, usando `Path(__file__).resolve().parent`.
- [ ] Resolver `.env` e `PLAN/` nessa raiz, mesmo quando o script for chamado por caminho absoluto a partir de outra pasta.
- [ ] Ler `.env` em UTF-8, aceitando BOM inicial.
- [ ] Aceitar linhas vazias, comentários de linha inteira e atribuições `CHAVE=valor`.
- [ ] Separar a atribuição somente no primeiro `=`.
- [ ] Remover espaços externos; remover um par correspondente de aspas simples ou duplas.
- [ ] Não executar shell, expandir variáveis, interpretar escapes ou cortar `#` dentro de um valor.
- [ ] Rejeitar aspas sem fechamento e duplicidade de uma das quatro chaves do SyncAssist.
- [ ] Ignorar entradas de outros aplicativos em um `.env` compartilhado; não alterá-las.
- [ ] Usar somente os quatro valores do `.env` para esta ferramenta; não aplicar fallback silencioso a variáveis de ambiente de outro projeto.
- [ ] Validar campos obrigatórios não vazios e IDs no formato completo aceito pela API; rejeitar controles e quebras de linha nas credenciais.
- [ ] Não impor um tamanho inventado para token; validar seu acesso com a API.
- [ ] Mostrar apenas o nome da variável inválida, nunca seu conteúdo.

#### 1.2. Validação remota e vínculo local

- [ ] Consultar a lista configurada para obter nome, `idBoard` e situação de arquivamento.
- [ ] Consultar o catálogo de labels do quadro e verificar se `TRELLO_DONE_LABEL_ID` pertence a ele.
- [ ] Não criar automaticamente uma label ausente, nem escolher uma pelo nome quando o ID falhar.
- [ ] Encerrar com erro de configuração se o binding não puder ser validado.
- [ ] Gravar no metadado de cada card o ID do quadro, o ID da lista e o ID da label usada para conclusão.
- [ ] Comparar esses três IDs com a configuração em toda execução.
- [ ] Se houver arquivos ativos com binding diferente, encerrar antes de mutações e explicar quais arquivos precisam de migração manual.
- [ ] Atualizar somente o nome informativo da lista quando ela for renomeada, preservando o ID.
- [ ] Se o quadro ou a lista inteira estiver arquivado, encerrar com diagnóstico e sem remover a coleção local; reabrir o escopo é decisão do responsável.

**Saída verificável do bloco:** executar de outra pasta encontra o mesmo `.env`; configuração inválida não altera arquivos nem cards.

### Bloco 2 — Cliente HTTP e inventário remoto

#### 2.1. Transporte

- [ ] Usar `urllib.request`, `urllib.error`, `urllib.parse`, `json`, `time` e demais módulos padrão necessários.
- [ ] Fixar origem HTTPS `https://api.trello.com/1`; nunca usar o campo URL de um card como destino de uma chamada autenticada.
- [ ] Usar o cabeçalho de autorização com key/token no formato aceito pelo Trello, centralizado em uma função; validar caracteres antes de interpolar.
- [ ] Manter validação TLS padrão habilitada e impedir redirecionamento autenticado para outra origem.
- [ ] Definir timeout de 30 segundos por tentativa.
- [ ] Definir no máximo três tentativas totais para GET e operações comprovadamente repetíveis.
- [ ] Usar esperas de 1 e 2 segundos para falhas transitórias; em 429, respeitar `Retry-After` quando válido ou esperar 10 segundos, sem loop infinito.
- [ ] Espaçar o início das requisições em pelo menos 0,2 segundo na instância local e tratar 429 mesmo assim, pois o token pode ser compartilhado com outros projetos.
- [ ] Tratar HTTP 400 como erro da operação, sem repetir a mesma entrada inválida.
- [ ] Tratar 401 como falha global de autenticação; encerrar as próximas mutações.
- [ ] Tratar 403 global na validação do escopo como fatal; 403 de recurso específico deve preservar o card e permitir processar os outros.
- [ ] Não classificar erro HTTP, timeout, JSON inválido ou formato inesperado como coleção vazia.
- [ ] Não repetir uma criação POST quando for incerto se o servidor a aplicou.
- [ ] Confirmar estado por GET antes de repetir atualização, associação de label ou exclusão de subitem que tenha resultado incerto.
- [ ] Redigir mensagens HTTP antes de registrar; não imprimir URL autenticada, corpo remoto ou traceback contendo credenciais.

A API aceita autenticação por key/token; o formato de cabeçalho e o escopo de autorização devem seguir a [documentação oficial de autorização](https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/). A política local de tentativas e espaçamento acima é uma decisão deste projeto, considerando os [limites oficiais de requisição](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/).

#### 2.2. Endpoints de referência

Os caminhos abaixo são relativos à origem fixa. Validar parâmetros e respostas na implementação; a tabela não autoriza enviar campos arbitrários do snapshot.

| Finalidade | Método e recurso |
| --- | --- |
| Ler configuração da lista | `GET /lists/{id}` |
| Listar cards da lista | `GET /lists/{id}/cards` |
| Inventariar arquivados quando necessário | `GET /boards/{id}/cards` com filtro documentado que inclua todos, restringindo por `idList` localmente |
| Ler card | `GET /cards/{id}` |
| Ler checklists | `GET /cards/{id}/checklists` |
| Ler histórico | `GET /cards/{id}/actions` |
| Ler anexos e membros | `GET /cards/{id}/attachments` e `GET /cards/{id}/members` |
| Ler labels disponíveis | `GET /boards/{id}/labels` |
| Alterar título/descrição | `PUT /cards/{id}` com campos explicitamente permitidos |
| Associar/desassociar label | `POST /cards/{id}/idLabels` e `DELETE /cards/{id}/idLabels/{idLabel}` |
| Criar/alterar/excluir checklist | `POST /checklists`, `PUT /checklists/{id}`, `DELETE /checklists/{id}` |
| Criar item | `POST /checklists/{id}/checkItems` |
| Alterar item | `PUT /cards/{id}/checkItem/{idCheckItem}` |
| Excluir item | `DELETE /checklists/{id}/checkItems/{idCheckItem}` |

Referências dos contratos: [listas](https://developer.atlassian.com/cloud/trello/rest/api-group-lists/), [quadros](https://developer.atlassian.com/cloud/trello/rest/api-group-boards/), [cards](https://developer.atlassian.com/cloud/trello/rest/api-group-cards/) e [checklists](https://developer.atlassian.com/cloud/trello/rest/api-group-checklists/).

#### 2.3. Inventário completo e enriquecimento

- [ ] Obter a relação completa de IDs do escopo antes de decidir remoções locais.
- [ ] Incluir cards arquivados ainda vinculados à lista; validar essa cobertura em teste de integração, sem presumir que a consulta padrão da lista os inclui.
- [ ] Se necessário, consultar cards do quadro com o filtro suportado para todos e reter apenas os cujo `idList` coincide com a configuração.
- [ ] Não armazenar nem renderizar conteúdo de cards de outras listas ao usar o inventário do quadro.
- [ ] Deduplicar resultados por ID; tratar IDs repetidos com dados incompatíveis como erro de inventário.
- [ ] Consultar recursos de cada card e manter em memória o snapshot remoto completo daquela execução.
- [ ] Paginar ações com o cursor oficial, avançando pelo ID da última ação; detectar cursor repetido e terminar somente quando a fonte estiver esgotada.
- [ ] Buscar todas as páginas de labels e outros recursos que exponham paginação.
- [ ] Ordenar ações de forma estável por data e ID; não depender da ordem de chegada de requisições.
- [ ] Não reconstruir o estado atual de checklists a partir do histórico; ler seus objetos atuais.
- [ ] Preservar dados de uma seção anterior quando um recurso complementar falhar; registrar a falha e não chamar essa coleta de completa.
- [ ] Bloquear a escrita daquele card no ciclo quando um recurso necessário ao contrato estiver incompleto.
- [ ] Distinguir recurso explicitamente não suportado de falha transitória: registrar indisponibilidade conhecida no snapshot; não fabricar uma coleção vazia.
- [ ] Não truncar silenciosamente comentários, descrições, títulos ou histórico para cumprir metas de desempenho.

O cursor de ações deve seguir o mecanismo descrito na [introdução oficial da API](https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/). “Todos os dados” neste produto significa os dados de card e recursos associados expostos ao token, e não acesso a histórico privado ou conteúdo binário indisponível.

**Saída verificável do bloco:** uma resposta incompleta jamais habilita limpeza local; cards arquivados e históricos paginados são cobertos.

### Bloco 3 — Contrato dos arquivos Markdown

#### 3.1. Identidade e regiões

- [ ] Usar UTF-8 e gerar quebras de linha LF; aceitar CRLF ao ler.
- [ ] Reconhecer arquivo gerenciado somente quando houver marcador inicial, JSON válido, `managed_by: "syncassist"`, `role: "card"`, versão suportada e identidade válida.
- [ ] Tratar arquivo com marcador do SyncAssist e JSON inválido como arquivo gerenciado corrompido; não ignorá-lo e depois sobrescrevê-lo com uma importação nova.
- [ ] Manter o front matter no início do arquivo, delimitado por `<!-- syncassist:metadata` e `syncassist:end -->`, em linhas próprias.
- [ ] Decodificar o objeto JSON por estrutura, sem `eval` e sem executar instruções do documento.
- [ ] Escapar `<`, `>` e `&` na serialização de JSON embutido em comentário HTML, preservando os valores após decodificação.
- [ ] Gerar um `section_token` aleatório em hexadecimal, fixo por arquivo, para identificar as regiões de descrição, checklists e referência.
- [ ] Utilizar marcadores em linhas próprias no formato `<!-- syncassist:<token>:description:begin -->` e `<!-- syncassist:<token>:description:end -->`; aplicar a mesma convenção a `checklists` e `reference`.
- [ ] Garantir na geração que os delimitadores escolhidos não ocorram literalmente no conteúdo remoto. Em colisão, escolher outro token e atualizar todos os marcadores numa única gravação.
- [ ] Na leitura, exigir cada região exatamente uma vez, na ordem definida. Marcadores ausentes, repetidos ou truncados bloqueiam o card.
- [ ] Não localizar regiões apenas por títulos como `## Descrição`, porque o usuário pode ter esses mesmos títulos dentro da descrição.
- [ ] Rejeitar alterações não suportadas na estrutura do documento com mensagem objetiva; não descartá-las silenciosamente.

#### 3.2. Campos obrigatórios do front matter v1

| Campo | Tipo / responsabilidade |
| --- | --- |
| `managed_by` | String fixa `syncassist`, gerada pela ferramenta. |
| `schema_version` | Inteiro `1`; versões desconhecidas bloqueiam o arquivo. |
| `role` | String `card`; conflitos usam papel próprio. Backups preservam os bytes originais e são ignorados pela localização em subpasta. |
| `trello_card_id` | ID completo e imutável do card. |
| `trello_board_id` | ID do quadro validado na origem. |
| `trello_list_id` | ID da lista configurada; não editável como comando de movimento. |
| `trello_list_name` | Nome informativo atual da lista. |
| `trello_done_label_id` | Label que define a semântica de conclusão deste arquivo. |
| `trello_url` | Link informativo para abrir o card; não é destino autenticado. |
| `section_token` | Token dos delimitadores internos. |
| `status` | Espelho informativo do último status sincronizado; não é a entrada editável de conclusão. |
| `filename` | Objeto gerado com `slug` e `suffix`, para manter nomes estáveis após desambiguação. |
| `content.title` | Título completo, string editável e única fonte local do título. |
| `content.label_ids` | Array editável de IDs das labels comuns; exclui a label de conclusão. |
| `sync.last_synced_at` | Data UTC em ISO 8601 da última sincronização confirmada daquele conteúdo. |
| `sync.base` | Snapshot da projeção editável comum à última sincronização bem-sucedida. |
| `sync.base_hash` | SHA-256 da serialização canônica de `sync.base`. |
| `sync.reference_hash` | Hash da região somente leitura gerada na última versão, para detectar edição local indevida. |
| `sync.pending` | `null` normalmente; objeto de retomada quando houver lote remoto em andamento. |
| `sync.conflict` | `null` normalmente; identidade e fingerprint do conflito em aberto. |
| `sync.resolution` | `null` normalmente; decisão explícita descrita no Bloco 8. |

- [ ] Validar tipos, valores obrigatórios, unicidade de IDs e integridade de `base_hash` antes de comparar versões.
- [ ] Preservar campos remotos desconhecidos no snapshot de referência, mas rejeitar versão de schema local desconhecida.
- [ ] Não apresentar o hash como assinatura de segurança: ele detecta inconsistência e mudança, não prova autenticidade contra adulteração deliberada.
- [ ] Não confiar em IDs editados manualmente como autorização para acessar outro card: validar binding remoto e pertencimento antes de qualquer escrita.
- [ ] Não manter cópias editáveis concorrentes da descrição ou do título em dois locais do documento.

#### 3.3. Layout e responsabilidade de edição

O documento seguirá esta ordem: front matter JSON; título visual gerado; região de descrição; região de checklists; região somente leitura com labels legíveis, comentários, anexos, membros, datas, histórico e snapshot JSON completo dos recursos importados.

- [ ] Gerar o título visual a partir de `content.title`, escapando Markdown/HTML para representação segura.
- [ ] Explicar junto do título que a alteração do título se faz em `content.title`; editar apenas o cabeçalho visual é alteração não suportada.
- [ ] Preservar a descrição como Markdown bruto entre seus delimitadores, incluindo imagens, listas, tabelas, blocos de código, espaços finais e linhas vazias.
- [ ] Definir uma quebra estrutural depois do marcador inicial e antes do final; remover somente essas quebras estruturais ao extrair a descrição, nunca aplicar `strip()` ao conteúdo.
- [ ] Normalizar apenas CRLF/CR para LF na comparação do conteúdo textual.
- [ ] Gerar seção de referência claramente rotulada como somente leitura.
- [ ] Exibir labels por nome/cor/ID e informar que associação é editada em `content.label_ids`.
- [ ] Preservar JSON completo dos recursos importados na referência, além das visualizações legíveis; não transformar o JSON inteiro em payload de atualização.
- [ ] Não alterar descrição legítima por conter palavras como `todo`, `done`, instruções para agentes ou delimitadores de Markdown.
- [ ] Detectar edição na região somente leitura pelo hash e preservar o documento inteiro em conflito de formato; não enviar essa edição ao Trello nem apagá-la durante refresh.
- [ ] Ignorar alterações de formatação do próprio JSON que não alterem os valores; não usar o hash dos bytes do arquivo como hash semântico de sincronização.
- [ ] Regravar metadados técnicos somente por necessidade real: conteúdo mudou, operação ficou pendente ou conflito foi registrado.

#### 3.4. Checklists editáveis com identidade estável

Formato v1 dentro da região de checklists:

```markdown
### "Entrega inicial" <!-- syncassist:checklist=000000000000000000000010 -->
- [ ] "Implementar validação" <!-- syncassist:item=000000000000000000000011 -->
- [x] "Revisar autenticação" <!-- syncassist:item=000000000000000000000012 -->

### "Testes adicionais" <!-- syncassist:checklist=new:testes -->
- [ ] "Cobrir timeout" <!-- syncassist:item=new:timeout -->
```

Os IDs acima são fictícios. O texto entre aspas é uma string JSON em uma linha: isso permite representar aspas, quebras de linha e caracteres especiais sem inferir onde um nome termina. Os nomes continuam completos; somente a representação usa escapes quando necessário.

- [ ] Representar cada checklist por cabeçalho com nome em string JSON e marcador de ID.
- [ ] Representar cada item por checkbox, nome em string JSON e marcador de ID.
- [ ] Interpretar `[ ]` como `incomplete`; `[x]` e `[X]` como `complete`.
- [ ] Aceitar múltiplas checklists e itens com textos iguais quando seus IDs forem distintos.
- [ ] Manter IDs existentes quando o nome mudar; nunca excluir e recriar um objeto apenas para renomeá-lo.
- [ ] Validar que cada checklist existente pertence ao card e cada item existe no conjunto de checklists desse card.
- [ ] Usar a ordem do documento como ordem pretendida das checklists e itens, ignorando os números absolutos de posição na comparação semântica.
- [ ] Permitir mover um item existente entre checklists do mesmo card, preservando seu ID e usando os campos permitidos pela API.
- [ ] Para objetos novos, exigir ID temporário explícito `new:<chave>`, com chave de 1 a 64 caracteres entre letras ASCII minúsculas, números e hífen.
- [ ] Exigir unicidade das chaves temporárias dentro do documento.
- [ ] Criar objetos remotos e substituir IDs temporários pelos IDs retornados somente com confirmação registrada.
- [ ] Rejeitar novos itens sem marcador; não tentar identificá-los por correspondência aproximada de título.
- [ ] Excluir objeto existente somente com marcador explícito `delete` dentro do comentário, por exemplo `<!-- syncassist:item=<id> delete -->`.
- [ ] Exigir marcador `delete` no cabeçalho para remover uma checklist inteira; essa operação remove seus itens e deve constar do relatório.
- [ ] Tratar ausência inexplicada de ID que existia na base como erro de edição, não como autorização implícita de exclusão.
- [ ] Aceitar ausência local de objeto que também foi removido remotamente e que não tenha outras alterações locais; isso permite convergência legítima.
- [ ] Rejeitar `delete` em objeto novo e duplicidade de IDs existentes.
- [ ] Comparar a intenção de exclusão com a base e com o remoto antes de executá-la; remoção versus edição concorrente é conflito.
- [ ] Preservar atributos somente leitura de itens, como responsável e prazo, ao alterar nome, estado, checklist ou posição.

**Saída verificável do bloco:** round-trip de arquivo preserva texto; duas subtarefas homônimas continuam distinguíveis; remover um marcador não apaga dados remotos.

### Bloco 4 — Títulos, slugs e nomes portáteis

#### 4.1. Regra básica

```text
todo-titulo-curto.md
done-titulo-curto.md
todo-titulo-curto--a1b2c3.md   # somente quando há colisão
todo-card--a1b2c3.md           # quando não há texto útil
```

- [ ] Preservar integralmente o título original em `content.title`; nunca truncar o título enviado ao Trello por causa do limite do nome do arquivo.
- [ ] Usar o nome do arquivo somente como apresentação e entrada de status.
- [ ] Usar normalização Unicode NFKC e minúsculas consistentes para o slug.
- [ ] Remover caracteres de controle, separadores de caminho e caracteres proibidos: `< > : " / \\ | ? *`.
- [ ] Manter letras e números Unicode; converter espaços, pontuação e separadores em hífen; colapsar hífens repetidos.
- [ ] Remover pontos, espaços e hífens das extremidades.
- [ ] Limitar o slug a 60 caracteres e, adicionalmente, a 180 bytes UTF-8, cortando apenas em fronteira de caractere.
- [ ] Aplicar o limite antes do prefixo, sufixo de colisão e extensão.
- [ ] Evitar nomes reservados do Windows, inclusive variantes com extensão e famílias `COM1`–`COM9` e `LPT1`–`LPT9`; usar `card-<slug>` quando houver texto aproveitável.
- [ ] Validar o caminho final no sistema de destino; erro de tamanho total deve preservar os arquivos e informar a necessidade de encurtar a raiz.

#### 4.2. Imagens, URLs e títulos sem texto

- [ ] Para imagem Markdown simples `![texto alternativo](url)`, aproveitar o texto alternativo quando existir.
- [ ] Para link Markdown simples `[texto](url)`, aproveitar seu texto, sem consultar a URL.
- [ ] Remover URLs isoladas, data URIs e tags HTML do texto usado para o slug.
- [ ] Em títulos mistos, aproveitar o texto restante após retirar as referências de mídia.
- [ ] Se restarem apenas emojis, símbolos ou espaço, usar `card` mais sufixo do ID.
- [ ] Não depender de parser Markdown completo; documentar a heurística limitada para sintaxe simples e assegurar fallback seguro para sintaxe não reconhecida.
- [ ] Marcar essa simplificação no código com comentário `ponytail:` informando que interpretar Markdown aninhado exigirá parser específico se houver necessidade real.
- [ ] Nunca inferir conclusão pelo texto do título ou pelo tipo da capa.

#### 4.3. Colisões e estabilidade

- [ ] Calcular colisões sobre slugs normalizados e truncados, comparando também com `casefold()` para compatibilidade entre sistemas.
- [ ] Considerar a colisão independentemente do prefixo `todo-`/`done-`, para não surgir conflito ao concluir um dos cards.
- [ ] Em grupo de cards com o mesmo slug, acrescentar sufixo a todos os integrantes do grupo; ordenar pelo ID completo para resultado determinístico.
- [ ] Usar inicialmente os últimos seis caracteres do ID completo como sufixo.
- [ ] Se o sufixo ainda colidir, ampliar para 8, 12 e, por último, 24 caracteres até distinguir os IDs.
- [ ] Considerar todos os arquivos já existentes como nomes ocupados, inclusive arquivos não gerenciados.
- [ ] Se um nome ocupado não puder ser desambiguado com segurança, bloquear o card e não sobrescrever o arquivo.
- [ ] Guardar o sufixo escolhido em `filename.suffix` e preservá-lo se um card homônimo desaparecer; não causar renomeações apenas para encurtar um nome já estável.
- [ ] Recalcular o slug quando o título mudar e resolver novamente as colisões.
- [ ] Uma renomeação manual que altere somente o slug não altera o título remoto; o próximo sync restaura o nome derivado de `content.title`.
- [ ] Reconhecer somente os prefixos exatos `todo-` e `done-`; prefixo inválido em arquivo gerenciado gera erro, nunca exclusão ou adivinhação.
- [ ] Planejar as renomeações de todos os cards antes de aplicá-las para tratar trocas de títulos e colisões cruzadas.
- [ ] Usar nomes temporários únicos para trocas e mudanças apenas de caixa, mantendo identidade e conteúdo recuperáveis se houver interrupção.
- [ ] Se dois arquivos ativos tiverem o mesmo `trello_card_id`, bloquear ambos; não escolher pelo mais recente nem apagar um deles.

**Saída verificável do bloco:** títulos enormes, imagens, emojis, caracteres proibidos e duplicatas resultam em nomes válidos, sem perda do título original nem sobrescrita.

### Bloco 5 — Projeção canônica, hashes e decisão de sincronização

#### 5.1. Modelo comparável

A projeção editável usada em `sync.base`, na leitura local e na leitura remota tem os mesmos campos:

```text
title: string completa
description: string Markdown completa, com quebras normalizadas para LF
status: "todo" | "done"
label_ids: array ordenado de IDs únicos, excluindo a label de conclusão
checklists: array em ordem visual
  id: ID estável ou ID temporário de objeto novo local
  name: nome completo
  items: array em ordem visual
    id: ID estável ou ID temporário de objeto novo local
    name: nome completo
    state: "incomplete" | "complete"
```

- [ ] Canonicalizar o JSON com chaves ordenadas, separadores fixos e UTF-8; calcular SHA-256 do resultado.
- [ ] Normalizar labels como conjunto de IDs e ordenar apenas esse conjunto.
- [ ] Preservar ordem de checklists e itens, usando posição remota e ID como desempate de leitura.
- [ ] Excluir `last_synced_at`, datas de consulta, nomes de arquivo, posição numérica absoluta, nome da lista e metadados somente leitura do hash editável.
- [ ] Não usar `dateLastActivity` como substituto de comparação de conteúdo.
- [ ] Materializar marcadores de exclusão como intenção separada validada; a projeção desejada omite o objeto após validar a autorização de remoção.
- [ ] Reconhecer que IDs temporários mudam após criação; atualizar a projeção desejada com os IDs confirmados antes da comparação final.
- [ ] Gerar `sync.base` exclusivamente de um estado remoto confirmado compatível com o resultado local.

#### 5.2. Tabela de decisão

Definições: `B` é a base confirmada; `L`, a projeção local; `R`, a projeção remota atual. Comparações abaixo são semânticas, não por mtime.

| Condição | Ação |
| --- | --- |
| Card remoto sem arquivo local | Importar; não criar card remoto. |
| `L = B` e `R = B` | Nenhuma mutação editável; atualizar referência apenas se ela realmente mudou. |
| `L = B` e `R ≠ B` | Aplicar versão remota no arquivo. |
| `L ≠ B` e `R = B` | Validar e enviar somente as alterações locais permitidas. |
| `L = R`, mesmo que ambos difiram de `B` | Reconhecer convergência; atualizar base sem POST/PUT desnecessário. |
| `L ≠ B`, `R ≠ B` e `L ≠ R` | Conflito; preservar ambas as versões e bloquear envio daquele card. |
| Base ausente/corrompida em arquivo gerenciado | Erro de integridade; não assumir que local ou remoto vence. |
| Referência remota mudou, projeção editável não | Atualizar somente leitura sem conflito editável. |
| Referência local foi editada | Conflito de formato/somente leitura; preservar bytes e solicitar correção. |

- [ ] Implementar a tabela em função pura testável, sem HTTP nem escrita.
- [ ] Manter conflito no nível do card: alterações diferentes em campos distintos ainda exigem revisão quando ambos os lados divergem.
- [ ] Não criar conflitos apenas porque chegou comentário, mudou nome de membro ou houve reordenação de uma resposta equivalente da API.
- [ ] Não considerar mudanças de formatação do JSON uma edição semântica.
- [ ] Atualizar `last_synced_at` somente quando uma nova base ou referência for efetivamente persistida com sucesso.
- [ ] Revalidar `R` imediatamente antes de começar mutações remotas. Se mudou desde a decisão, recalcular a classificação.

**Saída verificável do bloco:** todos os ramos da tabela são reproduzíveis sem rede e convergência não gera conflito desnecessário.

### Bloco 6 — Escrita remota, labels e conclusão

#### 6.1. Status

- [ ] Derivar status remoto exclusivamente da associação de `TRELLO_DONE_LABEL_ID`.
- [ ] Derivar status local exclusivamente do prefixo do arquivo principal.
- [ ] Para transição local a `done-`, associar a label de conclusão se ainda não estiver presente.
- [ ] Para transição local a `todo-`, remover somente essa associação se estiver presente.
- [ ] Refletir mudança remota da label renomeando o prefixo quando não houver conflito.
- [ ] Nunca alterar `idList`, `closed`, `due`, `dueComplete` ou estado de checklist para representar a conclusão do card.
- [ ] Explicar no README que o status deste produto usa uma label, não o checkbox nativo de prazo do Trello.
- [ ] Não inferir conclusão do card a partir de todos os itens de checklist marcados.
- [ ] Rejeitar inclusão manual da label de conclusão em `content.label_ids`, indicando o uso do prefixo; não manter duas fontes concorrentes de status.

#### 6.2. Campos e operações permitidas

- [ ] Validar título como string não vazia segundo os limites atuais da API; não truncar para fazê-lo caber.
- [ ] Aceitar descrição vazia como remoção intencional da descrição, desde que a região esteja estruturalmente íntegra.
- [ ] Usar uma lista explícita de campos permitidos ao construir cada payload.
- [ ] Calcular deltas de título/descrição em vez de reenviar o snapshot inteiro.
- [ ] Validar cada label comum contra o catálogo do quadro; preservar cor e nome globais.
- [ ] Adicionar/remover somente as associações de labels necessárias ao resultado desejado.
- [ ] Preservar objetos e IDs de checklist ao editar nomes, estados e ordem.
- [ ] Aplicar criação de checklist antes de seus itens; resolver IDs temporários pelos retornos confirmados.
- [ ] Aplicar alterações e movimentos de itens antes de exclusões de checklists que poderiam contê-los.
- [ ] Executar exclusões explicitamente marcadas por último e registrar contagem separada no relatório.
- [ ] Não excluir subobjetos por erro de parsing, listagem incompleta ou falha na leitura da base.
- [ ] Buscar o estado remoto novamente após o lote; só concluir a sincronização quando corresponder à intenção validada, incluindo IDs atribuídos e preservação de campos não editáveis.

**Saída verificável do bloco:** mudar `todo-` para `done-` altera somente a label definida; edição de checklist não recria IDs existentes nem modifica prazos e membros.

### Bloco 7 — Falhas parciais, retomada e integridade local

#### 7.1. Registro de operações no próprio arquivo

Uma sincronização de card pode exigir diversas chamadas HTTP. Não existe commit único que una Trello e disco. O campo `sync.pending` registra a intenção e o progresso sem criar banco ou arquivo global de estado.

- [ ] Antes da primeira mutação remota, gravar atomicamente `sync.pending` com ID da execução, base original, fingerprint remoto observado, projeção desejada e operações ordenadas.
- [ ] Cada operação deverá conter tipo permitido, IDs-alvo, ID temporário quando aplicável, payload mínimo, estado e ID remoto confirmado quando houver criação.
- [ ] Usar estados `not_sent`, `sent_unconfirmed` e `confirmed`.
- [ ] Persistir `sent_unconfirmed` antes de enviar a operação; persistir `confirmed` e o retorno relevante depois da resposta validada.
- [ ] Não avançar `sync.base`, `base_hash` ou `last_synced_at` enquanto o lote inteiro não for confirmado.
- [ ] Se falhar uma operação, preservar as edições locais, a base anterior e o registro do que já foi confirmado.
- [ ] Continuar o processamento dos demais cards se a falha não for global.
- [ ] Na execução seguinte, resolver `pending` antes da tabela normal de sincronização, pois alterações causadas pela própria execução não são novas alterações externas.
- [ ] Reconstruir o estado remoto esperado a partir da base e das operações confirmadas; continuar apenas se o remoto ainda for compatível com esse progresso.
- [ ] Confirmar pelo estado remoto operações repetíveis cujo resultado ficou incerto, sem reenviar automaticamente por hábito.
- [ ] Não repetir POST de criação de checklist ou item em estado `sent_unconfirmed` quando o ID não foi recuperado.
- [ ] Não tentar descobrir um objeto criado só pelo nome: nomes repetidos são válidos.
- [ ] Para criação de resultado desconhecido, abrir conflito de operação ambígua e bloquear novas escritas daquele card.
- [ ] Resolver operação ambígua aceitando explicitamente a versão remota, preservando o documento local como backup; em seguida, o usuário poderá reaplicar somente as intenções ainda ausentes num novo ciclo.
- [ ] Não permitir que uma decisão genérica `local` repita criações ambíguas; informar esse impedimento no artefato.
- [ ] Não executar operações arbitrárias lidas do JSON pendente: validar novamente allowlist, escopo, IDs e coerência com as projeções base/desejada.
- [ ] Se a intenção local mudar enquanto houver operação pendente, preservar ambos os estados e exigir revisão, sem misturar lotes silenciosamente.
- [ ] Limpar `pending` somente após releitura remota final e persistência local bem-sucedidas.

#### 7.2. Escrita atômica e concorrência

- [ ] Criar lock exclusivo em `PLAN/.sync.lock` com a operação nativa de criação exclusiva do arquivo.
- [ ] Gravar PID, identificação da máquina e timestamp no lock para diagnóstico.
- [ ] Segunda execução deve encerrar com falha operacional antes de modificar cards ou arquivos.
- [ ] Remover somente o lock criado pela própria execução, em bloco de finalização.
- [ ] Não apagar lock antigo automaticamente com base apenas em idade/PID; após encerramento anormal, orientar remoção manual depois de verificar que o processo terminou.
- [ ] Capturar os bytes lidos do arquivo principal e verificar novamente antes de substituí-lo.
- [ ] Se o conteúdo mudou durante a operação, guardar o resultado/recibo em conflito e preservar a edição externa, mesmo se o Trello já tiver sido atualizado.
- [ ] Gravar temporário único no mesmo diretório do destino, fazer flush, fechar o arquivo e substituir com `os.replace` apenas quando o destino for o arquivo gerenciado esperado.
- [ ] Em arquivo novo, garantir que o destino continua livre; não sobrescrever arquivo que surgiu entre planejamento e aplicação.
- [ ] Reconhecer que lock próprio não impede um editor externo de gravar no último instante; revalidar o mais perto possível da troca e manter recuperação de resultados já enviados.
- [ ] Na renomeação, preservar um caminho recuperável com o documento completo até que o novo nome esteja confirmado.
- [ ] Se uma interrupção deixar dois arquivos com o mesmo ID, bloquear ambos para revisão na próxima execução, em vez de escolher por mtime.
- [ ] Capturar falha por disco cheio, arquivo aberto no Windows, permissão e caminho inválido; preservar o original e não considerar o card sincronizado.
- [ ] Nunca aplicar limpeza recursiva da pasta como mecanismo de reparo.

**Saída verificável do bloco:** interrupção após criar uma checklist não duplica o objeto na retomada; falha de escrita local não faz o script esquecer uma operação remota enviada.

### Bloco 8 — Conflitos e resolução explícita

#### 8.1. Detecção e armazenamento

- [ ] Manter o arquivo principal com a edição local, inclusive prefixo e título locais.
- [ ] Não modificar os campos remotos enquanto o card tiver conflito não resolvido.
- [ ] Criar `PLAN/.conflicts/<card-id>-<conflict-id>.md` com identidade estável da revisão do conflito.
- [ ] Incluir `role: "conflict"`, tipo de conflito, IDs, data, fingerprint remoto e link do card.
- [ ] Incluir a base anterior, a projeção local capturada, a remota capturada e lista dos grupos de campos divergentes.
- [ ] Preservar cópia integral do documento local no artefato para conflitos de parsing/somente leitura e em falhas de persistência após escrita remota.
- [ ] Escapar corretamente o conteúdo ao embuti-lo no artefato para não confundir seus delimitadores.
- [ ] Registrar `sync.conflict` no arquivo principal sem alterar sua versão-base.
- [ ] Reutilizar o conflito existente quando local/remoto não trouxerem uma nova situação; não produzir cópias idênticas a cada execução.
- [ ] Se o remoto mudar novamente, criar nova revisão do conflito, conservar a anterior e invalidar resolução preparada para o fingerprint antigo.
- [ ] Se o artefato for apagado e o conflito persistir, recriá-lo; apagar arquivo de conflito nunca equivale a escolher uma versão.
- [ ] Ignorar `.conflicts/` na descoberta de cards e na regra de remoção por ausência remota.

#### 8.2. Interface de resolução

A decisão fica em `sync.resolution` do arquivo principal, normalmente `null`. Sua estrutura será:

```json
{
  "conflict_id": "identificador-exato-do-conflito-revisado",
  "choice": "local",
  "expected_remote_hash": "fingerprint-remoto-exato-do-artefato"
}
```

As strings descritivas acima são exemplos documentais; a ferramenta deverá produzir os valores reais no artefato para cópia. `choice` aceita somente `local`, `remote` ou `merged`.

- [ ] Para `local`, usar os campos editáveis atuais do arquivo principal e seu prefixo como resultado desejado.
- [ ] Para `remote`, usar a versão remota revisada; fazer backup do documento local antes de substituí-lo.
- [ ] Para `merged`, o responsável edita título, descrição, labels, checklists e prefixo no arquivo principal; o script usa esse resultado como uma versão local explicitamente revisada.
- [ ] Não permitir resolução editando diretamente `sync.base` ou seus hashes.
- [ ] Reconsultar o remoto antes de aplicar a decisão e comparar seu hash com `expected_remote_hash`.
- [ ] Recusar `conflict_id` desconhecido, decisão com hash obsoleto ou card cujo binding tenha mudado.
- [ ] Gerar revisão nova se houve mudança remota; não interpretar uma decisão antiga como autorização permanente.
- [ ] Para conflito de seção somente leitura, aceitar `remote` com backup ou exigir restaurar a estrutura/seção indevidamente editada; `local` não autoriza enviar campos fora do escopo.
- [ ] Para criação remota ambígua do Bloco 7, permitir somente aceitação explícita do remoto e revisão posterior da intenção restante.
- [ ] Depois de aplicar e confirmar o resultado, atualizar base/hashes, limpar `pending`, `conflict` e `resolution` e gerar arquivo canônico.
- [ ] Manter o artefato resolvido como registro inativo, indicando a decisão e data; não apagá-lo automaticamente.
- [ ] Se houver conflito em um card, sincronizar os demais e encerrar com código `1`.

**Saída verificável do bloco:** excluir o artefato ou repetir uma decisão obsoleta não sobrescreve o Trello; base, local e remoto ficam disponíveis para revisão.

### Bloco 9 — Remoção remota, movimentação e recuperação

#### 9.1. Regra de escopo

- [ ] Considerar ativo para o projeto todo card cujo `idList` ainda corresponda à configuração, incluindo cards arquivados.
- [ ] Não usar presença em resposta filtrada de cards abertos como critério de existência.
- [ ] Para arquivo gerenciado cujo ID não apareceu no inventário completo, consultar individualmente o card antes de retirá-lo.
- [ ] Se a consulta confirmar outra lista, classificá-lo como movido e não enviar alterações locais a partir do projeto original.
- [ ] Se a consulta confirmar a mesma lista, preservar o arquivo e tratar a divergência de inventário como erro, nunca como exclusão.
- [ ] Se retornar 404, registrar ausência/inacessibilidade, não afirmar que houve exclusão definitiva.
- [ ] Antes de qualquer retirada por 404, confirmar novamente acesso à lista/quadro e obter um segundo inventário completo no mesmo ciclo.
- [ ] Se o card continuar ausente nesses inventários íntegros, retirar o principal de forma recuperável, com motivo `absent_or_inaccessible`.
- [ ] Para 401, 403, timeout, 429 esgotado, JSON inválido ou inventário incompleto, preservar o principal e reportar erro; não limpar a coleção.
- [ ] Se ocorrer falha global depois do inventário inicial, cancelar a fase de remoções, mesmo que alguns cards já tenham sido sincronizados.
- [ ] Tratar lista validamente vazia como um caso legítimo, sujeito às mesmas confirmações por card.

#### 9.2. Retirada recuperável

- [ ] Criar a pasta `.removed/` apenas quando houver algo a preservar.
- [ ] Validar caminho absoluto, vínculo de identidade e pertencimento à pasta `PLAN/` antes de mover um arquivo.
- [ ] Recusar `PLAN/`, arquivos ou subpastas de controle que sejam symlinks/junctions/reparse points apontando para fora do projeto.
- [ ] Mover o principal para nome único em `.removed/`, composto por ID completo e timestamp UTC com precisão suficiente para evitar sobrescrita.
- [ ] Preservar os bytes originais do principal, inclusive alterações locais, registros pendentes e metadados antigos.
- [ ] Registrar o motivo da retirada no relatório e, quando houver conflito/pendência, em artefato de revisão relacionado.
- [ ] Manter artefatos de conflito já existentes; não apagá-los junto com o card.
- [ ] Se houver edição local não sincronizada, conflito ou operação pendente, retirar recuperavelmente e retornar `1`, informando que existe trabalho a revisar.
- [ ] Quando não houver edição pendente e a mudança de lista estiver confirmada, considerar a retirada normal e bem-sucedida.
- [ ] Para ausência/inacessibilidade não distinguível de exclusão, manter aviso e saída `1`, mesmo após retirar recuperavelmente.
- [ ] Não purgar `.removed/` automaticamente nem implementar retenção temporal no MVP.
- [ ] Informar a localização do backup e a possibilidade de recuperação no resumo da operação.

O requisito de exclusão remota é atendido retirando o arquivo da raiz ativa de `PLAN/`. A cópia em `.removed/` evita perda irreversível em casos de indisponibilidade de identidade ou trabalho local pendente; não participa de futuras comparações de cards.

#### 9.3. Arquivo local apagado e card que retorna

- [ ] Quando um card existir no escopo e não houver arquivo principal, importar seu estado remoto atual.
- [ ] Não enviar exclusão, arquivamento ou movimento ao Trello por ausência local.
- [ ] Não restaurar automaticamente alterações antigas de `.removed/`; preservar o backup para revisão separada.
- [ ] Se o card voltar à lista, criar um novo principal a partir do remoto atual, mantendo backups anteriores.
- [ ] Informar criação local; sem estado global, nem sempre é possível distinguir primeira importação de recriação após exclusão manual.
- [ ] Não inventar essa distinção nas métricas: agrupar como `arquivos criados/recriados`.
- [ ] Ignorar Markdown local não gerenciado, mesmo que seu nome comece com `todo-` ou `done-`.
- [ ] Nunca sobrescrever arquivo não gerenciado para acomodar um nome gerado; resolver colisão ou reportar erro.

**Saída verificável do bloco:** card movido sai da pasta ativa, arquivo local apagado reaparece, falha de rede não apaga planos e arquivos pessoais permanecem intactos.

### Bloco 10 — Orquestração e interface de execução

#### 10.1. Sequência completa

- [ ] Interpretar CLI; `--help` e `--version` não devem exigir `.env` nem rede.
- [ ] Validar configuração, binding e acesso remoto.
- [ ] Criar `PLAN/` se necessário e adquirir lock exclusivo.
- [ ] Descobrir somente os arquivos da raiz imediata de `PLAN/`; não percorrer subpastas de backup/conflito.
- [ ] Validar metadados locais, identificar duplicatas e binding divergente antes das mutações.
- [ ] Se a varredura local estiver incompleta ou corrompida, desabilitar limpeza; processar somente cards com identidade inequívoca.
- [ ] Obter inventário remoto completo e recursos do card necessário à comparação.
- [ ] Resolver primeiro operações pendentes e decisões de conflito válidas.
- [ ] Classificar demais cards pela tabela de três versões.
- [ ] Planejar nomes finais globalmente com os dados já validados, levando em conta arquivos ocupados e cards bloqueados.
- [ ] Aplicar importações, atualizações, confirmações e renomeações seguras; preservar nome local de card em conflito até resolvê-lo.
- [ ] Realizar fase de retirada de ausentes somente depois das verificações de inventário e acesso.
- [ ] Persistir resultados confirmados e consolidar falhas sem apagar informações parciais.
- [ ] Liberar o lock próprio em finalização e retornar o código adequado.

#### 10.2. CLI e versão

```text
python sync.py
python sync.py --help
python sync.py --version
```

- [ ] Implementar CLI com `argparse`; a execução sem parâmetros realiza a sincronização automática.
- [ ] Não abrir navegador nem pedir credenciais interativamente.
- [ ] Definir versão inicial do produto como `0.1.0` e `schema_version` do documento como `1`; não confundir as duas versões.
- [ ] Não adicionar opções especulativas de daemon, múltiplas listas, force, prune, reset ou overwrite.
- [ ] Manter resolução de conflitos no arquivo, sem depender de interação no terminal.

#### 10.3. Logs e códigos de saída

| Código | Significado |
| --- | --- |
| `0` | Todos os cards processados com sucesso, inclusive execução sem mudanças. |
| `1` | Conflito, falha parcial, coleta incompleta, lock, erro de disco ou recuperação/intervenção necessária. |
| `2` | Uso ou configuração inválida, binding divergente ou versão de schema global incompatível. |
| `3` | Falha global de autenticação ou permissão de acesso ao quadro/lista. |

- [ ] Dar prioridade a falha global de autenticação caso aconteça depois de mudanças parciais; informar que o lote não foi concluído.
- [ ] Listar contagens de cards examinados, arquivos criados/recriados, atualizados, renomeados, retirados, cards enviados, sem mudança, conflitos e falhas.
- [ ] Diferenciar número de cards de número de operações; um card pode gerar atualização e renomeação.
- [ ] Registrar operações destrutivas de subitens e o caminho de recuperação de arquivos retirados.
- [ ] Usar mensagens previsíveis com ação, ID do card e erro resumido.
- [ ] Não despejar título completo, comentários, descrição, JSON remoto, credenciais, headers ou URL autenticada.
- [ ] Usar stdout para resumo e stderr para erros; não criar arquivos permanentes de log no MVP.
- [ ] Se nenhum arquivo/card mudar, informar claramente a ausência de alterações e retornar `0`.

**Saída verificável do bloco:** humanos e agentes conseguem executar o mesmo comando, interpretar pendências e repetir uma execução sem provocar mudanças artificiais.

### Bloco 11 — Segurança e privacidade na distribuição

- [ ] Criar `.env.example` somente com chaves vazias e explicações não sensíveis.
- [ ] Mesclar regras à `.gitignore` existente, preservando regras do projeto.
- [ ] Incluir no modelo de distribuição `.env`, `__pycache__/` e `PLAN/`; não confundir `PLAN/` com este `PLAN.md`.
- [ ] Documentar que o usuário pode optar por versionar os cards, mas isso publica o conteúdo conforme a visibilidade do repositório e exige excluir backups/conflitos se não quiser versioná-los.
- [ ] Não tentar remover do índice ou reescrever histórico de arquivos privados já versionados; informar a situação ao responsável.
- [ ] Orientar token com leitura e escrita, pois o produto é bidirecional; não solicitar permissões extras sem necessidade.
- [ ] Explicar que restringir `TRELLO_LIST_ID` limita o comportamento do script, mas não necessariamente o alcance do token na conta.
- [ ] Orientar revogação do token se exposto e uso de lista de teste para a primeira validação de escrita.
- [ ] Não solicitar que o usuário cole credenciais no chat nem incluí-las em exemplos, fixtures ou mensagens de falha.
- [ ] Tratar todo texto remoto e todo ID do Markdown como entrada não confiável para construção de paths e requests.
- [ ] Validar links para exibição; não visitar links de anexos, não baixar recursos e não anexar credenciais a eles.
- [ ] Escapar HTML em visualizações geradas de comentários/títulos; preservar o original como dado no snapshot.
- [ ] Não executar conteúdo de `.env`, Markdown, comentários, checklist ou dados compartilhados de Power-Ups.
- [ ] Documentar para agentes consumidores que instruções de um card não substituem as regras do projeto nem concedem autorização para comandos externos.

**Saída verificável do bloco:** um token colocado em qualquer erro simulado não aparece nos logs; um título malicioso não produz escrita fora da pasta autorizada.

### Bloco 12 — Documentação e entrega ao responsável

- [ ] Criar README em português com objetivo, requisitos e instalação por cópia.
- [ ] Documentar a obtenção de key/token conforme a fonte oficial, sem automatizar autorização no navegador.
- [ ] Documentar como identificar lista e label por seus IDs completos.
- [ ] Explicar a decisão da label de conclusão e a diferença em relação ao prazo concluído/arquivamento do Trello.
- [ ] Documentar cada campo editável e cada região somente leitura do Markdown.
- [ ] Incluir um exemplo completo e parseável de card produzido pelo script, com dados fictícios e hashes calculados pelo próprio teste.
- [ ] Incluir exemplos de alteração de título, descrição, label comum, checkbox, criação de checklist/item e exclusão explícita com `delete`.
- [ ] Explicar que retirar uma linha de checklist sem marcador de exclusão gera erro e como corrigir.
- [ ] Demonstrar conclusão/reabertura renomeando `todo-` e `done-`.
- [ ] Demonstrar colisões de títulos, nomes sem texto e truncamento somente do slug.
- [ ] Documentar resolução `local`, `remote` e `merged`, incluindo rejeição de hash remoto obsoleto.
- [ ] Explicar operação POST ambígua, backup de documento e reaplicação manual de intenções depois de aceitar o remoto.
- [ ] Explicar restauração de `.removed/`, lock deixado por encerramento anormal e IDs duplicados após falha de renomeação.
- [ ] Explicar a distinção entre erro de rede, card ausente, card movido e card arquivado.
- [ ] Documentar códigos de saída e métricas.
- [ ] Documentar limites: histórico depende da API/permissões, sem download de anexos, sem transação entre HTTP e disco, sem merge automático.
- [ ] Incluir instruções para rodar testes offline e a validação manual em lista de teste.
- [ ] Atualizar README quando uma funcionalidade pública mudar, conforme a regra do projeto.
- [ ] Não criar CHANGELOG apenas por hábito; se houver alteração/criação de `CHANGELOG.md`, manter versão SemVer consistente: major para quebra, minor para funcionalidade, patch para correção.
- [ ] Não marcar itens como concluídos apenas porque foram documentados; implementação e validação são necessárias.
- [ ] Ao entregar, informar arquivos alterados, testes realizados, limitações reais e qualquer item ainda pendente.

## 5. Critérios de validação e conclusão

### 5.1. Testes automatizados offline

Arquivos-alvo futuros: um único `test_sync.py`, usando `unittest`, `unittest.mock` quando útil e `tempfile`. Manter os testes pequenos e orientados a comportamentos e perda de dados; não exigir rede, credenciais ou framework externo. O transporte poderá ser substituído por uma função fake nos testes, sem criar uma camada de abstração pública apenas para esse fim.

#### A. Configuração e isolamento

- [ ] `.env` com BOM, aspas, `=` no valor, `#` no valor, comentários e variáveis de outro projeto.
- [ ] Campo obrigatório ausente, aspas incompletas, valor vazio e duplicidade de chave.
- [ ] Execução de outra pasta resolve a raiz do script corretamente.
- [ ] Binding de lista/quadro/label divergente preserva os arquivos e não envia requests de escrita.
- [ ] `--help` e `--version` funcionam sem `.env` e sem rede.

#### B. Nomes e parsing

- [ ] Título curto normal e título muito longo, preservando o original completo.
- [ ] Unicode, acentos, emojis, controles, nomes reservados, caracteres de caminho e título em escrita não latina.
- [ ] Imagem Markdown com/sem texto alternativo, URL pura, título misto e string sem conteúdo útil.
- [ ] Colisão por truncamento, caixa, normalização Unicode e sufixo curto igual.
- [ ] Colisão com arquivo não gerenciado, troca de títulos entre dois cards e transição `todo-`/`done-`.
- [ ] Round-trip de descrição com blocos de código, headings iguais aos da ferramenta, linhas vazias, espaços finais e CRLF.
- [ ] JSON inválido, versão desconhecida, região duplicada e marcador ausente não geram push nem remoção.
- [ ] Duas checklists/itens homônimos mantêm identidades separadas.
- [ ] Item sem ID, ID de outro card, marcador duplicado e exclusão implícita são rejeitados.
- [ ] Exclusão explícita, criação com ID temporário, renomeação e mudança de ordem mantêm o contrato definido.

#### C. Comparação e sincronização

- [ ] Cobrir todos os ramos da tabela `B/L/R`, incluindo ambos alterados com resultado igual.
- [ ] Alteração apenas em comentário ou dado somente leitura remoto não causa conflito editável.
- [ ] Edição indevida de referência local é preservada e não enviada.
- [ ] Título editado no front matter atualiza o card e o nome do arquivo.
- [ ] Alterar apenas o slug não muda o título remoto.
- [ ] `done-` adiciona a label correta e `todo-` remove somente essa label.
- [ ] Nenhuma mudança de status modifica lista, arquivamento, prazo, `dueComplete` ou conclusão das subtarefas.
- [ ] Arquivo sem alteração não é regravado e não muda seu mtime ou `last_synced_at`.
- [ ] Segunda execução após sincronização bem-sucedida faz zero escritas HTTP e zero mudanças de arquivo.

#### D. HTTP, completude e falhas

- [ ] Respostas 400, 401, 403, 404, 429, 5xx, JSON inválido e timeout são classificadas corretamente.
- [ ] Paginação com mais de uma página preserva todas as ações; cursor repetido gera erro, não loop infinito.
- [ ] Resposta incompleta jamais é convertida em lista vazia para limpeza.
- [ ] Um recurso complementar que falhou preserva o dado anterior e sinaliza coleta incompleta.
- [ ] Inventário inclui card arquivado ainda na lista.
- [ ] Falha em um card permite processar outro; falha de autenticação global interrompe próximas mutações.
- [ ] Backoff respeita limite de tentativas; simular o relógio nos testes para não esperar de verdade.
- [ ] Token e key sentinelas não aparecem em stdout/stderr, mesmo dentro de mensagem de erro HTTP simulada.

#### E. Recuperação e conflitos

- [ ] Conflito preserva base/local/remoto e bloqueia somente o card correspondente.
- [ ] Apagar artefato de conflito não autoriza overwrite; conflito é recriado.
- [ ] Resolução com hash antigo é recusada após nova alteração remota.
- [ ] Decisões local/remota/mesclada válidas convergem e limpam o estado de pendência.
- [ ] Crash antes do POST, após envio sem resposta e após resposta antes da gravação não causam criação duplicada automática.
- [ ] Falha na segunda operação preserva a primeira confirmada e a intenção restante.
- [ ] Aceitar remoto em POST ambíguo importa o estado real sem reenviar a criação.
- [ ] Edição local durante HTTP não é sobrescrita na persistência final.
- [ ] Disco cheio ou erro de substituição preserva original e pendência remota.
- [ ] Lock impede segunda execução; remoção de lock alheio não acontece automaticamente.

#### F. Remoções e arquivos pessoais

- [ ] Card movido é retirado do conjunto ativo e tem backup recuperável.
- [ ] Card ausente com dois inventários íntegros e 404 é retirado recuperavelmente com diagnóstico de ambiguidade.
- [ ] 404 isolado, 403, timeout ou inventário incompleto não removem arquivo.
- [ ] Card arquivado na mesma lista permanece representado e não vira `done-` por arquivamento.
- [ ] Arquivo apagado localmente é recriado e nenhum DELETE de card é enviado.
- [ ] Retirada de arquivo com edição pendente preserva seu conteúdo e reporta revisão necessária.
- [ ] Markdown pessoal, symlink/junction inseguro, backup e artefato de conflito não são tratados como cards ativos.
- [ ] Card que retorna à lista recebe principal novo do remoto, sem aplicar automaticamente backup antigo.

Comando esperado de validação offline:

```text
python -m unittest -v test_sync.py
```

### 5.2. Validação manual em lista de teste

Realizar somente quando o responsável indicar uma lista destinada a teste e fornecer as credenciais localmente. A ausência dessa preparação não impede implementar e validar offline, mas deve ser registrada como teste real pendente.

- [ ] Configurar uma lista descartável de teste no mesmo modelo de organização por projeto e uma label de conclusão conhecida.
- [ ] Executar importação com card contendo descrição, duas checklists, labels, comentário, anexo e datas.
- [ ] Comparar o conteúdo importado com o card original, incluindo IDs de subtarefas e links de anexo.
- [ ] Criar remotamente um novo card e confirmar criação do arquivo.
- [ ] Alterar título e descrição remotamente e confirmar atualização local.
- [ ] Alterar título e descrição localmente e confirmar atualização remota.
- [ ] Marcar/desmarcar item, criar item/checklist e testar exclusão explícita de objeto de teste.
- [ ] Associar/desassociar uma label comum sem alterar seu nome ou cor no quadro.
- [ ] Renomear `todo-` para `done-` e vice-versa; verificar que nenhuma movimentação ocorreu.
- [ ] Alterar a label de conclusão pelo Trello e verificar o prefixo.
- [ ] Criar títulos repetidos, enormes e com imagem/URL; verificar nomes seguros e título integral preservado.
- [ ] Alterar o mesmo card nos dois lados, verificar conflito e resolver cada uma das opções em cenários independentes.
- [ ] Apagar um arquivo local e verificar recriação.
- [ ] Mover um card de teste para outra lista e verificar retirada recuperável no projeto original.
- [ ] Arquivar um card de teste ainda na lista e confirmar que continua presente no planejamento local.
- [ ] Excluir definitivamente apenas um card descartável de teste e verificar a regra de ausência e recuperação local.
- [ ] Reexecutar sem novas alterações e confirmar ausência de escritas desnecessárias.
- [ ] Executar em Windows, Linux e macOS quando houver ambientes disponíveis; registrar os sistemas efetivamente testados, sem declarar portabilidade testada onde houve apenas revisão de código.

### 5.3. Aceitação por entrega

| Entrega | Condição mínima para marcar concluída |
| --- | --- |
| Configuração e transporte | Sem dependências, validação anterior a mutações, erros HTTP previsíveis e logs redigidos. |
| Importação | Um arquivo por card, incluindo arquivados da lista; conteúdo completo acessível e parser com round-trip validado. |
| Identidade e títulos | Renomeações e duplicatas não perdem IDs, não truncam título original e não sobrescrevem arquivos. |
| Escrita bidirecional | Título, descrição, checklists, labels e prefixo sincronizam pelos contratos descritos. |
| Conflitos | Base/local/remoto preservados; resolução explícita, versionada e protegida contra decisão obsoleta. |
| Falhas parciais | Nenhum POST ambíguo repetido automaticamente; pendências retomáveis e reportadas. |
| Remoções | Principal sai do escopo ativo com recuperação; falha de inventário não provoca limpeza. |
| Idempotência | Execução repetida sem mudanças não escreve no Trello nem regrava Markdown. |
| Distribuição | Script, modelo de configuração, README e testes suficientes para copiar e operar por projeto. |

### 5.4. Checklist final do agente implementador

- [ ] Todos os requisitos funcionais acordados foram implementados ou identificados claramente como pendências.
- [ ] Nenhuma dependência externa foi adicionada.
- [ ] Nenhum token ou conteúdo privado foi incluído em exemplos versionáveis.
- [ ] A versão-base só avança depois de confirmação remota e persistência local.
- [ ] Os cenários críticos de conflito, remoção e falha parcial foram executados em testes offline.
- [ ] O README descreve o formato real produzido pelo script, sem divergência com o parser.
- [ ] O contrato de `schema_version: 1` e a versão do script estão coerentes.
- [ ] Os testes passaram e as evidências foram registradas abaixo.
- [ ] A validação real no Trello foi realizada em lista de teste ou está explicitamente marcada como pendente.
- [ ] Os sistemas efetivamente testados estão registrados.
- [ ] Nenhum commit foi criado sem autorização explícita.
- [ ] As caixas deste documento foram atualizadas conforme resultados reais, sem marcar automaticamente blocos inteiros.

### 5.5. Registro de execução a preencher futuramente

| Bloco / cenário | Data | Resultado | Evidência ou comando | Pendência |
| --- | --- | --- | --- | --- |
| Implementação | — | Não iniciada | Este documento é somente planejamento | Todos os blocos de implementação |
| Testes offline | — | Não executados | A executar pelo próximo agente | `test_sync.py` |
| Integração Trello | — | Não executada | Exige lista de teste e credenciais locais | Ambiente de teste |
| Windows | — | Não validado | — | Executar testes |
| Linux | — | Não validado | — | Executar testes |
| macOS | — | Não validado | — | Executar testes |

O próximo agente deverá usar este arquivo como roteiro de execução e manter visíveis as limitações que não conseguiu validar. O término do planejamento não equivale ao término do produto.
