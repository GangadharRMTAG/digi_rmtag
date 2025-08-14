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
    COM_PORT = 'COM3'
    BAUD_RATE = 115200
    TIMEOUT = 2

    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)

    yield ser

    ser.close()
    print("\n[Serial Closed]")

def send_cli_command(ser, cmd, wait=1):
    log_uart(f"\n{cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"\n{response}")
    return response
def apply_standard_device_config(ser, password):
    commands = [
        f'pass {password}',
        'debug on',
        'blemode down',
        'zpmode down',
        'tr 0',
        'log debug'
    ]
    for cmd in commands:
        send_cli_command(ser, cmd, wait=2)

def test_DataloggerUpload(serial_connection, record_property):
    ser = serial_connection

    response = send_cli_command(ser, 'id', wait=2)
    match = re.search(r'\d{20}', response)
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]

    apply_standard_device_config(ser, password)
    send_cli_command(ser, 'config print', wait=2)
    send_cli_command(ser, 'upload 20 AC Powered Interval', wait=5)
    send_cli_command(ser, 'vbv set port 4', wait=5)
    send_cli_command(ser, 'config print', wait=2)

    send_cli_command(ser, 'reset n', wait=2)
    time.sleep(20) # Wait for device to reset
    apply_standard_device_config(ser, password)
    send_cli_command(ser, 'config print', wait=2)

    # Log output
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
