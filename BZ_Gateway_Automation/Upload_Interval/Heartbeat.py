import pytest
import time
import serial
import re
#this test is not performed beacuse in 'hb' command their is  'No heartbeat timer message found'
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

def read_for_duration(ser, duration=5):
    """Read UART logs continuously for `duration` seconds."""
    end_time = time.time() + duration
    collected = ""
    while time.time() < end_time:
        data = ser.read_all().decode(errors='ignore')
        if data:
            collected += data
            log_uart(data.strip())
        time.sleep(0.2)
    return collected

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

def test_hb_timer_modem_reboot(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    log_uart("[PRE-CHECK] DUT ON, AC or battery >= 45%.")

    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'blemode down', wait=1)
    send_cli_command(ser, 'zpmode down', wait=1)
    send_cli_command(ser, 'log debug', wait=1)

    hb_resp = send_cli_command(ser, 'hb', wait=2)
    hb_match = re.search(r'Heartbeat\s+timer\s+will\s+expire\s+in\s+(\d+)\s+seconds', hb_resp, re.IGNORECASE)
    assert hb_match, "No heartbeat timer message found"
    hb_time_initial = int(hb_match.group(1))
    log_uart(f"[INFO] Initial HB timer: {hb_time_initial} seconds")

    send_cli_command(ser, 'AT+CFUN=4', wait=2)  
    send_cli_command(ser, 'network set_apn badapn', wait=2)
    logs_after_apn = read_for_duration(ser, duration=6)
    assert "badapn" in logs_after_apn or "Successfully set default APN string" in logs_after_apn, \
        "APN change not confirmed"

    hb_resp2 = send_cli_command(ser, 'hb', wait=2)
    hb_match2 = re.search(r'Heartbeat\s+timer\s+will\s+expire\s+in\s+(\d+)\s+seconds', hb_resp2, re.IGNORECASE)
    assert hb_match2, "No heartbeat timer message after APN change"
    hb_time_after = int(hb_match2.group(1))
    log_uart(f"[INFO] HB timer after APN change: {hb_time_after} seconds")
    assert hb_time_after < hb_time_initial, "HB timer did not continue countdown"

    log_uart(f"[INFO] Waiting {hb_time_after + 5} seconds for HB timer to expire...")
    time.sleep(hb_time_after + 5)

    tr_resp = send_cli_command(ser, 'tr 2', wait=8)
    error_logs = read_for_duration(ser, duration=10)
    expected_errors = [
        "Failed to bring modem online",
        "Upload attempts exhausted",
        "Modem failed to register",
        "Modem failed to activate pdp context",
        "Heartbeat timer has expired, restarting modem"
    ]
    for err in expected_errors:
        assert any(err in s for s in error_logs.splitlines()), f"Missing expected log: {err}"

    log_uart("[✓] Modem reboot triggered after HB timer expiry and failed transmission.")

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)
