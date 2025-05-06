PONG MULTIPLAYER - CLIENTE E SERVIDOR EM PYTHON

Requisitos:
- Python 3.x
- pygame (pip install pygame)

Como usar:

1. Abra um terminal e execute o servidor:
   python server.py

2. Em dois computadores na mesma rede (ou duas janelas diferentes), execute:
   python client.py

3. Edite o IP no client.py para o IP da máquina que está rodando o servidor (linha 12):
   client.connect(("IP_DO_SERVIDOR", 3001))

Controles:
- Jogador 1: W / S
- Jogador 2: ↑ / ↓