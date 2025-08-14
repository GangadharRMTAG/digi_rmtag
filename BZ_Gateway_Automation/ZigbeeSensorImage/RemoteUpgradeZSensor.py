import pytest
import time
import serial
import re
import pandas as pd
from playwright.sync_api import sync_playwright
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
        'zpmode up',
        'tr 0',
        'log debug'
    ]
    for cmd in commands:
        send_cli_command(ser, cmd, wait=2)

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
    page.get_by_role("textbox", name="Enter Command").fill("8C3201016A")
    page.get_by_role("button", name="save").click()

def test_RemoteUpgradeZSensor(serial_connection, record_property):
    ser = serial_connection

    response = send_cli_command(ser, 'id', wait=2)
    match = re.search(r'\d{20}', response)
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]

    apply_standard_device_config(ser, password)
    
    sfstatus_resp = send_cli_command(ser, 'sfstatus', wait=2)
    expected_msg = "0 items in the store and 0 items in the priority queue"
    log_uart(f"Checking sfstatus: {sfstatus_resp}")

    if expected_msg not in sfstatus_resp:
        log_uart("[!] sfstatus not clean, flushing...")
        send_cli_command(ser, 'sfflush store', wait=3)
        sfstatus_resp = send_cli_command(ser, 'sfstatus', wait=2)

    assert expected_msg in sfstatus_resp, "[✗] sfstatus still not clean after flush."
    with sync_playwright() as playwright:
        login_and_configure_time_interval(playwright, device_id)

    send_cli_command(ser, 'tr 2', wait=5)
    send_cli_command(ser, 'firmware image info all', wait=5)
    send_cli_command(ser, 'firmware package info all', wait=5)

    with sync_playwright() as playwright:
        login_and_configure_time_interval(playwright, device_id)

    send_cli_command(ser, 'tr 2', wait=5)
    send_cli_command(ser, 'firmware package info all', wait=5)
    send_cli_command(ser, 'firmware image info all', wait=5)

    with sync_playwright() as playwright:
        login_and_configure_time_interval(playwright, device_id)

    send_cli_command(ser, 'tr 2', wait=5)
    send_cli_command(ser, 'firmware image info all', wait=5)
    # Log output
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
