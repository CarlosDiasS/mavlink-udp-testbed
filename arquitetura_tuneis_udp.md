# Arquitetura de comunicação MAVLink com dois túneis UDP

## 1. Objetivo e conclusão

Os três scripts implementam a cadeia **GCS ↔ túnel da estação ↔ túnel do drone ↔ endpoint UDP do SITL/MAVProxy**. Os comandos percorrem essa cadeia em direção ao veículo; a telemetria percorre o sentido inverso.

Arquivos analisados:

- `gcs_mavlink.py`: aplicação GCS, com interpretação e geração de MAVLink.
- `tunel_udp_station.py`: primeiro túnel, no lado da estação.
- `tunel_udp_drone.py`: segundo túnel, no lado do drone.

Os túneis são encaminhadores UDP em espaço de usuário. Eles simulam o transporte intermediário do serviço de comunicação, sem implementar rádio XBee, DigiMesh, endereçamento MAC ou características de um enlace físico.

## 2. Mapa definitivo das portas

**Uma porta pertence ao processo que faz `bind()` nela. O destino de um envio é a porta ocupada pelo processo receptor.**

| Processo | Endereço local de recepção | Papel do socket |
| --- | --- | --- |
| GCS | `0.0.0.0:14101` | Receber telemetria do túnel da estação e enviar comandos pelo mesmo socket |
| Túnel da estação | `127.0.0.1:14003` | Comunicar-se com a GCS |
| Túnel da estação | `127.0.0.1:14200` | Comunicar-se com o túnel do drone |
| Túnel do drone | `127.0.0.1:14100` | Comunicar-se com o túnel da estação |
| Túnel do drone | `127.0.0.1:14550` | Comunicar-se com o endpoint UDP do SITL/MAVProxy |
| Endpoint SITL/MAVProxy | `127.0.0.1:P` | Enviar telemetria para `14550` e receber comandos de volta; `P` é a porta de origem observada |

`P` representa a porta real usada pelo emissor da telemetria. Ela pode ser dinâmica e não está fixada nos scripts. Por isso, o túnel do drone a aprende a partir dos datagramas recebidos.

**A porta `14550` é ocupada pelo túnel do drone neste teste.** Dizer que ela é “a porta do SITL” pode induzir a erro: aqui ela é o destino UDP da telemetria que sai do SITL/MAVProxy, não necessariamente a porta local do processo que a transmite.

Os pares de comunicação são:

| Enlace | Endpoint de um lado | Endpoint do outro lado |
| --- | --- | --- |
| GCS ↔ estação | GCS `14101` | Estação `14003` |
| Estação ↔ drone | Estação `14200` | Drone `14100` |
| Drone ↔ SITL/MAVProxy | Drone `14550` | SITL/MAVProxy `P` |

Cada socket serve para **receber e enviar**. Os dois sockets de cada túnel correspondem aos dois vizinhos, não a um socket exclusivo de transmissão e outro exclusivo de recepção.

### Diagrama da arquitetura

![Arquitetura UDP: GCS 14101 ↔ túnel da estação 14003 / 14200 ↔ túnel do drone 14100 / 14550 ↔ SITL P](<image(20261029-191545).png>)

Os números junto aos blocos indicam as portas locais de cada processo. Os comandos MAVLink seguem da esquerda para a direita; a telemetria percorre o sentido inverso. **P** é a porta de origem do SITL/MAVProxy, aprendida pelo túnel do drone ao receber telemetria. No teste local, todos os enlaces usam `127.0.0.1`.

## 3. Conceitos de UDP usados no código

### IP, porta e socket

O IP indica o host/interface; a porta identifica o ponto de comunicação dentro daquele host. Um socket UDP é o recurso usado pelo programa para trocar datagramas.

`127.0.0.1` é o endereço de loopback: todos os scripts, na configuração atual, comunicam-se dentro da mesma máquina e do mesmo contexto de rede. Separar os blocos em “estação” e “drone” representa uma divisão lógica; não significa que já estejam em dois computadores.

`0.0.0.0`, usado no `udpin` da GCS, significa receber pelas interfaces IPv4 locais. Não é um endereço de destino remoto. Como os túneis usam loopback, a origem da GCS vista por eles neste teste é `127.0.0.1:14101`.

### `bind()`, `recvfrom()` e `sendto()`

```python
socket_lado_gcs.bind((IP_LOCAL, PORTA_LOCAL_LADO_GCS))
```

No túnel da estação, essa linha associa o socket à porta local `14003`.

```python
dados, origem = sock.recvfrom(65535)
```

