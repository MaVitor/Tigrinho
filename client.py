import socket
import threading
import json
import time
import sys

# Configurações do cliente
SERVER_HOST = '127.0.0.1' # Alterado para teste local
TCP_PORT = 5000
UDP_PORT = 5001

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

player_name = "JogadorAnônimo"
running_client = True # Flag para controlar o loop principal e a thread UDP

# Conectar ao servidor
try:
    print(f"Tentando conectar ao servidor {SERVER_HOST}:{TCP_PORT}...")
    tcp_socket.connect((SERVER_HOST, TCP_PORT))
    print(f"Conectado ao servidor {SERVER_HOST}:{TCP_PORT}")

    udp_socket.bind(('0.0.0.0', UDP_PORT))
    print(f"Escutando por atualizações UDP na porta {UDP_PORT}")

    while True:
        name_input = input("Digite seu nome para o jogo: ").strip()
        if name_input:
            player_name = name_input
            name_set_message = {"command": "set_name", "name": player_name}
            tcp_socket.send(json.dumps(name_set_message).encode('utf-8'))
            # Espera uma resposta simples para confirmação do nome
            response_name_raw = tcp_socket.recv(1024)
            if not response_name_raw: # Checa se a conexão foi fechada
                print("Conexão perdida ao definir nome.")
                running_client = False
                break
            response_name = json.loads(response_name_raw.decode('utf-8'))
            if response_name.get("status") == "name_set_ok":
                print(f"Nome '{player_name}' registrado no servidor.")
            else:
                print(f"Servidor respondeu sobre o nome: {response_name.get('message', 'Status desconhecido')}")
            break # Sai do loop de pedir nome
        else:
            print("Nome não pode ser vazio. Tente novamente.")
    
    if not running_client: # Se a conexão foi perdida durante o set_name
        sys.exit(1)

except Exception as e:
    print(f"Erro ao conectar ou configurar nome: {e}")
    running_client = False # Garante que não prossiga se a conexão falhar
    sys.exit(1)

# Variáveis de estado do cliente
current_multiplier = 1.0
game_status = "waiting"
has_active_bet = False
bet_amount = 0
client_balance = 0.0
last_known_server_game_status = "waiting" # Importante para transições de estado

# Função para receber atualizações UDP
def receive_udp_updates():
    global current_multiplier, game_status, has_active_bet, bet_amount, last_known_server_game_status, running_client

    while running_client: # USA A FLAG running_client
        try:
            data, _ = udp_socket.recvfrom(1024)
            if not running_client: break # Checa novamente após o bloqueio

            update = json.loads(data.decode('utf-8'))

            current_multiplier = update.get("multiplier", current_multiplier)
            new_server_status = update.get("status", game_status)

            # Lógica de transição de estado e impressão
            if new_server_status == "crashed" and last_known_server_game_status != "crashed":
                display_name_info = f" ({player_name})" if player_name != "JogadorAnônimo" else ""
                # Limpa a linha do multiplicador antes de imprimir CRASH
                sys.stdout.write("\r" + " " * 70 + "\r") 
                if has_active_bet:
                    print(f"CRASH em {current_multiplier:.2f}x! Você{display_name_info} não sacou a tempo.")
                else:
                    print(f"CRASH em {current_multiplier:.2f}x!")
                has_active_bet = False
                bet_amount = 0
            elif new_server_status == "waiting" and last_known_server_game_status != "waiting":
                # Limpa a linha antes de "Nova rodada" se o estado anterior era "crashed" ou "running"
                if last_known_server_game_status != "waiting": # Evita printar toda vez se já estiver em waiting
                    sys.stdout.write("\r" + " " * 70 + "\r") 
                    print("Nova rodada começando. Faça sua aposta!")
                has_active_bet = False
                bet_amount = 0

            # Atualiza os status globais do cliente
            game_status = new_server_status
            last_known_server_game_status = new_server_status

            # Exibe o multiplicador atual somente se estiver 'running'
            if game_status == "running":
                sys.stdout.write(f"\rMultiplicador atual: {current_multiplier:.2f}x  ")
                sys.stdout.flush()
            
        except json.JSONDecodeError:
            # Em geral, é melhor não imprimir nada para erros de pacotes UDP malformados
            # para não poluir o console do usuário.
            pass
        except OSError: # Ocorre se o socket UDP for fechado enquanto recvfrom está bloqueando
             if running_client: # Só loga se não for um encerramento esperado
                print(f"\nSocket UDP fechado ou erro de rede na thread UDP.")
             break # Sai do loop da thread
        except Exception as e:
            if running_client: # Só loga se não for um encerramento esperado
                print(f"\nErro inesperado na thread UDP: {e}")
            # Considerar se deve sair do loop ou não dependendo do erro
            pass


