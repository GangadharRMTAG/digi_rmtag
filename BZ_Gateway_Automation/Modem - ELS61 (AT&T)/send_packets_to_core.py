import pytest
import time
import serial
import re
import csv
import pandas as pd
from SFConnection import get_connection
from playwright.sync_api import sync_playwright

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

def send_cli_command(ser, cmd, wait=1, expected_log=None, regex=False):
    print(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    # response = ser.read_all()
    print(f"<< Response:\n{response}")
    # if expected_log:
    #     if regex:
    #         match = re.search(expected_log, response)
    #         if match:
    #             print(f"[PASS] Expected pattern '{expected_log}' found.")
    #             return response, True
    #         else:
    #             print(f"[FAIL] Expected pattern '{expected_log}' NOT found.")
    #             return response, False
    #     else:
    #         if expected_log in response:
    #             print(f"[PASS] Expected text '{expected_log}' found.")
    #             return response, True
    #         else:
    #             print(f"[FAIL] Expected text '{expected_log}' NOT found.")
    #             return response, False

    # return response, None
    passed = None
    if expected_log:
        if regex:
            passed = bool(re.search(expected_log, response))
        else:
            passed = expected_log in response

        if passed:
            print(f"[PASS] Expected log '{expected_log}' found.")
        else:
            print(f"[FAIL] Expected log '{expected_log}' NOT found.")

    return response, passed

def snowflake_login_and_download_csv(device_id, expected_pattern):
    conn = get_connection("gthalang", "xU$I(R#WpFUC9H_6=J^oeiBu")
    id_str = device_id
    query = f"""
        SELECT DATERECEIVED, PACKET_PAYLOAD, RESPONSE_PAYLOAD
        FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
        WHERE cast(DATERECEIVED as timestamp) > dateadd(minute, -30, current_timestamp)
        AND DEVICEID IN ({id_str})
        AND CONTAINS(RESPONSE_PAYLOAD, '{expected_pattern}')
        ORDER BY DATERECEIVED DESC
    """
    file_path = "downloaded_result.csv" 
    df=pd.read_sql(query, conn)
    df.to_csv(file_path, index=False)
    return file_path

def test_send_packets_to_core(serial_connection):
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

    _, passed = send_cli_command(ser, 'tr 2', wait=2, expected_log="Requesting sensor read and upload")
    assert passed, "Transmission success log not found."

    print("Waiting for 20 minutes to snowflake get updated")
    # time.sleep(1200)
    # print("Wait completed, checking snowflake for the packet")
    # csv_file_path = snowflake_login_and_download_csv(device_id)

    # found = False
    # with open(csv_file_path, mode='r', newline='', encoding='utf-8') as file:
    #     reader = csv.reader(file)
    #     next(reader)
    #     second_row = next(reader, None)

    #     if second_row and len(second_row) >= 2:
    #         payload = second_row[1].strip()
    #         print(f"Second row payload: {payload}")
    #         # if expected_pattern in payload:
    #         #     print("Expected value found in second row payload.")
    #         #     found = True
    #         # else:
    #         #     print("Expected value NOT found in second row payload.")
    #         #     found = False
    #     else:
    #         print("Second row not found or invalid.")
    #         found = False

    # assert found, "Expected pattern not found in the second row payload."