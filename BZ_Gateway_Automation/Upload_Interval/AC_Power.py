import pytest
import time
import serial
import re
import pandas as pd
from SFConnection import get_connection

LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
}

DUMMY_PACKET = "zpdummy 0311666000000134915483556E40ED4CD45206"

def log_uart(msg):
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")

def strip_ansi_and_timestamp(log_line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', log_line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    line = timestamp_prefix.sub('', line)
    return line.strip()

def send_cli_command(ser, cmd, wait=1):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")
    return response

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM8'
    BAUD_RATE = 115200
    TIMEOUT = 2

    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)
    yield ser
    ser.close()
    print("\n[Serial Closed]")

def test_dummy_packet_upload(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    send_cli_command(ser, 'upload', wait=2)

    t1 = time.time()
    send_cli_command(ser, DUMMY_PACKET, wait=2)
    log_uart(f"[INFO] First dummy packet sent at {time.ctime(t1)}")

    time.sleep(30)  
    t2 = time.time()
    send_cli_command(ser, DUMMY_PACKET, wait=2)
    log_uart(f"[INFO] Second dummy packet sent at {time.ctime(t2)}")
    log_uart("[INFO] Waiting for next upload interval...")
    time.sleep(60)  # adjust based on device interval

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
