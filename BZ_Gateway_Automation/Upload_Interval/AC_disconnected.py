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

def strip_ansi_and_timestamp(line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    return timestamp_prefix.sub('', line).strip()

def send_cli_command(ser, cmd, wait=1):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")
    return response

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM8'  # adjust to your local
    BAUD_RATE = 115200
    TIMEOUT = 2
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)
    yield ser
    ser.close()
    print("\n[Serial Closed]")

def test_upload_interval_no_ac(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    log_uart("[PRE-CHECK] Ensure AC power is physically disconnected from DUT.")

    # Step 1
    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    # Step 2
    upload_resp = send_cli_command(ser, 'upload', wait=8)
    log_uart(f"[DEBUG] Raw upload command output:\n{upload_resp}")

    upload_type_match = re.search(r'Current\s+Interval\s+Type\s+is\s+(\d+)', upload_resp, re.IGNORECASE)
    interval_match = re.search(r'Current\s+Upload\s+Interval\s+is\s+(\d+)', upload_resp, re.IGNORECASE)

    upload_type = upload_type_match.group(1) if upload_type_match else "?"
    upload_interval = int(interval_match.group(1)) if interval_match else 60

    log_uart(f"[INFO] Upload type: {upload_type}, Interval: {upload_interval} sec")

    assert upload_type == "1", f"Expected upload type 1, got {upload_type}"

    # Step 3
    t1 = time.time()
    send_cli_command(ser, DUMMY_PACKET, wait=2)
    log_uart(f"[INFO] First dummy packet sent at {time.ctime(t1)}")

    # Step 4
    time.sleep(max(upload_interval - 10, 5)) 
    t2 = time.time()
    send_cli_command(ser, DUMMY_PACKET, wait=2)
    log_uart(f"[INFO] Second dummy packet sent at {time.ctime(t2)}")

    # Step 5
    log_uart("[INFO] Waiting for next scheduled upload...")
    time.sleep(upload_interval + 20)

    # Step 6
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully without AC power.")
