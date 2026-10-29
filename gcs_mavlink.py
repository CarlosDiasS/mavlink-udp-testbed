
import math
import time

from pymavlink import mavutil

# ==================================================
# 1. CONEXÃO
# ==================================================

PORTA_DRONE_SOCKET = 14101

# abre um socket udp na 14101, onde ira receber(udpin) 
# as respostas(mavlink) da "controladora"
conexao = mavutil.mavlink_connection(
    f"udpin:0.0.0.0:{PORTA_DRONE_SOCKET}",
    source_system=255,
    source_component=190
)

print("Aguardando HEARTBEAT do SITL...")

"""
 sentido de envio
 script <-- controladora 
 passivo, apenas aguarda
 qnd recebe, vincula (implicitamente) a porta para futuros envios
"""
conexao.wait_heartbeat()

print("Conectado!")
print(f"Sistema: {conexao.target_system}")
print(f"Componente: {conexao.target_component}")


# ==================================================
# 2. SOLICITAR TELEMETRIA
# ==================================================

def solicitar_telemetria():

    # Mensagens MAVLink que queremos receber
    mensagens = [
        mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
        mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
        mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD,
        mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS
    ]

    # Solicitar uma mensagem por segundo de cada tipo
    intervalo_us = 1_000_000

    for mensagem_id in mensagens:

        conexao.mav.command_long_send(
            conexao.target_system,
            conexao.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            mensagem_id,
            intervalo_us,
            0, 0, 0, 0, 0
        )

        print(f"Telemetria solicitada: ID {mensagem_id}")


# ==================================================
# 3. RECEBER E IMPRIMIR TELEMETRIA
# ==================================================

def imprimir_telemetria():

    tipos = [
        "ATTITUDE",
        "GLOBAL_POSITION_INT",
        "VFR_HUD",
        "SYS_STATUS" #apenas esses 4
    ]

    # Armazena uma mensagem de cada tipo
    dados = {}

    while len(dados) < len(tipos):

        mensagem = conexao.recv_match(
            type=tipos,
            blocking=True,
            timeout=5
        )

        if mensagem is None:
            print("Timeout aguardando telemetria.")
            return False

        tipo = mensagem.get_type()

        dados[tipo] = mensagem

    # Todas as quatro mensagens foram recebidas
    atitude = dados["ATTITUDE"]
    posicao = dados["GLOBAL_POSITION_INT"]
    voo = dados["VFR_HUD"]
    bateria = dados["SYS_STATUS"]

    print("\n----- TELEMETRIA -----")

    print(f"Latitude: {posicao.lat / 1e7:.7f}")
    print(f"Longitude: {posicao.lon / 1e7:.7f}")

    print(
        f"Altitude relativa: "
        f"{posicao.relative_alt / 1000:.2f} m"
    )

    print(f"Roll: {math.degrees(atitude.roll):.2f}°")
    print(f"Pitch: {math.degrees(atitude.pitch):.2f}°")
    print(f"Yaw: {math.degrees(atitude.yaw):.2f}°")

    print(f"Velocidade: {voo.groundspeed:.2f} m/s")

    print(
        f"Bateria: "
        f"{bateria.voltage_battery / 1000:.2f} V"
    )

    print("----------------------")

    return True


# ==================================================
# 4. ALTERAR MODO DE VOO PARA GUIDED
# ==================================================

def mudar_para_guided():

    modos = conexao.mode_mapping() or {}

    if "GUIDED" not in modos:
        print("Modo GUIDED não disponível.")
        return False

    id_guided = modos["GUIDED"]

    print("\nEnviando comando para GUIDED...")

    conexao.mav.command_long_send(
        conexao.target_system,
        conexao.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        id_guided,
        0, 0, 0, 0, 0
    )

    # Aguardar confirmação pelo HEARTBEAT
    limite = time.monotonic() + 10

    while time.monotonic() < limite:

        mensagem = conexao.recv_match(
            type="HEARTBEAT",
            blocking=True,
            timeout=1
        )

        if mensagem is None:
            continue

        modo_atual = mavutil.mode_string_v10(mensagem)

        print(f"Modo atual: {modo_atual}")

        if modo_atual == "GUIDED":
            print("Modo GUIDED confirmado!")
            return True

    print("Não foi possível confirmar o modo GUIDED.")
    return False


# ==================================================
# 5. EXECUÇÃO DO TESTE
# ==================================================

try:

    solicitar_telemetria()

    # Primeiras 5 amostras de telemetria
    print("\n========== ANTES DO GUIDED ==========")

    for i in range(5):

        print(f"\nIteração {i + 1}/5")

        if not imprimir_telemetria():
            raise RuntimeError("Falha na recepção de telemetria.")

    # Alterar modo de voo
    print("\n========== MUDANÇA DE MODO ==========")

    if not mudar_para_guided():
        raise RuntimeError("Falha ao confirmar GUIDED.")

    # Mais 5 amostras de telemetria
    print("\n========== DEPOIS DO GUIDED ==========")

    for i in range(5):

        print(f"\nIteração {i + 1}/5")

        if not imprimir_telemetria():
            raise RuntimeError("Falha na recepção de telemetria.")

    print("\nTeste concluído!")

finally:
    conexao.close()
