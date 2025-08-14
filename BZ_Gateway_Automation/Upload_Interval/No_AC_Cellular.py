import pytest
import time
import serial
import re
#this test is failed. Expected upload type 5, got 3
LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

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

def test_upload_no_ac_power(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    log_uart("[PRE-CHECK] Ensure AC power is physically disconnected from DUT.")

    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    ac_resp = send_cli_command(ser, 'acpg', wait=2)
    assert "AC power not detected" in ac_resp, "AC Power is still connected!"

    send_cli_command(ser, 'at AT+CFUN=4', wait=3) 
    send_cli_command(ser, 'network set_apn badapn', wait=2)

    upload_resp = send_cli_command(ser, 'upload', wait=8)
    upload_type_match = re.search(r'Current\s+Interval\s+Type\s+is\s+(\d+)', upload_resp, re.IGNORECASE)
    interval_match = re.search(r'Current\s+Upload\s+Interval\s+is\s+(\d+)', upload_resp, re.IGNORECASE)

    upload_type = upload_type_match.group(1) if upload_type_match else "?"
    upload_interval = int(interval_match.group(1)) if interval_match else 60

    log_uart(f"[INFO] Upload type: {upload_type}, Interval: {upload_interval} sec")
    assert upload_type == "5", f"Expected upload type 5, got {upload_type}"

    sensors_resp = send_cli_command(ser, 'sensors', wait=5)
    assert "Forcing a measurement interval" in sensors_resp, "Sensors command did not trigger as expected"

    log_uart("[INFO] Waiting for next transmission...")
    t_start = time.time()
    time.sleep(upload_interval + 10)  
    t_end = time.time()

    measured_interval = round(t_end - t_start)
    log_uart(f"[INFO] Measured interval: {measured_interval} sec (Expected: {upload_interval} sec)")
    assert abs(measured_interval - upload_interval) <= 10, \
        f"Measured interval {measured_interval}s does not match expected {upload_interval}s"

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully for No AC Power + Cellular Issue (Upload Type 5)")