Essa operação recebe um datagrama. `dados` contém seus bytes; `origem` contém o IP e a porta do remetente imediato. O valor `65535` é a capacidade de leitura solicitada, não o tamanho de toda mensagem recebida nem a carga útil máxima de UDP/IPv4.

```python
socket_lado_gcs.sendto(dados, ENDERECO_GCS)
```

Como esse socket já foi associado à porta `14003`, a GCS recebe um datagrama **de `14003` para `14101`**. `sendto()` define o destino; a porta de origem vem do socket utilizado.

UDP não estabelece uma sessão por handshake. No teste, “conectado” significa que a aplicação recebeu um HEARTBEAT e passou a conhecer o veículo; não que o transporte UDP realizou uma conexão equivalente à do TCP.

## 4. Caminho da telemetria: SITL até a GCS

A telemetria inicial também prepara o caminho para os comandos.

| Passo | Emissor | Destino | Ação ao receber |
| --- | --- | --- | --- |
| 1 | SITL/MAVProxy, porta `P` | Túnel do drone, `14550` | Guarda a origem `P` e encaminha os bytes pelo socket `14100` |
| 2 | Túnel do drone, `14100` | Túnel da estação, `14200` | Guarda a origem `14100` e encaminha os bytes pelo socket `14003` |
| 3 | Túnel da estação, `14003` | GCS, `14101` | O pymavlink recebe e interpreta as mensagens |

Todos os endereços da tabela são locais, `127.0.0.1`.

### No túnel do drone

O datagrama chega a `socket_lado_sitl`, associado à porta `14550`. O script executa:

```python
endereco_sitl_aprendido = origem
socket_lado_tunel_estacao.sendto(dados, ENDERECO_TUNEL_ESTACAO)
```

`ENDERECO_TUNEL_ESTACAO` vale `("127.0.0.1", 14200)`. O envio utiliza `socket_lado_tunel_estacao`, associado à porta `14100`. Portanto, o datagrama sai de `14100` e vai para `14200`, enquanto a origem final `P` fica guardada para os comandos.

### No túnel da estação

O datagrama chega a `socket_lado_tunel_drone`, associado à porta `14200`. O script executa:

```python
endereco_tunel_drone_aprendido = origem
socket_lado_gcs.sendto(dados, ENDERECO_GCS)
```

A origem guardada é `("127.0.0.1", 14100)`. `ENDERECO_GCS` vale `("127.0.0.1", 14101)` e `socket_lado_gcs` usa a porta `14003`. Assim, a GCS recebe o datagrama de `14003` para `14101`.

A estação aprende o endereço do **túnel do drone**, seu vizinho imediato; ela não conhece a porta `P` do endpoint final.

## 5. Caminho dos comandos: GCS até o SITL

Depois que a telemetria percorre a cadeia, cada componente conhece o vizinho necessário para enviar no sentido contrário.

| Passo | Emissor | Destino | Como o destino é conhecido |
| --- | --- | --- | --- |
| 1 | GCS, `14101` | Túnel da estação, `14003` | Aprendido pelo pymavlink ao receber datagramas |
| 2 | Túnel da estação, `14200` | Túnel do drone, `14100` | Guardado em `endereco_tunel_drone_aprendido` |
| 3 | Túnel do drone, `14550` | SITL/MAVProxy, `P` | Guardado em `endereco_sitl_aprendido` |

### Encaminhamento nos túneis

Na estação, o comando entra por `socket_lado_gcs` (`14003`). Após conferir a origem e a existência do endereço aprendido, o script executa:

```python
socket_lado_tunel_drone.sendto(dados, endereco_tunel_drone_aprendido)
```

O envio sai de `14200` para `14100`. No drone, o comando entra por `socket_lado_tunel_estacao` (`14100`). Depois das verificações equivalentes:

```python
socket_lado_sitl.sendto(dados, endereco_sitl_aprendido)
```

O envio sai de `14550` para a porta `P` aprendida.

### Por que a GCS não declara `14003`?

A GCS abre `udpin:0.0.0.0:14101`. No modo de entrada UDP, o pymavlink registra os remetentes recebidos e usa esses endereços nos envios. Nesta arquitetura, o remetente esperado é apenas `127.0.0.1:14003`, o primeiro túnel. Assim, a recepção inicial permite enviar os comandos de volta ao túnel. Isso pressupõe que não existam outros emissores alimentando a mesma porta da GCS.

