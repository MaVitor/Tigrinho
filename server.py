import socket
import threading
import time
import random
import json

# Configurações do servidor
TCP_HOST = '0.0.0.0'
TCP_PORT = 5000
UDP_PORT = 5001

# Configurações do jogo
MIN_MULTIPLIER = 1.0
MAX_MULTIPLIER = 10.0
CRASH_PROBABILITY = 0.01 # Chance de crashar
TICK_RATE = 0.1 # Intervalo de atualização do multiplicador
INITIAL_BALANCE = 100.0 # Saldo inicial dos jogadores
DEFAULT_PLAYER_NAME = "Anônimo" # Nome default pra quando não colocar nome
RANKING_TOP_N = 10 # Número de jogadores no ranking

# Dicionario de Estado do jogo
game_state = {
    "status": "waiting",
    "multiplier": 1.0,
    "players": {}, # {client_addr_tuple: {"bet": amount, "cash_out": multiplier, "ip": ip_str}}
    "history": []
}

# Saldos e Nomes dos jogadores (em memória)
# Estrutura: {"ip_address_str": {"balance": balance_float, "name": "nome_str"}}
player_data_store = {}

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_socket.bind((TCP_HOST, TCP_PORT))
tcp_socket.listen(5)

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

print(f"Servidor iniciado - TCP: {TCP_HOST}:{TCP_PORT}, UDP Broadcast para porta: {UDP_PORT}")

def get_player_name(ip_str):
    # Retorna o nome do jogador ou um nome padrão se não estiver definido
    player_info = player_data_store.get(ip_str)
    if player_info and player_info.get("name"):
        return player_info["name"]
    return f"{DEFAULT_PLAYER_NAME}_{ip_str.split('.')[-1]}"


# Função para lidar com conexões TCP
def handle_tcp_client(client_socket, client_addr_tuple):
    client_ip = client_addr_tuple[0]
    print(f"Nova conexão TCP de {client_addr_tuple} (IP: {client_ip})")

    if client_ip not in player_data_store:
        default_name_for_new_player = f"{DEFAULT_PLAYER_NAME}_{client_ip.split('.')[-1]}"
        player_data_store[client_ip] = {"balance": INITIAL_BALANCE, "name": default_name_for_new_player}
        print(f"Novo jogador (IP: {client_ip}) registrado com saldo inicial de {INITIAL_BALANCE:.2f} e nome '{default_name_for_new_player}'.")
    
    current_player_name_for_log = get_player_name(client_ip)

    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            
            message = json.loads(data.decode('utf-8'))
            command = message.get("command")
            response = {"status": "error", "message": "Comando desconhecido"}

            player_entry = player_data_store.get(client_ip, {"balance": 0, "name": client_ip})
            current_player_balance = player_entry.get("balance", 0)
            current_player_name_for_log = player_entry.get("name", client_ip)

            if command == "set_name":
                name_from_client = message.get("name", "").strip()
                if name_from_client:
                    player_data_store[client_ip]["name"] = name_from_client
                    current_player_name_for_log = name_from_client
                    response = {"status": "name_set_ok", "name": name_from_client, "message": f"Nome definido como {name_from_client}"}
                    print(f"Jogador {client_addr_tuple} (IP: {client_ip}) atualizou nome para: {name_from_client}")
                else:
                    response = {"status": "error", "message": "Nome não pode ser vazio."}
            
            elif command == "bet":
                if game_state["status"] == "waiting":
                    amount = message.get("amount", 0)
                    if client_addr_tuple in game_state["players"]:
                        response = {"status": "error", "message": "Você já tem uma aposta ativa nesta rodada.", "balance": current_player_balance}
                    elif amount <= 0:
                        response = {"status": "error", "message": "Valor da aposta deve ser positivo.", "balance": current_player_balance}
                    elif current_player_balance < amount:
                        response = {"status": "error", "message": "Saldo insuficiente.", "balance": current_player_balance}
                    else:
                        player_data_store[client_ip]["balance"] -= amount
                        game_state["players"][client_addr_tuple] = {
                            "bet": amount,
                            "cash_out": None,
                            "ip": client_ip 
                        }
                        response = {"status": "bet_accepted", "amount": amount, "balance": player_data_store[client_ip]["balance"]}
                        print(f"Jogador '{current_player_name_for_log}' ({client_ip}) apostou {amount:.2f}. Saldo restante: {player_data_store[client_ip]['balance']:.2f}")
                else:
                    response = {"status": "error", "message": "Apostas encerradas ou jogo em progresso.", "balance": current_player_balance}
                    
            elif command == "cash_out":
                if game_state["status"] == "running":
                    player_round_data = game_state["players"].get(client_addr_tuple)
                    if player_round_data and player_round_data["cash_out"] is None:
                        cash_out_multiplier = game_state["multiplier"]
                        player_round_data["cash_out"] = cash_out_multiplier
                        
                        bet_amount = player_round_data["bet"]
                        winnings = bet_amount * cash_out_multiplier
                        player_data_store[client_ip]["balance"] += winnings
                        
                        response = {
                            "status": "cash_out_success",
                            "multiplier": cash_out_multiplier,
                            "winnings": winnings,
                            "balance": player_data_store[client_ip]["balance"]
                        }
                        print(f"Jogador '{current_player_name_for_log}' ({client_ip}) sacou em {cash_out_multiplier:.2f}x. Ganhos: {winnings:.2f}. Novo saldo: {player_data_store[client_ip]['balance']:.2f}")
                    else:
                        response = {"status": "error", "message": "Sem aposta ativa ou já sacou.", "balance": current_player_balance}
                else:
                    response = {"status": "error", "message": "Jogo não está em execução.", "balance": current_player_balance}
            
            elif command == "status":
                response = {
                    "status": "game_status",
                    "game_status": game_state["status"],
                    "multiplier": game_state["multiplier"],
                    "history": game_state["history"][-10:],
                    "balance": current_player_balance,
                    "player_name": current_player_name_for_log
                }
            
            elif command == "get_ranking":
                ranking_list = []
                for ip, data in player_data_store.items():
                    ranking_list.append({
                        "name": data.get("name", f"{DEFAULT_PLAYER_NAME}_{ip.split('.')[-1]}"),
                        "balance": data.get("balance", 0)
                    })
                sorted_players = sorted(ranking_list, key=lambda x: x["balance"], reverse=True)
                response = {"status": "ranking_data", "ranking": sorted_players[:RANKING_TOP_N]}
                print(f"Jogador '{current_player_name_for_log}' ({client_ip}) solicitou o ranking.")

            client_socket.send(json.dumps(response).encode('utf-8'))
            
    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON de '{get_player_name(client_ip)}' ({client_addr_tuple})")
    except ConnectionResetError:
        print(f"Conexão TCP com '{get_player_name(client_ip)}' ({client_addr_tuple}) resetada.")
    except BrokenPipeError: 
        print(f"Conexão TCP com '{get_player_name(client_ip)}' ({client_addr_tuple}) foi quebrada (BrokenPipe).")
    except Exception as e:
        print(f"Erro na conexão TCP com '{get_player_name(client_ip)}' ({client_addr_tuple}): {e}")
    finally:
        if client_addr_tuple in game_state["players"]:
            del game_state["players"][client_addr_tuple]
        client_socket.close()
        print(f"Conexão TCP com '{get_player_name(client_ip)}' ({client_addr_tuple}) encerrada")

