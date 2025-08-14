import pytest
import time
import serial
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from SFConnection import get_connection
import csv

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
                log_uart(f"[✓] Expected regex pattern matched: '{expected}'")
                return True
            else:
                log_uart(f"[✗] Expected regex pattern NOT found: '{expected}'")
                return False
        else:
            if expected in response:
                log_uart(f"[✓] Expected string found: '{expected}'")
                return True
            else:
                log_uart(f"[✗] Expected string NOT found: '{expected}'")
                return False

    return response

def snowflake_login_and_download_csv(device_id, expected_pattern):
    conn = get_connection("gthalang", "xU$I(R#WpFUC9H_6=J^oeiBu")
    query = f"""
        SELECT DATERECEIVED,PACKET_PAYLOAD,RESPONSE_PAYLOAD
        FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
        WHERE DATERECEIVED BETWEEN '2025-07-04 00:00:00' AND '2025-07-04 23:59:00' AND DEVICEID='{device_id}'
        ORDER BY DATERECEIVED DESC;
    """
    file_path = "downloaded_result.csv"
    df = pd.read_sql(query, conn)
    df.to_csv(file_path, index=False)
    return file_path

def test_OldRecordHandling(serial_connection, record_property):
    ser = serial_connection

    response = send_cli_command(ser,'id', wait=2)
    match = re.search(r'\d{20}', response)
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]
    
    assert send_cli_command(ser, f'pass {password}', wait=2,
                            expected="Password Valid, Security access level 2 granted.")

    assert send_cli_command(ser, 'debug on', wait=2,
                            expected="Enabling external debug UART without auto-off")

    assert send_cli_command(ser, 'blemode down', wait=2,
                            expected="B-Sensor mode set to DOWN.")

    send_cli_command(ser, 'zpmode down', wait=2,
                     expected="Zpoint mode set to: DOWN")

    assert send_cli_command(ser, 'tr 0', wait=2,
                            expected="Disabling transmissions to Core.")

    assert send_cli_command(ser, 'log debug', wait=2,
                            expected="Setting log level to debug for all modules")
    time.sleep(2)

    response = send_cli_command(ser, 'sfstatus', wait=2)
    if "0 items in the store" not in response:
        log_uart("S&F store not empty, flushing store...")
        send_cli_command(ser, 'sfflush store', wait=5, expected="Flush successful")
    response = send_cli_command(ser, 'sfstatus', wait=2)
    assert "0 items in the store" in response, "S&F store not empty after flush!"
    send_cli_command(ser, 'sffill 33000 10')
    assert send_cli_command(ser, 'sfstatus', wait=2,
                            expected="S&F contains 65536 items in the store and 625 items in the priority queue")
    
    payload = "0311666000000134915483556E4000012C5206"
    for i in range(20):
        assert send_cli_command(ser, f'zpdummy {payload}', wait=10,
                            expected="zpoint: Successfully pushed packet to S&F")
        
        payload = "0311666000000134915483556E4000012B5206"
        for i in range(20):
            assert send_cli_command(ser, f'zpdummy {payload}', wait=10,
                            expected="zpoint: Successfully pushed packet to S&F")

    send_cli_command(ser, 'sfstatus', wait=2)
    send_cli_command(ser, 'sffill 100 10', wait=10)
    send_cli_command(ser, 'sfstatus', wait=2)

    payload = "0311666000000134915483556E40004DFA5206"
    for i in range(20):
        assert send_cli_command(ser, f'zpdummy {payload}', wait=10,
                            expected="zpoint: Successfully pushed packet to S&F")
        send_cli_command(ser, 'sfstatus', wait=2)
        send_cli_command(ser, 'tr 1', wait=20,
                            expected="Enabling transmissions to Core")
        assert send_cli_command(ser, 'sfstatus', wait=2,
                            expected="S&F contains 0 items in the store and 0 items in the priority queue")

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)
    log_uart("[✓] Test completed successfully.")
