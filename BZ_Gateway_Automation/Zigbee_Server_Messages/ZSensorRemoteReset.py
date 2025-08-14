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

def login_and_configure_time_interval(playwright, deviceID):
    browser = playwright.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context()
    print("Logging in tools", context)
    page = context.new_page()
    page.goto("https://tools.smartsense.co/")
    page.get_by_role("button", name="Sign In With SSO").click()
    page.get_by_role("textbox", name="Username").click()
    page.get_by_role("textbox", name="Username").fill("gthalang@digi.com")
    page.get_by_text("Keep me signed in").click()
    page.get_by_role("button", name="Next").click()
    page.get_by_role("textbox", name="Password").fill("Rmtag@123456")
    page.get_by_role("button", name="Verify").click()
    page.locator("iframe[title=\"'Verify with Duo Security'\"]").content_frame.locator("body").click()
    page.locator("iframe[title=\"'Verify with Duo Security'\"]").content_frame.get_by_role("button", name="Send Me a Push").click()
    time.sleep(10)
    page.get_by_role("link", name=" Devices").click()
    page.get_by_role("textbox").click()
    page.get_by_role("textbox").fill(deviceID)
    page.get_by_role("button", name="Search ").click()
    device_row = page.locator('tr').filter(has_text=deviceID)
    device_row.get_by_role("checkbox").click()
    page.get_by_role("button", name="Send Command").click()
    page.get_by_role("textbox", name="Enter Command").click()
    page.get_by_role("textbox", name="Enter Command").fill("9D03")
    page.get_by_role("button", name="save").click()

def test_ZSensorRemoteReset(serial_connection, record_property):
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

    send_cli_command(ser, 'zpmode up', wait=2,
                     expected="Zpoint mode set to: UP")

    assert send_cli_command(ser, 'tr 0', wait=2,
                            expected="Disabling transmissions to Core.")

    assert send_cli_command(ser, 'log debug', wait=2,
                            expected="Setting log level to debug for all modules")
    time.sleep(2)
    assert send_cli_command(ser, 'tr 1', wait=2,
                            expected="Enabling transmissions to Core")
    time.sleep(30)
    assert send_cli_command(ser, 'zplist', wait=2,
                            expected="Zpoint Network Tunnel Status")

    with sync_playwright() as playwright:
        login_and_configure_time_interval(playwright, device_id)
        # expected_pattern = "9D03"
    time.sleep(30)
    send_cli_command(ser, 'tr 2', wait=30)
    # log_uart("Waiting for 20 minutes to update packets in snowflake")
    # print("Waiting for 20 minutes to update packets in snowflake")
    # time.sleep(1200)
    # log_uart("Downloading CSV file from Snowflake")
    # print("Downloading CSV file from Snowflake")
    
    # csv_file_path = snowflake_login_and_download_csv(device_id, expected_pattern)

    # found = False
    # print("Expected hex value in packet from cvs file :", expected_pattern)
    # with open(csv_file_path, mode='r', newline='', encoding='utf-8') as file:
    #     reader = csv.reader(file)
    #     next(reader)
    #     second_row = next(reader, None)

    #     if second_row and len(second_row) >= 2:
    #         payload = second_row[1].strip()
    #         print(f"Second row payload: {payload}")
    #         if expected_pattern in payload:
    #             print("Expected value found in second row payload.")
    #             found = True
    #         else:
    #             print("Expected value NOT found in second row payload.")
    #             found = False
    #     else:
    #         print("Second row not found or invalid.")
    #         found = False

    # assert found, "Expected pattern not found in the second row payload."

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)
    log_uart("[✓] Test completed successfully.")