Esse comportamento pode ser consultado na classe `mavudp`, métodos `recv()` e `write()`, no [código oficial do pymavlink](https://github.com/ArduPilot/pymavlink/blob/master/mavutil.py).

### Por que manter o mesmo socket no retorno?

O túnel da estação verifica se os comandos vieram exatamente de `127.0.0.1:14101`. O túnel do drone verifica se vieram de `127.0.0.1:14200`.

Se a estação usasse um socket novo, com porta de origem aleatória, para transmitir ao drone, este descartaria os datagramas por origem inesperada. Enviar pelo socket já associado a `14200` preserva o par de endpoints esperado.

## 6. Aprendizado dos endereços e inicialização

Na estação, `endereco_tunel_drone_aprendido` começa como `None`; no drone, `endereco_sitl_aprendido` começa como `None`. Cada variável é atualizada quando um datagrama chega pelo respectivo socket voltado ao lado do veículo.

| Componente | Endereço configurado previamente | Endereço aprendido pela recepção |
| --- | --- | --- |
| GCS | Porta local `14101` | Estação `127.0.0.1:14003` |
| Túnel da estação | GCS `127.0.0.1:14101` | Drone `127.0.0.1:14100` |
| Túnel do drone | Estação `127.0.0.1:14200` | SITL/MAVProxy `127.0.0.1:P` |

A sequência necessária é:

1. Os processos abrem seus sockets, sem conflito de portas.
2. O endpoint do SITL/MAVProxy envia telemetria para `127.0.0.1:14550`.
3. O túnel do drone aprende o endpoint final e encaminha os bytes à estação.
4. A estação aprende o endpoint do túnel do drone e encaminha os bytes à GCS.
5. A GCS recebe um HEARTBEAT, identifica o veículo e começa o teste.

Se um comando chegar a um túnel antes de ele conhecer a origem do lado do veículo, será descartado. Não existe fila de comandos pendentes. A mensagem “Ainda não recebi telemetria do SITL” indica essa condição; no túnel da estação, ela significa que ainda não chegou tráfego do túnel do drone.

**O envio inicial de telemetria pelo endpoint final é uma condição de funcionamento.** Se todos os componentes apenas esperarem receber, a cadeia não será inicializada.

## 7. O que cada script executa

### GCS: `gcs_mavlink.py`

O script abre a porta `14101`, com identidade MAVLink `source_system=255` e `source_component=190`. Esses números são identificadores dentro do protocolo MAVLink; não são portas UDP.

Em seguida:

1. Aguarda um HEARTBEAT, sem timeout explícito nessa chamada.
2. Solicita `ATTITUDE`, `GLOBAL_POSITION_INT`, `VFR_HUD` e `SYS_STATUS`, com intervalo solicitado de `1.000.000 µs` (1 segundo) para cada tipo.
3. Imprime cinco conjuntos de telemetria.
4. Envia `MAV_CMD_DO_SET_MODE` solicitando `GUIDED`.
5. Procura confirmar o modo por HEARTBEAT durante aproximadamente dez segundos.
6. Imprime outros cinco conjuntos e fecha a conexão no bloco `finally`.

Cada conjunto reúne uma mensagem de cada um dos quatro tipos. As mensagens podem ter instantes diferentes; não representam necessariamente uma amostra sincronizada. A frequência é solicitada ao veículo, não garantida pelo túnel.

O timeout de cinco segundos de `recv_match()` vale por chamada. Se alguns tipos continuarem chegando e outro nunca chegar, o laço de coleta pode continuar aguardando o tipo faltante, pois não há prazo global para completar o conjunto.

O teste muda o modo para GUIDED, mas não contém comandos de armar, decolar ou pousar. A ausência de confirmação de GUIDED não prova, sozinha, uma falha de UDP: a solicitação pode ter chegado e o veículo não ter alterado o modo.

### Túneis: estação e drone

Ambos utilizam `socket` e `select`, sem pymavlink. `select.select()` aguarda atividade nos dois sockets; quando há dados, o programa lê um datagrama e escolhe o sentido de encaminhamento conforme o socket que o recebeu.

O recebimento ocorre por um socket e o reenvio pelo socket do outro lado. Isso mantém a separação dos dois enlaces. Não há criação de mensagens MAVLink, decodificação, mudança de sistema-alvo ou cálculo de novos campos MAVLink pelos túneis.

## 8. O que é preservado e o que muda

**Os bytes da carga útil são preservados. Os endereços UDP de origem e destino mudam em cada salto.**

Cada túnel recebe `dados` e passa os mesmos bytes para `sendto()`. O sistema operacional constrói um novo datagrama UDP/IP com os endereços do enlace seguinte. Portanto, não há preservação integral do pacote IP original.

Um datagrama recebido gera um envio correspondente no caminho aceito pelo código. Isso não significa que um datagrama contenha exatamente uma mensagem MAVLink: os túneis não analisam essa estrutura.

A GCS vê a estação como remetente UDP, embora as mensagens MAVLink transportadas tenham sido produzidas pelo veículo. Endereçamento de transporte e identidade MAVLink são camadas distintas.

## 9. Dicionário das variáveis atuais

Os nomes abaixo já estão presentes nos arquivos atualizados. `PORTA_LOCAL_...` identifica onde o próprio túnel faz `bind()`. `ENDERECO_...` identifica um destino remoto configurado, mesmo quando esse destino está na mesma máquina. Os nomes terminados em `_aprendido` guardam o par `(IP, porta)` obtido por `recvfrom()`.

### Túnel da estação

| Variável | Valor ou associação | Uso |
| --- | --- | --- |
| `IP_LOCAL` | `127.0.0.1` | Interface local dos dois sockets |
| `ENDERECO_GCS` | `127.0.0.1:14101` | Destino da telemetria e origem exigida para os comandos |
| `PORTA_LOCAL_LADO_GCS` | `14003` | Porta local voltada à aplicação GCS |
| `PORTA_LOCAL_LADO_TUNEL_DRONE` | `14200` | Porta local voltada ao segundo túnel |
| `socket_lado_gcs` | Associado a `14003` | Recebe comandos da GCS e envia telemetria à GCS |
| `socket_lado_tunel_drone` | Associado a `14200` | Recebe telemetria do drone e envia comandos ao drone |
| `endereco_tunel_drone_aprendido` | Inicialmente `None`; depois `127.0.0.1:14100` | Destino dos comandos enviados ao segundo túnel |

### Túnel do drone

| Variável | Valor ou associação | Uso |
| --- | --- | --- |
| `IP_LOCAL` | `127.0.0.1` | Interface local dos dois sockets |
| `ENDERECO_TUNEL_ESTACAO` | `127.0.0.1:14200` | Destino da telemetria e origem exigida para os comandos |
| `PORTA_LOCAL_LADO_TUNEL_ESTACAO` | `14100` | Porta local voltada ao primeiro túnel |
| `PORTA_LOCAL_LADO_SITL` | `14550` | Porta local voltada ao SITL/MAVProxy |
| `socket_lado_tunel_estacao` | Associado a `14100` | Recebe comandos da estação e envia telemetria à estação |
| `socket_lado_sitl` | Associado a `14550` | Recebe telemetria final e envia comandos ao endpoint final |
| `endereco_sitl_aprendido` | Inicialmente `None`; depois `127.0.0.1:P` | Destino dos comandos enviados ao SITL/MAVProxy |

### Variáveis do laço de recepção

| Variável | Significado |
| --- | --- |
| `sockets_prontos` | Sockets que `select.select()` identificou como prontos para leitura |
| `sock` | Socket atualmente processado no laço |
| `dados` | Bytes do datagrama recebido, encaminhados sem alteração |
| `origem` | IP e porta do remetente imediato do datagrama |

### Comentários e logs que ainda usam nomes genéricos

Os nomes das variáveis estão mais claros, mas alguns textos dos scripts mantêm a nomenclatura anterior. Eles não alteram o funcionamento; precisam ser interpretados conforme o vizinho real:

| Local | Texto ou comentário atual | Interpretação correta |
| --- | --- | --- |
| Estação, porta `14200` | “Entrada da telemetria SITL” | Telemetria encaminhada pelo túnel do drone |
| Estação, ao aprender a origem | Comentário sobre porta dinâmica do MAVProxy | A origem imediata aprendida aqui é o túnel do drone em `14100` |
| Estação, logs com `SITL {origem}` ou `SITL {endereco_tunel_drone_aprendido}` | Rótulo `SITL` | O endereço mostrado pertence ao túnel do drone |
| Drone, porta `14100` | “Entrada da GCS” | Entrada de comandos encaminhados pelo túnel da estação |
| Drone, filtro/logs com `GCS` | “Origem GCS inesperada” e `GCS {origem}` | A origem comparada é o túnel da estação em `14200` |

Para uma apresentação, prefira chamar os vizinhos de **GCS**, **túnel da estação**, **túnel do drone** e **SITL/MAVProxy**, conforme o processo envolvido. Este documento descreve os arquivos recebidos; não altera seus comentários ou logs.

## 10. Execução e diagnóstico

### Sequência sugerida

Com o ambiente Python da GCS já preparado com pymavlink, abra terminais separados:

```bash
python3 'tunel_udp_station.py'
```

```bash
python3 'tunel_udp_drone.py'
```

```bash
python3 'gcs_mavlink.py'
```

Inicie ou mantenha o SITL/MAVProxy configurado para enviar telemetria a `127.0.0.1:14550` e aceitar o retorno pelo mesmo endpoint de origem. Os três arquivos não incluem a inicialização do SITL/MAVProxy; por isso, essa configuração externa precisa ser conferida no ambiente de execução.

Os túneis não terminam automaticamente quando o teste da GCS acaba. Encerre-os com `Ctrl+C` ao finalizar.

### Verificar portas no Linux

```bash
ss -lunp | grep -E ':(14003|14100|14101|14200|14550)([[:space:]]|$)'
```

Compare os processos exibidos com a tabela da seção 2. Para UDP, é normal aparecer `UNCONN`; isso não significa que os datagramas não estejam circulando.

| Sintoma | O que verificar |
| --- | --- |
| `Address already in use` | Outro processo ou segunda cópia do túnel já ocupa uma das portas locais |
| GCS parada em “Aguardando HEARTBEAT” | Se existe telemetria chegando em `14550` e passando por ambos os túneis |
| “Origem GCS inesperada” na estação | A origem dos comandos deve ser `127.0.0.1:14101` |
| “Origem GCS inesperada” no drone | A origem dos comandos deve ser `127.0.0.1:14200` |
| “Ainda não recebi telemetria” | O túnel ainda não aprendeu o endpoint do lado do veículo |
| Telemetria chega, GUIDED não é confirmado | Percurso de ida, encaminhamento pelo MAVProxy e resposta/estado do veículo |

Não execute outro receptor, como uma GCS adicional, disputando a porta `14550` com o túnel do drone. Também não tente resolver a topologia compartilhando indiscriminadamente uma mesma porta entre processos: cada endpoint da tabela deve ter seu proprietário definido.

## 11. Limites do teste e uso em máquinas diferentes

O encaminhamento atual não adiciona retransmissão, confirmação de entrega, criptografia ou garantia de ordem. Os filtros de origem no lado da estação são comparações de IP e porta, não autenticação.

No lado voltado ao veículo, os túneis aprendem a origem de qualquer datagrama recebido naquele socket; o valor anterior pode ser substituído. Isso atende ao teste controlado com um veículo e um vizinho por lado, mas não implementa roteamento para múltiplos drones.

Para distribuir os dois túneis entre computadores, seria necessário:

- Fazer o socket `14200` da estação e o socket `14100` do drone receberem em interfaces acessíveis pela rede.
- Alterar `ENDERECO_TUNEL_ESTACAO` no túnel do drone para o IP real da estação, porta `14200`.
- Garantir que o filtro de origem do drone corresponda ao IP/porta efetivamente usados pela estação.
- Permitir o tráfego UDP entre esses endpoints na rede.

GCS e primeiro túnel podem continuar usando loopback entre si se estiverem na mesma máquina. O mesmo vale para segundo túnel e SITL/MAVProxy. Trocar apenas o IP de destino, mantendo o socket receptor restrito a `127.0.0.1`, não torna o enlace acessível remotamente.

## 12. Verificação realizada para este documento

Os dois túneis atualizados (`tunel_udp_station(2).py` e `tunel_udp_drone(3).py`) foram executados em um teste local com sockets substituindo a GCS e o endpoint SITL/MAVProxy. Um datagrama binário de telemetria foi enviado a `14550`, atravessou os túneis e chegou à GCS de teste em `14101`, com origem `14003`. A resposta percorreu o sentido inverso e chegou ao endpoint final com origem `14550`.

Os bytes foram comparados nos dois sentidos e permaneceram idênticos. Isso verifica o encadeamento UDP dos túneis. **Não foi executado um SITL real nem validada a mudança para GUIDED nesse teste.** A GCS foi analisada pelo código; o comportamento de descoberta de remetentes do `udpin` foi conferido no código oficial do pymavlink.

## 13. Roteiro curto para apresentação oral

> A GCS usa a porta 14101 e conversa somente com o primeiro túnel, pela porta 14003. Esse túnel usa sua outra porta, 14200, para conversar com a porta 14100 do túnel do drone. O túnel do drone recebe a telemetria do SITL/MAVProxy em 14550 e aprende o endereço de origem para enviar comandos de volta. A telemetria inicia esse aprendizado e chega até a GCS. Depois, os comandos percorrem os mesmos pares de sockets no sentido inverso. Cada túnel preserva os bytes MAVLink e cria um novo envio UDP para o vizinho seguinte.