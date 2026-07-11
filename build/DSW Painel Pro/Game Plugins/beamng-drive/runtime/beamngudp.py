import socket
import struct


localIP = "127.0.0.1"
localPort = 4444
bufferSize = 256

UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPServerSocket.bind((localIP, localPort))
UDPServerSocket.setblocking(False)

UDPServerSocketM = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
UDPServerSocketM.bind((localIP, 4446))
UDPServerSocketM.setblocking(False)

carData = {}
_gauge_data = {}
_motion_data = {"x": 0.0, "y": 0.0, "z": 0.0}


def decodeFlag(flag):
    flagBin = bin(flag)[2:].zfill(32)
    return {
        "showTurbo": newBool(flagBin[-1]),
        "showKM": not newBool(flagBin[-2]),
        "showBAR": not newBool(flagBin[-3]),
    }


def newBool(string):
    return string == "1"


def decodeLights(lightsAvailable, lightsActive):
    lightsActBin = bin(lightsActive)[2:][::-1]
    lights = {}
    totalLights = [
        "shift_light",
        "full_beam",
        "handbrake",
        "pit_limiter",
        "tc",
        "left_turn",
        "right_turn",
        "both_turns",
        "oil_warn",
        "battery_warn",
        "abs",
        "spare_light",
    ]
    for i in range(0, 12):
        try:
            lights[totalLights[i]] = newBool(lightsActBin[i])
        except Exception:
            lights[totalLights[i]] = False
    return lights


def _recv_latest(sock, size):
    latest = None
    while True:
        try:
            payload, _addr = sock.recvfrom(size)
            latest = payload
        except BlockingIOError:
            break
        except OSError:
            break
    return latest


def readData():
    global carData, _gauge_data, _motion_data

    gauge_packet = _recv_latest(UDPServerSocket, bufferSize)
    if gauge_packet:
        expected_size = struct.calcsize("I4sHBBfffffffIIfff16s16sxxxx")
        if len(gauge_packet) == expected_size:
            unpackedData = struct.unpack("I4sHBBfffffffIIfff16s16sxxxx", gauge_packet)
            gear = unpackedData[3]
            if gear >= 2:
                gear = gear - 1
            elif gear == 1:
                gear = 0
            else:
                gear = gear - 1

            _gauge_data = {
                "time": unpackedData[0],
                "carName": unpackedData[1].decode("utf-8", errors="ignore"),
                "flags": decodeFlag(unpackedData[2]),
                "gear": gear,
                "PLID": unpackedData[4],
                "speed": unpackedData[5],
                "rpm": unpackedData[6],
                "turboPressure": unpackedData[7],
                "engTemp": unpackedData[8],
                "fuel": unpackedData[9] * 100,
                "oilPressure": unpackedData[10],
                "oilTemp": unpackedData[11],
                "bico_de_luz": decodeLights(unpackedData[12], unpackedData[13]),
                "throttle": unpackedData[14],
                "brake": unpackedData[15],
                "clutch": unpackedData[16],
                "misc1": unpackedData[17],
                "misc2": unpackedData[18],
                "ElectricEnabled": False if unpackedData[8] <= 1 else True,
                "EngineEnabled": False if unpackedData[6] <= 100 else True,
            }

    motion_packet = _recv_latest(UDPServerSocketM, 1024)
    if motion_packet and len(motion_packet) >= 64:
        outsim_pack = struct.unpack("I12f3i", motion_packet[:64])
        _motion_data = {
            "x": outsim_pack[9],
            "y": outsim_pack[10],
            "z": outsim_pack[11],
        }

    if _gauge_data:
        carData = dict(_gauge_data)
        carData.update(_motion_data)


def get():
    readData()
    return carData


def iniciada(ip="127.0.0.1", port=4444):
    global localIP, localPort
    localIP = ip
    localPort = port