# Função para enviar comandos TCP e atualizar saldo
def send_tcp_command(command, **kwargs):
    global client_balance, running_client
    if not running_client: # Não tenta enviar se o cliente já está encerrando
        return {"status": "error", "message": "Cliente encerrando"}

    message = {"command": command, **kwargs}
    try:
        tcp_socket.sendall(json.dumps(message).encode('utf-8')) # Usar sendall para garantir envio completo
        response_data = tcp_socket.recv(1024)
        if not response_data:
            print("\nServidor não enviou resposta (conexão pode ter sido fechada).")
            running_client = False
            return {"status": "error", "message": "Sem resposta do servidor"}
        response = json.loads(response_data.decode('utf-8'))

        if "balance" in response:
            client_balance = float(response["balance"])
        return response
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
        print(f"\nErro de conexão TCP: {e}. O servidor pode ter sido encerrado ou a rede falhou.")
        running_client = False
        return {"status": "error", "message": f"Conexão perdida: {e}"}
    except json.JSONDecodeError:
        print("\nErro ao decodificar resposta do servidor (JSON inválido).")
        return {"status": "error", "message": "Resposta inválida do servidor"}
    except Exception as e:
        print(f"\nErro ao enviar/receber comando TCP: {e}")
        # running_client = False # Pode ser muito agressivo para qualquer exceção
        return {"status": "error", "message": f"Erro TCP desconhecido: {e}"}

# Função para exibir o menu
def show_menu():
    # Limpa a linha do multiplicador apenas se o jogo não estiver 'running'
    if game_status != "running":
        sys.stdout.write("\r" + " " * 80 + "\r") 
    else: # Se estiver running, o multiplicador já está lá, só precisamos de uma nova linha para o menu
        sys.stdout.write("\n")
    sys.stdout.flush()

    print(f"===== JOGO CRASH (Jogador: {player_name}, Saldo: R${client_balance:.2f}) =====")
    print("1. Fazer aposta")
    print("2. Cash out")
    print("3. Ver status do jogo e Saldo")
    print("4. Ver Ranking dos Melhores Jogadores")
    print("5. Sair")
    return input("Escolha uma opção: ")

# Solicita o status inicial para obter o saldo
if running_client:
    print("Obtendo saldo inicial do servidor...")
    initial_status_response = send_tcp_command("status")
    if initial_status_response and "balance" in initial_status_response:
        client_balance = float(initial_status_response["balance"])
        if "player_name" in initial_status_response and initial_status_response["player_name"] != player_name and not initial_status_response["player_name"].startswith(DEFAULT_PLAYER_NAME):
            player_name = initial_status_response["player_name"] # Atualiza nome se servidor tiver um melhor
            print(f"Nome '{player_name}' e saldo inicial R${client_balance:.2f} carregados.")
        else:
            print(f"Saldo inicial R${client_balance:.2f} carregado para '{player_name}'.")
    else:
        if running_client: # Só imprime se o cliente ainda deveria estar rodando
            print(f"Não foi possível obter o saldo inicial do servidor. Resposta: {initial_status_response}")


# Inicia a thread para receber atualizações UDP
if running_client:
    udp_thread = threading.Thread(target=receive_udp_updates, daemon=True)
    udp_thread.start()
else: # Se a conexão inicial ou o set_name falhou, não inicia a thread UDP
    udp_thread = None # Garante que a variável exista para o finally block

