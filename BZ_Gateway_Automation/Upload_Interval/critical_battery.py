import pytest
import time
import serial
import re
import pandas as pd
from SFConnection import get_connection
#successfully completed and pass in testrail
LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()  # reset log file

DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
}

def log_uart(msg):
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")

def strip_ansi_and_timestamp(line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    return timestamp_prefix.sub('', line).strip()

def send_cli_command(ser, cmd, wait=1, read_timeout=5):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    end_time = time.time() + read_timeout
    response_data = ""
    while time.time() < end_time:
        chunk = ser.read_all().decode(errors='ignore')
        if chunk:
            response_data += chunk
        time.sleep(0.2)
    log_uart(f"<< Response:\n{response_data}")
    return response_data

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

def test_upload_type3_low_battery(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    log_uart("[PRE-CHECK] Ensure AC power is disconnected and external supply simulates battery <25%.")
  
    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    vbat_resp = send_cli_command(ser, 'vbat', wait=2, read_timeout=5)
    log_uart(f"[DEBUG] Raw vbat output: {repr(vbat_resp)}")

    battery_match = re.search(r'Battery.*?(\d+)%', vbat_resp, re.IGNORECASE)
    battery_percent = int(battery_match.group(1)) if battery_match else None

    if battery_percent is None:
        pytest.skip("Battery percentage not found in vbat output — check DUT response format.")

    log_uart(f"[INFO] Battery percentage: {battery_percent}%")
    assert battery_percent < 25, f"Battery is not below 25%: {battery_percent}%"

    upload_resp = send_cli_command(ser, 'upload', wait=8)
    upload_type_match = re.search(r'Current\s+Interval\s+Type\s+is\s+(\d+)', upload_resp, re.IGNORECASE)
    interval_match = re.search(r'Current\s+Upload\s+Interval\s+is\s+(\d+)', upload_resp, re.IGNORECASE)

    upload_type = upload_type_match.group(1) if upload_type_match else "?"
    upload_interval = int(interval_match.group(1)) if interval_match else None

    log_uart(f"[INFO] Upload type: {upload_type}, Interval: {upload_interval} sec")
    assert upload_type == "3", f"Expected upload type 3, got {upload_type}"
    assert upload_interval is not None, "Upload interval could not be determined."

    send_cli_command(ser, 'sensors', wait=4)

    log_uart("[INFO] Waiting for next scheduled upload...")
    start_wait = time.time()
    time.sleep(upload_interval + 20)
    end_wait = time.time()
    log_uart(f"[INFO] Waited {end_wait - start_wait:.1f} seconds for possible upload.")

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed: Low battery upload type 3 verified.")