def broadcast_game_updates():
    while True:
        update = {
            "status": game_state["status"],
            "multiplier": game_state["multiplier"]
        }
        message = json.dumps(update).encode('utf-8')
        broadcast_address = ('255.255.255.255', UDP_PORT)
        try:
            udp_socket.sendto(message, broadcast_address)
        except Exception as e:
            pass
        time.sleep(TICK_RATE)

def game_loop():
    global game_state
    
    while True:
        game_state["status"] = "waiting"
        game_state["multiplier"] = 1.0
        game_state["players"] = {}
        print("\n----------------------------------")
        print(f"Aguardando apostas (10 segundos)... Nomes e Saldos Atuais: ")
        if player_data_store:
            for ip, data in player_data_store.items():
                print(f"  - IP: {ip}, Nome: {data.get('name', 'N/A')}, Saldo: {data.get('balance', 0):.2f}")
        else:
            print("  Nenhum jogador registrado ainda.")
        time.sleep(10)
        
        if not game_state["players"]:
            print("Nenhuma aposta recebida. Reiniciando ciclo...")
            continue
            
        game_state["status"] = "running"
        print("Jogo iniciado!")
        
        crashed = False
        start_time = time.time()
        while not crashed:
            increment_factor = 0.01 + (game_state["multiplier"] * 0.0005) + ((time.time() - start_time) * 0.0001)
            game_state["multiplier"] += increment_factor
            game_state["multiplier"] = round(game_state["multiplier"], 2)

            if (random.random() < CRASH_PROBABILITY or
                game_state["multiplier"] >= MAX_MULTIPLIER):
                crashed = True
            
            time.sleep(TICK_RATE)
            if crashed:
                break

        game_state["status"] = "crashed"
        final_crash_multiplier = game_state["multiplier"]
        if final_crash_multiplier > MAX_MULTIPLIER: 
            final_crash_multiplier = MAX_MULTIPLIER
        
        game_state["multiplier"] = round(final_crash_multiplier,2)

        print(f"CRASH em {game_state['multiplier']:.2f}x")
        
        game_state["history"].append(game_state["multiplier"])
        if len(game_state["history"]) > 20:
            game_state["history"].pop(0)
        
        print("--- Resultados da Rodada ---")
        for client_addr_key, player_round_data in list(game_state["players"].items()):
            player_ip_for_round = player_round_data.get("ip", "IP Desconhecido")
            player_name_for_round = get_player_name(player_ip_for_round)
            
            if player_round_data["cash_out"] is not None:
                print(f"Jogador '{player_name_for_round}' ({player_ip_for_round}) FEZ cash out em {player_round_data['cash_out']:.2f}x.")
            else:
                print(f"Jogador '{player_name_for_round}' ({player_ip_for_round}) NÃO FEZ cash out e perdeu {player_round_data['bet']:.2f}.")
        
        print(f"Saldos Finais da Rodada:")
        if player_data_store:
            for ip, data in player_data_store.items():
                print(f"  - IP: {ip}, Nome: {data.get('name', 'N/A')}, Saldo: {data.get('balance', 0):.2f}")
        else:
             print("  Nenhum jogador com saldo registrado.")
        print("----------------------------------")
        
        time.sleep(5)

threading.Thread(target=game_loop, daemon=True).start()
threading.Thread(target=broadcast_game_updates, daemon=True).start()

try:
    while True:
        client_socket, client_addr = tcp_socket.accept()
        threading.Thread(target=handle_tcp_client, args=(client_socket, client_addr), daemon=True).start()
except KeyboardInterrupt:
    print("Servidor encerrado pelo usuário.")
finally:
    tcp_socket.close()
    udp_socket.close()
    print("Saldos finais (em memória):")
    if player_data_store:
        for ip, data in player_data_store.items():
            print(f"  - IP: {ip}, Nome: {data.get('name', 'N/A')}, Saldo: {data.get('balance', 0):.2f}")
    else:
        print("  Nenhum jogador com dados para exibir.")