# Loop principal do cliente
try:
    while running_client:
        try:
            choice = show_menu()
        except EOFError:
            print("\nEntrada finalizada, saindo...")
            running_client = False
            break

        if not running_client: break

        if choice == "1": # Fazer Aposta
            if game_status == "waiting":
                if has_active_bet:
                     print("Você já tem uma aposta ativa para esta rodada.")
                     continue
                try:
                    amount_str = input(f"Seu saldo atual: R${client_balance:.2f}. Valor da aposta: ")
                    amount = float(amount_str)
                    if amount <= 0:
                        print("O valor da aposta deve ser positivo.")
                        continue

                    response = send_tcp_command("bet", amount=amount)
                    if not running_client: break 

                    if response and response.get("status") == "bet_accepted":
                        print(f"Aposta de R${response.get('amount', amount):.2f} aceita! Novo saldo: R${client_balance:.2f}")
                        has_active_bet = True
                        bet_amount = amount
                    else:
                        msg = (response.get('message', 'Aposta não aceita') if response else "Sem resposta do servidor")
                        print(f"Erro ao apostar: {msg}")
                except ValueError:
                    print("Por favor, insira um valor numérico válido.")
                except Exception as e:
                    print(f"Ocorreu um erro ao tentar apostar: {e}")
            else:
                print(f"Não é possível apostar agora (status do jogo: '{game_status}'). Aguarde a fase 'waiting'.")

        elif choice == "2": # Cash Out
            if game_status == "running" and has_active_bet:
                response = send_tcp_command("cash_out")
                if not running_client: break

                if response and response.get("status") == "cash_out_success":
                    # Limpa a linha do multiplicador antes de imprimir sucesso
                    sys.stdout.write("\r" + " " * 70 + "\r") 
                    print(f"Cash out realizado com sucesso em {response['multiplier']:.2f}x!")
                    print(f"Você ganhou R${response['winnings']:.2f}! Novo saldo: R${client_balance:.2f}")
                    has_active_bet = False 
                else:
                    msg = (response.get('message', 'Cash out falhou') if response else "Sem resposta do servidor")
                    print(f"Erro no cash out: {msg}")
            else:
                print(f"Não é possível fazer cash out agora (status: '{game_status}', aposta ativa: {has_active_bet}).")

        elif choice == "3": # Ver Status
            response = send_tcp_command("status")
            if not running_client: break

            if response and response.get("status") == "game_status":
                sys.stdout.write("\r" + " " * 70 + "\r") 
                print(f"\n--- Status do Jogo ---")
                print(f"Status no servidor: {response['game_status']}")
                print(f"Multiplicador no servidor: {response['multiplier']:.2f}x")
                print(f"Seu saldo (Jogador: {player_name}): R${client_balance:.2f}")
                if "player_name" in response and response["player_name"] != player_name :
                     player_name = response["player_name"] # Atualiza nome se o servidor tiver um diferente

                if response.get("history"):
                    print("Histórico recente de crashes:")
                    for mult_val in response["history"]:
                        print(f"  {mult_val:.2f}x")
            else:
                msg = (response.get('message', 'Falha ao obter status') if response else "Sem resposta do servidor")
                print(f"Erro ao obter status do jogo: {msg}")
        
        elif choice == "4": # Ver Ranking
            response = send_tcp_command("get_ranking")
            if not running_client: break

            if response and response.get("status") == "ranking_data":
                ranking = response.get("ranking", [])
                sys.stdout.write("\r" + " " * 70 + "\r") 
                print("\n--- RANKING DOS MELHORES JOGADORES ---")
                if ranking:
                    for i, player_entry in enumerate(ranking):
                        print(f"{i+1}. {player_entry.get('name', 'N/A')} - R${player_entry.get('balance', 0):.2f}")
                else:
                    print("Nenhum jogador no ranking ainda ou ranking vazio.")
            else:
                msg = (response.get('message', 'Falha ao buscar ranking') if response else "Sem resposta do servidor")
                print(f"Erro ao obter ranking: {msg}")

        elif choice == "5": # Sair
            print("Saindo do jogo...")
            running_client = False
            break
            
        else:
            print("Opção inválida. Tente novamente.")

        if running_client:
            time.sleep(0.1)

except KeyboardInterrupt:
    print("\nPrograma encerrado pelo usuário.")
    running_client = False
except ConnectionRefusedError:
    print(f"\nErro: Não foi possível conectar ao servidor em {SERVER_HOST}:{TCP_PORT}. Verifique se o servidor está online.")
    running_client = False
except Exception as e:
    print(f"\nOcorreu um erro fatal no cliente: {e}")
    running_client = False
finally:
    print("Encerrando cliente...")
    running_client = False 

    if udp_socket: # Fecha o socket UDP primeiro
        udp_socket.close() 
    
    if tcp_socket: # Tenta fechar o socket TCP
        try:
            # Tenta um shutdown mais gracioso, mas pode falhar se já desconectado
            tcp_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass 
        tcp_socket.close()
    
    # Espera um pouco pela thread UDP, que deve sair por causa do running_client = False e OSError no recvfrom
    if udp_thread and udp_thread.is_alive():
        print("Aguardando thread UDP finalizar...")
        udp_thread.join(timeout=0.5) # Espera no máximo 0.5 segundo
        if udp_thread.is_alive():
            print("Thread UDP não finalizou a tempo (normal se o socket já foi fechado).")

    print("Cliente encerrado.")