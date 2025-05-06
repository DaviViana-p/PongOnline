import socket
import pygame
import pickle
import threading
import time

WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PADDLE_WIDTH, PADDLE_HEIGHT = 10, 100
BALL_SIZE = 15

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pong Network")

font = pygame.font.SysFont(None, 48)
clock = pygame.time.Clock()

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 3001))  # Altere para o IP do servidor

state = "menu"  # menu, searching, ready, countdown, playing, finished
game_state = {}
partner_ready = False
countdown = 3
result = None  # Resultado do jogo: "win" ou "lose"

def receive_data():
    global state, game_state, partner_ready, countdown, result
    while True:
        try:
            data = client.recv(4096)
            msg = pickle.loads(data)
            print("[DEBUG - Cliente] Mensagem recebida:", msg)

            if isinstance(msg, dict) and "state" in msg:
                state = msg["state"]
                partner_ready = msg.get("partner_ready", False)
                countdown = msg.get("countdown", 3)
                print(f"[DEBUG - Cliente] Estado: {state}, adversário pronto: {partner_ready}, countdown: {countdown}")

                if state == "finished":
                    # aqui você captura o resultado enviado pelo servidor
                    result = msg.get("result")
                    print(f"[DEBUG - Cliente] RESULT recebido: {result}")

                elif state == "playing":
                    # durante o jogo, o servidor manda game_state dentro do dict
                    game_state.update(msg.get("game_state", {}))

            elif isinstance(msg, dict):
                # caso o servidor envie só o game_state puro
                game_state = msg

        except Exception as e:
            print("[ERRO - Cliente] Falha ao receber dados:", e)
            break


threading.Thread(target=receive_data, daemon=True).start()

def send(msg):
    client.send(pickle.dumps(msg))

def draw_button(text, rect, hover=False):
    color = (70, 130, 180) if hover else (100, 100, 100)
    pygame.draw.rect(screen, color, rect)
    txt = font.render(text, True, WHITE)
    screen.blit(txt, (rect.x + 20, rect.y + 10))

button_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 40, 200, 60)

running = True
while running:
    screen.fill(BLACK)
    mx, my = pygame.mouse.get_pos()
    click = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            click = True
        if event.type == pygame.KEYDOWN and state == "playing":
            if event.key in [pygame.K_w, pygame.K_UP]:
                send("UP")
            elif event.key in [pygame.K_s, pygame.K_DOWN]:
                send("DOWN")
        if event.type == pygame.KEYUP and state == "playing":
            send("STOP")

    if state == "menu":
        hover = button_rect.collidepoint((mx, my))
        draw_button("Iniciar", button_rect, hover)
        if hover and click:
            send({"action": "search"})
            state = "searching"

    elif state == "searching":
        text = font.render("Procurando jogador...", True, WHITE)
        screen.blit(text, (WIDTH // 2 - 180, HEIGHT // 2))

    elif state == "ready":
        hover = button_rect.collidepoint((mx, my))
        draw_button("Pronto", button_rect, hover)
        if hover and click:
            send({"action": "ready"})

        if partner_ready:
            txt = font.render("Oponente pronto!", True, WHITE)
            screen.blit(txt, (WIDTH // 2 - 120, HEIGHT // 2 + 80))

    elif state == "countdown":
        txt = font.render(f"Iniciando em {countdown}", True, WHITE)
        screen.blit(txt, (WIDTH // 2 - 120, HEIGHT // 2))

    elif state == "playing":
        if game_state:
            pygame.draw.rect(screen, WHITE, (10, game_state["paddle1_y"], PADDLE_WIDTH, PADDLE_HEIGHT))
            pygame.draw.rect(screen, WHITE, (WIDTH - 20, game_state["paddle2_y"], PADDLE_WIDTH, PADDLE_HEIGHT))
            pygame.draw.ellipse(screen, WHITE, (game_state["ball_x"], game_state["ball_y"], BALL_SIZE, BALL_SIZE))
            s1 = font.render(str(game_state["score1"]), True, WHITE)
            s2 = font.render(str(game_state["score2"]), True, WHITE)
            screen.blit(s1, (WIDTH // 4, 20))
            screen.blit(s2, (WIDTH * 3 // 4, 20))

    elif state == "finished":
        # Renderiza o texto
        if result == "win":
            mensagem = "Você venceu!"
        elif result == "lose":
            mensagem = "Você perdeu!"
        else:
            mensagem = "Fim de jogo!"
        txt = font.render(mensagem, True, WHITE)
        # Centraliza horizontalmente e mantém no topo (por exemplo y = 20px)
        text_x = WIDTH // 2 - txt.get_width() // 2
        text_y = 20
        screen.blit(txt, (text_x, text_y))

        # Posiciona o botão no centro da tela
        button_rect.center = (WIDTH // 2, HEIGHT // 2)
        hover = button_rect.collidepoint((mx, my))
        draw_button("Voltar ao Menu", button_rect, hover)
        if hover and click:
            state = "menu"
            game_state = {}
            result = None
            send({"action": "reset"})
    print("[DEBUG - Cliente] estado:", state)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
