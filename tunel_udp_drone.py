import select
import socket

# Endereços locais
IP_LOCAL = "127.0.0.1"
ENDERECO_TUNEL_ESTACAO = ("127.0.0.1", 14200)

# A GCS envia seus comandos para esta porta
# essa porta que a udp_Station ira descobrir com recvFrom
PORTA_LOCAL_COMUNICA_COM_TUNEL_ESTACAO = 14100

# O tunel_drone abre essa porta,
# que ira receber mensagens da controladora/sitl 
# --out=14550 e a porta default do sitl
PORTA_LOCAL_COMUNICA_COM_SITL = 14550 

# Um socket por porta de entrada
socket_lado_tunel_estacao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_lado_tunel_estacao.bind((IP_LOCAL, PORTA_LOCAL_COMUNICA_COM_TUNEL_ESTACAO))

socket_lado_sitl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_lado_sitl.bind((IP_LOCAL, PORTA_LOCAL_COMUNICA_COM_SITL))

endereco_sitl_aprendido = None

print(f"Entrada da GCS: {IP_LOCAL}:{PORTA_LOCAL_COMUNICA_COM_TUNEL_ESTACAO}")
print(f"Entrada da telemetria SITL: {IP_LOCAL}:{PORTA_LOCAL_COMUNICA_COM_SITL}")

while True:
    sockets_prontos, _, _ = select.select([socket_lado_tunel_estacao, socket_lado_sitl], [], [])

    for sock in sockets_prontos:
        dados, origem = sock.recvfrom(65535) # tamanho maximo udp

        if sock is socket_lado_sitl:
            # O MAVProxy pode transmitir usando uma porta de origem dinâmica.
            endereco_sitl_aprendido = origem
            socket_lado_tunel_estacao.sendto(dados, ENDERECO_TUNEL_ESTACAO)
            print(f"SITL {origem} -> ENDERECO_TUNEL_ESTACAO {ENDERECO_TUNEL_ESTACAO} | {len(dados)} bytes")

        elif sock is socket_lado_tunel_estacao:
            if origem != ENDERECO_TUNEL_ESTACAO:
                print(f"Origem GCS inesperada: {origem}")
                continue

            if endereco_sitl_aprendido is None:
                print("Ainda não recebi telemetria do SITL.")
                continue

            socket_lado_sitl.sendto(dados, endereco_sitl_aprendido)
            print(f"GCS {origem} -> SITL {endereco_sitl_aprendido} | {len(dados)} bytes")
