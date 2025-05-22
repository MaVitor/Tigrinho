# Jogo Crash Multiplayer com TCP/UDP em Python

Este projeto implementa um jogo multiplayer simples do tipo "Crash" utilizando comunicação cliente-servidor com os protocolos TCP e UDP diretamente em Python.

## Funcionalidades

* **Jogo Multiplayer:** Vários clientes podem se conectar e jogar simultaneamente.
* **Sistema de Apostas:** Jogadores podem definir um nome, receber um saldo inicial e fazer apostas.
* **Mecânica de "Crash":** Um multiplicador aumenta progressivamente, e os jogadores devem fazer "cash out" antes que o multiplicador "crashe" aleatoriamente.
* **Cash Out:** Jogadores podem retirar seus ganhos multiplicados pelo valor do multiplicador no momento do cash out.
* **Saldo Persistente (por IP, em memória):** Cada jogador (identificado pelo IP) mantém seu saldo e nome enquanto o servidor estiver rodando.
* **Ranking:** Exibe um ranking dos jogadores com mais dinheiro.
* **Comunicação em Tempo Real:**
    * TCP para comandos críticos (registro de nome, apostas, cash out, status, ranking).
    * UDP para broadcast do multiplicador e status do jogo em tempo real.

## Como Funciona

O sistema é composto por dois scripts principais:

* **`server.py`**: O servidor que gerencia a lógica do jogo, o estado dos jogadores, as apostas, e a comunicação com os clientes.
* **`client.py`**: A interface de linha de comando que os jogadores usam para se conectar ao servidor e interagir com o jogo.

### Fluxo de Comunicação:

1.  **Conexão TCP:** O cliente estabelece uma conexão TCP com o servidor para enviar comandos e receber respostas diretas.
    * O cliente envia seu nome para ser registrado no servidor.
    * O cliente envia comandos como "bet" (apostar), "cash_out", "status" (ver status do jogo e saldo) e "get_ranking".
    * O servidor processa esses comandos e envia respostas JSON de volta ao cliente específico.
2.  **Broadcast UDP:** O servidor envia continuamente (a cada `TICK_RATE`) o estado atual do jogo (status "waiting", "running", "crashed" e o valor do multiplicador) para todos os clientes via broadcast UDP.
    * Os clientes escutam esses broadcasts para atualizar sua interface e lógica local (ex: exibir o multiplicador subindo, saber quando podem apostar ou quando o jogo crashou).

## Pré-requisitos

* Python 3.x

## Configuração e Execução

### Para Teste Local (Servidor e Cliente na Mesma Máquina)

1.  **Servidor (`server.py`):**
    * Verifique se as configurações no início do arquivo `server.py` estão adequadas. `TCP_HOST = '0.0.0.0'` e `broadcast_address = ('255.255.255.255', UDP_PORT)` devem funcionar bem.
    * Abra um terminal ou prompt de comando.
    * Navegue até o diretório onde o arquivo `server.py` está localizado.
    * Execute o servidor com o comando:
        ```bash
        python server.py
        ```
    * Você deverá ver a mensagem `Servidor iniciado - TCP: 0.0.0.0:5000, UDP Broadcast para porta: 5001`.

2.  **Cliente (`client.py`):**
    * No arquivo `client.py`, certifique-se de que a variável `SERVER_HOST` está configurada para o endereço de loopback:
        ```python
        SERVER_HOST = '127.0.0.1'
        ```
    * Abra um novo terminal ou prompt de comando para cada instância do cliente que você deseja rodar.
    * Navegue até o diretório onde o arquivo `client.py` está localizado.
    * Execute o cliente com o comando:
        ```bash
        python client.py
        ```
    * O cliente tentará se conectar ao servidor, pedirá seu nome e, em seguida, exibirá o menu do jogo.

### Para Jogar em Rede Local (Clientes em Outras Máquinas)

