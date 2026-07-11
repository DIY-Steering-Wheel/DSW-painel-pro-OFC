import socket
import struct


localIP = "127.0.0.1"
localPort = 46541
bufferSize = 256

UDPServerSocket = None
UDPServerSocketM = None

carData = {}
_gauge_data = {}
_motion_data = {"x": 0.0, "y": 0.0, "z": 0.0}


def decodeFlag(flag):
    flagBin = bin(flag)[2:].zfill(32)
    return {
        "showTurbo": flagBin[-14] == "1",
        "showKM": flagBin[-15] == "1",
        "showBAR": flagBin[-16] == "1",
    }


def decodeLights(lightsAvailable, lightsActive):
    lightsActBin = bin(lightsActive)[2:][::-1]
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
        "sidelights",
        "low_fuel",
        "rear_fog",
        "fog",
        "dipped_headlight",
        "engine_damage",
    ]
    lights = {}
    for index, light in enumerate(totalLights):
        lights[light] = index < len(lightsActBin) and lightsActBin[index] == "1"
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


def _build_socket(ip, port):
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
    sock.bind((ip, port))
    sock.setblocking(False)
    return sock


def _ensure_sockets():
    global UDPServerSocket, UDPServerSocketM

    if UDPServerSocket is None:
        UDPServerSocket = _build_socket(localIP, localPort)
    if UDPServerSocketM is None:
        UDPServerSocketM = _build_socket(localIP, 46542)


def shutdown():
    global UDPServerSocket, UDPServerSocketM

    for name in ("UDPServerSocket", "UDPServerSocketM"):
        sock = globals().get(name)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
            globals()[name] = None


def readData():
    global carData, _gauge_data, _motion_data
    _ensure_sockets()

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
            "fuel": unpackedData[9] * 100,
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
            "x": outsim_pack[7],
            "y": outsim_pack[8],
            "z": outsim_pack[9],
        }

    if _gauge_data:
        carData = dict(_gauge_data)
        carData.update(_motion_data)


def get():
    readData()
    return carData


def iniciada(ip="127.0.0.1", port=4444):
    global localIP, localPort
    if ip != localIP or port != localPort:
        shutdown()
    localIP = ip
    localPort = port
