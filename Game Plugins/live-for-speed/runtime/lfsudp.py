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

OUTGAUGE_BASE_FORMAT = "<I4sHBB7fIIfff16s16s"
OUTGAUGE_WITH_ID_FORMAT = "<I4sHBB7fIIfff16s16si"
OUTSIM_LEGACY_FORMAT = "I12f3i"
OUTSIM2_MAIN_FORMAT = "12f3i"
OUTSIM2_PREFIX_FORMAT = "4sii"


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
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
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
        parsed_gauge = _parse_outgauge_packet(gauge_packet)
        if parsed_gauge is not None:
            _gauge_data = parsed_gauge

    motion_packet = _recv_latest(UDPServerSocketM, bufferSize)
    if motion_packet:
        parsed_motion = _parse_outsim_packet(motion_packet)
        if parsed_motion is not None:
            _motion_data = parsed_motion

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


def _parse_outsim_packet(packet):
    if len(packet) >= struct.calcsize(OUTSIM2_PREFIX_FORMAT) + struct.calcsize(OUTSIM2_MAIN_FORMAT) and packet[:4] == b"LFST":
        prefix_size = struct.calcsize(OUTSIM2_PREFIX_FORMAT)
        main_values = struct.unpack(OUTSIM2_MAIN_FORMAT, packet[prefix_size:prefix_size + struct.calcsize(OUTSIM2_MAIN_FORMAT)])
        return {
            "x": main_values[6],
            "y": main_values[7],
            "z": main_values[8],
        }

    if len(packet) >= struct.calcsize(OUTSIM_LEGACY_FORMAT):
        outsim_pack = struct.unpack(OUTSIM_LEGACY_FORMAT, packet[:struct.calcsize(OUTSIM_LEGACY_FORMAT)])
        return {
            "x": outsim_pack[7],
            "y": outsim_pack[8],
            "z": outsim_pack[9],
        }

    return None


def _parse_outgauge_packet(packet):
    if len(packet) >= struct.calcsize(OUTGAUGE_WITH_ID_FORMAT):
        unpacked = struct.unpack(OUTGAUGE_WITH_ID_FORMAT, packet[:struct.calcsize(OUTGAUGE_WITH_ID_FORMAT)])
    elif len(packet) >= struct.calcsize(OUTGAUGE_BASE_FORMAT):
        unpacked = struct.unpack(OUTGAUGE_BASE_FORMAT, packet[:struct.calcsize(OUTGAUGE_BASE_FORMAT)])
    else:
        return None

    gear = unpacked[3]
    gear = gear - 1 if gear >= 2 else (0 if gear == 1 else gear - 1)
    return {
        "time": unpacked[0],
        "carName": unpacked[1].decode("utf-8", errors="ignore").rstrip("\x00"),
        "flags": decodeFlag(unpacked[2]),
        "gear": gear,
        "PLID": unpacked[4],
        "speed": unpacked[5],
        "rpm": unpacked[6],
        "turboPressure": unpacked[7],
        "engTemp": unpacked[8],
        "fuel": unpacked[9] * 100,
        "oilPressure": unpacked[10],
        "oilTemp": unpacked[11],
        "bico_de_luz": decodeLights(unpacked[12], unpacked[13]),
        "throttle": unpacked[14],
        "brake": unpacked[15],
        "clutch": unpacked[16],
        "misc1": unpacked[17],
        "misc2": unpacked[18],
        "ElectricEnabled": unpacked[8] > 1,
        "EngineEnabled": unpacked[6] > 100,
    }