1.  **Identifique o IP da Máquina Servidora:**
    * Na máquina que rodará o `server.py`, abra o prompt de comando/terminal e use `ipconfig` (Windows) ou `ifconfig`/`ip addr show` (Linux/macOS) para descobrir o endereço IPv4 da interface de rede que está conectada à rede local (ex: Wi-Fi ou Ethernet). Suponha que seja `192.168.1.100`.

2.  **Servidor (`server.py`):**
    * Mantenha `TCP_HOST = '0.0.0.0'` no `server.py`. Isso garante que ele escute em todas as interfaces de rede, incluindo o IP da sua rede local.
    * Execute o `server.py` conforme descrito acima.
    * **IMPORTANTE: Firewall do Servidor!** Certifique-se de que o firewall na máquina servidora (ex: Firewall do Windows) está configurado para permitir:
        * Conexões TCP de **entrada** na porta `5000` (ou para o `python.exe`).
        * Tráfego UDP de **saída** (especialmente broadcasts) na porta `5001` (ou para o `python.exe`).

3.  **Cliente (`client.py`):**
    * Nas máquinas clientes, edite o arquivo `client.py` e altere a variável `SERVER_HOST` para o endereço IP da máquina servidora que você identificou no passo 1:
        ```python
        SERVER_HOST = '192.168.1.100' # Substitua pelo IP real do seu servidor
        ```
    * Execute o `client.py` nas máquinas clientes.
    * **IMPORTANTE: Firewall do Cliente!** Certifique-se de que o firewall nas máquinas clientes permite:
        * Tráfego UDP de **entrada** na porta `5001` (ou para o `python.exe`).

## Estrutura do Código

### `server.py`

* **Configurações Globais:** Constantes para rede, regras do jogo, saldo inicial, etc.
* **`game_state` e `player_data_store`:** Dicionários que mantêm o estado da rodada atual e os dados persistentes (em memória) dos jogadores, respectivamente.
* **`handle_tcp_client()`:** Função executada em uma thread para cada cliente. Processa comandos TCP (set\_name, bet, cash\_out, status, get\_ranking) e interage com os dicionários de estado.
* **`broadcast_game_updates()`:** Função em uma thread que envia continuamente o status do jogo e o multiplicador via UDP broadcast.
* **`game_loop()`:** Função em uma thread que controla o ciclo principal do jogo (waiting, running, crashed), incluindo a lógica de incremento do multiplicador e o cálculo do crash.
* **Sockets e Threading:** Uso da biblioteca `socket` para comunicação e `threading` para concorrência.

### `client.py`

* **Configurações:** IP e portas do servidor.
* **Conexão Inicial:** Conecta-se ao TCP do servidor, faz o bind do socket UDP e envia o nome do jogador.
* **Variáveis de Estado Locais:** Mantém o status do jogo, multiplicador, saldo, etc., atualizados com base nas informações do servidor.
* **`receive_udp_updates()`:** Função em uma thread que escuta os broadcasts UDP do servidor e atualiza o estado local do cliente, incluindo a lógica crucial para resetar `has_active_bet`.
* **`send_tcp_command()`:** Envia comandos JSON para o servidor via TCP e processa as respostas.
* **`show_menu()`:** Exibe a interface de linha de comando para o jogador.
* **Loop Principal:** Gerencia a interação do usuário e as chamadas de função correspondentes.

## Explicação Detalhada de Funcionalidades

* **Cálculo do Crash:** O crash é determinado por uma combinação de uma chance aleatória a cada "tick" (`CRASH_PROBABILITY`) e um multiplicador máximo (`MAX_MULTIPLIER`).
* **Incremento do Multiplicador:** O fator de incremento (`increment_factor`) é dinâmico, aumentando com base no valor atual do multiplicador e no tempo decorrido na rodada, fazendo com que o multiplicador acelere.
* **Gerenciamento de Saldo e Nomes:** O `player_data_store` no servidor usa o IP do cliente como chave para armazenar um dicionário contendo o saldo e o nome do jogador.
* **Ranking:** O servidor classifica os jogadores no `player_data_store` pelo saldo em ordem decrescente para gerar o ranking.

---