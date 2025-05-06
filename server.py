import socket
import threading
import pickle
import time

WIDTH, HEIGHT = 800, 600
PADDLE_HEIGHT = 100
BALL_SIZE = 15
FPS = 60
WIN_SCORE = 10

sessions = {}            # session_id -> sessão
next_session_id = 0
lock = threading.Lock()

def novo_game_state():
    return {
        "paddle1_y": HEIGHT // 2 - PADDLE_HEIGHT // 2,
        "paddle2_y": HEIGHT // 2 - PADDLE_HEIGHT // 2,
        "ball_x": WIDTH // 2,
        "ball_y": HEIGHT // 2,
        "ball_dx": 5,
        "ball_dy": 5,
        "score1": 0,
        "score2": 0
    }

def assign_to_session(conn):
    """
    Entra em uma sessão já em 'searching' ou cria uma nova.
    Retorna (session_id, player_id).
    """
    global next_session_id
    with lock:
        # tenta emparelhar
        for sid, sess in sessions.items():
            if len(sess["clients"]) == 1 and sess["states"][0] == "searching":
                sess["clients"].append(conn)
                sess["states"][1] = "searching"
                sess["ready_flags"][1] = False
                return sid, 1

        # cria nova sessão
        sid = next_session_id
        next_session_id += 1
        sessions[sid] = {
            "clients": [conn],
            "states": {0: "searching"},
            "ready_flags": {0: False},
            "game_state": novo_game_state(),
            "inputs": [0, 0],
            "countdown": 3,
            "game_started": False
        }
        return sid, 0

def broadcast_states(session_id):
    sess = sessions.get(session_id)
    if not sess: return
    for i, c in enumerate(sess["clients"]):
        if c:
            try:
                c.sendall(pickle.dumps({
                    "state": sess["states"][i],
                    "partner_ready": sess["ready_flags"].get(1 - i, False),
                    "countdown": sess["countdown"]
                }))
            except:
                pass

def handle_client(conn, addr):
    print(f"[DEBUG] Conexão de {addr}")
    session_id = player_id = None

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = pickle.loads(data)

            # RESET: sai da sessão atual para voltar ao menu
            if isinstance(msg, dict) and msg.get("action") == "reset":
                print(f"[DEBUG] Cliente {addr} pediu RESET")
                session_id = player_id = None
                continue

            # SEARCH: só aqui entramos/criamos sessão
            if isinstance(msg, dict) and msg.get("action") == "search":
                if session_id is None:
                    session_id, player_id = assign_to_session(conn)
                    print(f"[DEBUG] Cliente {addr} entrou na sessão {session_id} como player {player_id}")
                    # iniciar loop de jogo quando tiver 2 jogadores
                    if len(sessions[session_id]["clients"]) == 2:
                        threading.Thread(target=game_loop, args=(session_id,), daemon=True).start()
                broadcast_states(session_id)
                continue

            # se ainda não entrou em sessão, ignora tudo
            if session_id is None:
                continue

            # READY
            if isinstance(msg, dict) and msg.get("action") == "ready":
                sessions[session_id]["ready_flags"][player_id] = True
                print(f"[DEBUG] Player {player_id} READY na sessão {session_id}")
                continue

            # MOVEMENT
            if isinstance(msg, str):
                delta = {"UP": -1, "DOWN": 1, "STOP": 0}.get(msg, 0)
                sessions[session_id]["inputs"][player_id] = delta

    except Exception as e:
        print(f"[ERRO] handle_client {addr}: {e}")
    finally:
        conn.close()
        if session_id is not None:
            sess = sessions.get(session_id)
            if sess:
                sess["clients"][player_id] = None
                sess["states"][player_id] = "disconnected"
                sess["ready_flags"][player_id] = False
                if all(c is None for c in sess["clients"]):
                    del sessions[session_id]
        print(f"[DEBUG] Conexão com {addr} encerrada")

