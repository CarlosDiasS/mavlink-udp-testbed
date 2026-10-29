import select
import socket

# Endereços locais
IP_LOCAL = "127.0.0.1"
ENDERECO_GCS = ("127.0.0.1", 14101)

# A GCS envia seus comandos para esta porta
# A GCS conhece essa porta apos a primeira msg, ao receber o heartbeat
PORTA_LOCAL_LADO_GCS = 14003

# O Segundo tunel(do lado do drone) envia telemetria para esta porta
PORTA_LOCAL_LADO_TUNEL_DRONE = 14200

# Um socket por porta de entrada
socket_lado_gcs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_lado_gcs.bind((IP_LOCAL, PORTA_LOCAL_LADO_GCS))

socket_lado_tunel_drone = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_lado_tunel_drone.bind((IP_LOCAL, PORTA_LOCAL_LADO_TUNEL_DRONE))

# seria a ttyUSB da xbee conectada ao computador
endereco_tunel_drone_aprendido = None

print(f"Entrada da GCS: {IP_LOCAL}:{PORTA_LOCAL_LADO_GCS}")
print(f"Entrada da telemetria SITL: {IP_LOCAL}:{PORTA_LOCAL_LADO_TUNEL_DRONE}")

while True:
    sockets_prontos, _, _ = select.select([socket_lado_gcs, socket_lado_tunel_drone], [], [])

    for sock in sockets_prontos:
        dados, origem = sock.recvfrom(65535) # tamanho maximo 

        if sock is socket_lado_tunel_drone:
            # O MAVProxy pode transmitir usando uma porta de origem dinâmica.
            endereco_tunel_drone_aprendido = origem
            socket_lado_gcs.sendto(dados, ENDERECO_GCS)
            print(f"SITL {origem} -> ENDERECO_GCS {ENDERECO_GCS} | {len(dados)} bytes")

        elif sock is socket_lado_gcs:
            if origem != ENDERECO_GCS:
                print(f"Origem GCS inesperada: {origem}")
                continue

            if endereco_tunel_drone_aprendido is None:
                print("Ainda não recebi telemetria do SITL.")
                continue

            socket_lado_tunel_drone.sendto(dados, endereco_tunel_drone_aprendido)
            print(f"GCS {origem} -> SITL {endereco_tunel_drone_aprendido} | {len(dados)} bytes")
