import pytest
import time
import serial
import re
import pandas as pd

LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

def log_uart(msg):
    clean_msg = strip_ansi_and_timestamp(msg)
    print(clean_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(clean_msg + "\n")

def strip_ansi_and_timestamp(log_line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', log_line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    line = timestamp_prefix.sub('', line)
    return line.strip()

DEVICE_CREDENTIALS = {
    "53874770835668991999": "uzMjzm9dBKY3x@ZR",
    "52328298625871380479": "@@fT27u6kWATxGqW",
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
    "54890725700062412799": "G@x7LPSaVi+voKEF",
    "46762288917430403071": "dN3CUgn6!$bEjrxj",
}

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM9'
    BAUD_RATE = 115200
    TIMEOUT = 2
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)
    yield ser
    ser.close()
    print("\n[Serial Closed]")

def send_cli_command(ser, cmd, wait=1, expected=None, regex=False):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")

    if expected:
        if regex:
            match = re.search(expected, response)
            if match:
                log_uart(f"[✓] Expected regex matched: '{expected}'")
            else:
                log_uart(f"[✗] Expected regex NOT found: '{expected}'")
                assert False, f"Expected regex not found in response: {expected}"
        else:
            if expected in response:
                log_uart(f"[✓] Expected string matched: '{expected}'")
            else:
                log_uart(f"[✗] Expected string NOT found: '{expected}'")
                assert False, f"Expected string not found in response: {expected}"

    return response


def test_B2SensorReConfiguration(serial_connection, record_property):
    ser = serial_connection

    response = send_cli_command(ser, 'id', wait=2)
    match = re.search(r'\d{20}', response)
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]

    send_cli_command(ser, f'pass {password}', wait=2,
                     expected="Password Valid, Security access level 2 granted.")
    
    send_cli_command(ser, 'debug on', wait=2,
                     expected="Enabling external debug UART without auto-off")

    send_cli_command(ser, 'blemode up', wait=2,
                     expected="B-Sensor mode set to UP.")

    send_cli_command(ser, 'zpmode down', wait=2,
                     expected="Zpoint mode set to: DOWN")

    send_cli_command(ser, 'tr 0', wait=2,
                     expected="Disabling transmissions to Core.")

    send_cli_command(ser, 'log debug', wait=2,
                     expected="Setting log level to debug for all modules")

    send_cli_command(ser, 'bleil show', wait=2)

    send_cli_command(ser, 'blecfg', wait=2,
                     expected="blecfg - BLE Configuration")

    send_cli_command(ser, 'blecmd D5245C8 0401020101', wait=2)

    send_cli_command(ser, 'blecfg', wait=2,
                     expected="blecfg - BLE Configuration")

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
