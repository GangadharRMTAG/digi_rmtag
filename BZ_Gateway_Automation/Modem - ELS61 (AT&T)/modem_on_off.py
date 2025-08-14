import pytest
import time
import serial
import re
from SFConnection import send_cli_command

DEVICE_CREDENTIALS = {
    "53874770835668991999": "uzMjzm9dBKY3x@ZR",
    "52328298625871380479": "@@fT27u6kWATxGqW",
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
    "54890725700062412799": "G@x7LPSaVi+voKEF",
    "46762288917430403071": "dN3CUgn6!$bEjrxj",
}

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM5'
    BAUD_RATE = 115200
    TIMEOUT = 2

    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)

    yield ser

    ser.close()
    print("\n[Serial Closed]")

# def send_cli_command(ser, cmd, wait=1, expected_log=None, regex=False):
#     print(f"\n>> Sending: {cmd}")
#     ser.write((cmd + '\n').encode())
#     time.sleep(wait)
#     response = ser.read_all().decode(errors='ignore')
#     print(f"<< Response:\n{response}")
#     passed = None
#     if expected_log:
#         if regex:
#             passed = bool(re.search(expected_log, response))
#         else:
#             passed = expected_log in response

#         if passed:
#             print(f"[PASS] Expected log '{expected_log}' found.")
#         else:
#             print(f"[FAIL] Expected log '{expected_log}' NOT found.")

#     return response, passed

def test_responsive_to_AT_commands(serial_connection):
    ser = serial_connection

    response, _ = send_cli_command(ser,'id', wait=2)
    match = re.search(r'\d{20}', response)
    assert match, "Device ID not found in logs."
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]
    
    _, passed = send_cli_command(ser, f'pass {password}', wait=2, expected_log="Password Valid, Security access level 2 granted.")
    assert passed, "Access not granted after password."

    _, passed = send_cli_command(ser, 'debug on', wait=2, expected_log="Enabling external debug UART without auto-off")
    assert passed, "Debug mode enable log not found."

    _, passed = send_cli_command(ser, 'log debug', wait=2, expected_log="Setting log level to debug for all modules")
    assert passed, "Log level not set for all modules."

    # _, passed = send_cli_command(ser, 'zpmode down', wait=2, expected_log="Zpoint mode set to: DOWN")
    # assert passed, "Zpoint mode set to: DOWN"

    # _, passed = send_cli_command(ser, 'blemode down', wait=2, expected_log="B-Sensor mode set to DOWN.")
    # assert passed, "B-Sensor mode set to DOWN."

    # _, passed = send_cli_command(ser, 'minfo', wait=2, expected_log="Modem model: EG21-G")
    # assert passed, "Modem info log not found."

    _, modem_on = send_cli_command(
        ser, 'mmstatus', wait=5, expected_log="Modem Status: ON"
    )
    if modem_on:
        _, passed = send_cli_command(
            ser, 'moff', wait=10, expected_log="modem: De-registering from network"
        )
        assert passed, "Failed to turn off modem."
    else:
        print("[SKIP] Modem already OFF, skipping 'moff' command.")

    _, modem_off = send_cli_command(
        ser, 'mmstatus', wait=5, expected_log="Modem Status: OFF"
    )
    if modem_off:
        _, passed = send_cli_command(
            ser, 'mon', wait=12
        )
        assert passed, "Failed to turn ON modem."
    else:
        print("[SKIP] Modem already ON, skipping 'mon' command.")

    _, modem_on = send_cli_command(
        ser, 'mmstatus', wait=5, expected_log="Modem Status: ON"
    )
    if modem_on:
        _, passed = send_cli_command(
            ser, 'mon', wait=10
        )
        assert passed, "Failed to turn on modem."
    else:
        print("[SKIP] Modem already ON, skipping 'mon' command.")
    
    send_cli_command(ser, 'moff', wait=5, expected_log="modem: De-registering from network")

    _, modem_off = send_cli_command(
        ser, 'mmstatus', wait=5, expected_log="Modem Status: OFF"
    )
    if modem_off:
        _, passed = send_cli_command(
            ser, 'moff', wait=5
        )
        assert passed, "Failed to turn off modem."
    else:
        print("[SKIP] Modem already OFF, skipping 'moff' command.")

    