def game_loop(session_id):
    sess = sessions.get(session_id)
    if not sess:
        return

    # aguarda os dois clientes
    while len(sess["clients"]) < 2 or any(c is None for c in sess["clients"]):
        time.sleep(0.5)
        sess = sessions.get(session_id)
        if not sess:
            return  # sessão removida

    # loop principal
    while True:
        sess = sessions.get(session_id)
        if not sess:
            return

        # searching → ready
        if sess["states"][0] == "searching" and sess["states"][1] == "searching":
            sess["states"][0] = sess["states"][1] = "ready"
            sess["ready_flags"][0] = sess["ready_flags"][1] = False
            broadcast_states(session_id)
            print(f"[DEBUG] Sessão {session_id} agora em READY")

        # ready → countdown → playing
        if sess["states"][0] == "ready" and sess["states"][1] == "ready":
            if sess["ready_flags"][0] and sess["ready_flags"][1]:
                for i in (3, 2, 1):
                    sess["countdown"] = i
                    sess["states"][0] = sess["states"][1] = "countdown"
                    broadcast(session_id, {"state": "countdown", "countdown": i})
                    time.sleep(1)
                sess["states"][0] = sess["states"][1] = "playing"
                sess["game_started"] = True
                broadcast(session_id, {"state": "playing", "game_state": sess["game_state"]})
                print(f"[DEBUG] Sessão {session_id} INICIOU JOGO")

        # jogando
        if sess["game_started"]:
            update_game(session_id)
            gs = sess["game_state"]
            if gs["score1"] >= WIN_SCORE or gs["score2"] >= WIN_SCORE:
                winner = 0 if gs["score1"] >= WIN_SCORE else 1
                # envia resultado individual a cada cliente
                for pid, conn in enumerate(sess["clients"]):
                    try:
                        res = "win" if pid == winner else "lose"
                        conn.sendall(pickle.dumps({
                            "state": "finished",
                            "result": res
                        }))
                    except:
                        pass
                # remove sessão ao terminar
                with lock:
                    sessions.pop(session_id, None)
                print(f"[DEBUG] Sessão {session_id} finalizada e removida")
                return
            broadcast(session_id, gs)
        else:
            broadcast_states(session_id)

        time.sleep(1 / FPS)

def update_game(session_id):
    sess = sessions.get(session_id)
    if not sess:
        return
    gs = sess["game_state"]
    # paddles
    if sess["inputs"][0] == -1 and gs["paddle1_y"] > 0:  gs["paddle1_y"] -= 7
    if sess["inputs"][0] == 1 and gs["paddle1_y"] < HEIGHT - PADDLE_HEIGHT: gs["paddle1_y"] += 7
    if sess["inputs"][1] == -1 and gs["paddle2_y"] > 0:  gs["paddle2_y"] -= 7
    if sess["inputs"][1] == 1 and gs["paddle2_y"] < HEIGHT - PADDLE_HEIGHT: gs["paddle2_y"] += 7

    # bola
    gs["ball_x"] += gs["ball_dx"]
    gs["ball_y"] += gs["ball_dy"]

    # topo/fundo
    if gs["ball_y"] <= 0 or gs["ball_y"] >= HEIGHT - BALL_SIZE:
        gs["ball_dy"] *= -1

    # colisão com raquetes
    if gs["ball_x"] <= BALL_SIZE and gs["paddle1_y"] <= gs["ball_y"] <= gs["paddle1_y"] + PADDLE_HEIGHT:
        gs["ball_dx"] *= -1
    if gs["ball_x"] >= WIDTH - BALL_SIZE and gs["paddle2_y"] <= gs["ball_y"] <= gs["paddle2_y"] + PADDLE_HEIGHT:
        gs["ball_dx"] *= -1

    # pontuação
    if gs["ball_x"] <= 0:
        gs["score2"] += 1
        reset_ball(session_id)
    elif gs["ball_x"] >= WIDTH:
        gs["score1"] += 1
        reset_ball(session_id)

def reset_ball(session_id):
    game = sessions.get(session_id, {}).get("game_state")
    if not game:
        return
    game["ball_x"] = WIDTH // 2
    game["ball_y"] = HEIGHT // 2
    game["ball_dx"] *= -1

def broadcast(session_id, data):
    sess = sessions.get(session_id)
    if not sess:
        return
    for c in sess["clients"]:
        try:
            c.sendall(pickle.dumps(data))
        except:
            pass

# servidor principal
server = socket.socket()
server.bind(('', 3001))
server.listen()
print("Servidor ouvindo na porta 3001…")
while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
