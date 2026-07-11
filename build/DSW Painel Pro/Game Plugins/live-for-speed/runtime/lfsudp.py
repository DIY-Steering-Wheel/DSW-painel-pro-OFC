import socket
import struct


localIP = "127.0.0.1"
localPort = 46541
bufferSize = 256

UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPServerSocket.bind((localIP, localPort))
UDPServerSocket.setblocking(False)

UDPServerSocketM = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
UDPServerSocketM.bind((localIP, 46542))
UDPServerSocketM.setblocking(False)

carData = {}
_gauge_data = {}
_motion_data = {"x": 0.0, "y": 0.0, "z": 0.0}


def decodeFlag(flag):
    flagBin = f"{flag:03b}"[::-1]
    return {
        "showTurbo": bool(int(flagBin[2])),
        "showKM": not bool(int(flagBin[1])),
        "showBAR": not bool(int(flagBin[0])),
    }


def decodeLights(lightsAvailable, lightsActive):
    lightsActBin = f"{lightsActive:012b}"[::-1]
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
    return {light: bool(int(lightsActBin[i])) for i, light in enumerate(totalLights)}


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
        unpackedData = struct.unpack("I3sxH2B7f2I3f15sx15sx", gauge_packet)
        gear = unpackedData[3]
        gear = gear - 1 if gear >= 2 else (0 if gear == 1 else gear - 1)
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
            "fuel": unpackedData[9],
            "oilPressure": unpackedData[10],
            "oilTemp": unpackedData[11],
            "bico_de_luz": decodeLights(unpackedData[12], unpackedData[13]),
            "throttle": unpackedData[14],
            "brake": unpackedData[15],
            "clutch": unpackedData[16],
            "misc1": unpackedData[17],
            "misc2": unpackedData[18],
            "ElectricEnabled": unpackedData[8] > 1,
            "EngineEnabled": unpackedData[6] > 100,
        }

    motion_packet = _recv_latest(UDPServerSocketM, bufferSize)
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
