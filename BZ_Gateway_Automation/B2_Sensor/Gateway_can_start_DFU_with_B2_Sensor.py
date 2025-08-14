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

def login_and_send_command(playwright, deviceID, command):
    browser = playwright.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://tools.smartsense.co/")

    page.get_by_role("button", name="Sign In With SSO").click()
    page.get_by_role("textbox", name="Username").click()
    page.get_by_role("textbox", name="Username").fill("gthalang@digi.com")
    page.get_by_text("Keep me signed in").click()
    page.get_by_role("button", name="Next").click()
    page.get_by_role("textbox", name="Password").fill("Rmtag@123456")
    page.get_by_role("button", name="Verify").click()

    iframe = page.frame_locator("iframe[title=\"'Verify with Duo Security'\"]")
    iframe.get_by_role("button", name="Send Me a Push").click()
    time.sleep(10)

    page.get_by_role("link", name=" Devices").click()
    page.get_by_role("textbox").click()
    page.get_by_role("textbox").fill(deviceID)
    page.get_by_role("button", name="Search ").click()
    device_row = page.locator('tr').filter(has_text=deviceID)
    device_row.get_by_role("checkbox").click()
    page.get_by_role("button", name="Send Command").click()
    page.get_by_role("textbox", name="Enter Command").click()
    page.get_by_role("textbox", name="Enter Command").fill(command)
    page.get_by_role("button", name="save").click()

    time.sleep(5)
    context.close()
    browser.close()

def test_GatewayCanStartDFUWithB2Sensor(serial_connection, record_property):
    ser = serial_connection

    response = send_cli_command(ser, 'id', wait=2)
    match = re.search(r'\d{20}', response)
    assert match, "Device ID not found in 'id' response"
    device_id = match.group(0)
    assert device_id in DEVICE_CREDENTIALS, f"Device ID {device_id} not in credentials list"
    password = DEVICE_CREDENTIALS[device_id]

    # Initial configuration with expected responses
    assert send_cli_command(ser, f'pass {password}', wait=2,
                            expected="Password Valid, Security access level 2 granted.")
    
    assert send_cli_command(ser, 'debug on', wait=2,
                            expected="Enabling external debug UART without auto-off")
    
    assert send_cli_command(ser, 'blemode up', wait=2,
                            expected="B-Sensor mode set to UP.")
    
    assert send_cli_command(ser, 'zpmode down', wait=2,
                            expected="Zpoint mode set to: DOWN")
    
    assert send_cli_command(ser, 'tr 0', wait=2,
                            expected="Disabling transmissions to Core.")
    
    assert send_cli_command(ser, 'log debug', wait=2,
                            expected="Setting log level to debug for all modules")
    
    send_cli_command(ser, 'bleil show', wait=2)

    # 1st Command: C20407000600
    with sync_playwright() as playwright:
        login_and_send_command(playwright, device_id, "C20407000600")

    time.sleep(30)
    assert send_cli_command(ser, 'tr 2', wait=5, expected="Requesting sensor read and upload")
    log_uart("[✓] Verified 'tr 2' response: 'Requesting sensor read and upload'")

    assert send_cli_command(ser, 'firmware package info all', wait=2,
                            expected="The following firmware packages are saved to device:")
    
    assert send_cli_command(ser, 'firmware image info all', wait=2,
                            expected="Listing firmware images save to device:")

    # 2nd Command: BB03000600
    with sync_playwright() as playwright:
        login_and_send_command(playwright, device_id, "BB03000600")

    time.sleep(30)
    assert send_cli_command(ser, 'tr 2', wait=5, expected="Requesting sensor read and upload")
    log_uart("[✓] Verified 'tr 2' response: 'Requesting sensor read and upload'")
    send_cli_command(ser, 'v', wait=2)

    # Final log capture
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")