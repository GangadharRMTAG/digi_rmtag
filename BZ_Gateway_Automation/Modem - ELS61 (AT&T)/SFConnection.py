import snowflake.connector
import pandas as pd
import time
import re

def send_cli_command(ser, cmd, wait=1, expected_log=None, regex=False):
    print(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    print(f"<< Response:\n{response}")
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

def get_connection(username, password):
    try:
        conn = snowflake.connector.connect(
            user=username,
            password=password,
            account="fo68387.us-east-1",
            warehouse="ENG_DEVS"
        )
        print("Type of conn:", type(conn))
        return conn
    except Exception as e:
        print(f"❌ Error connecting to Snowflake: {e}")
        return f"Error: {e}"
    
def fetch_packets(conn, device_ids, start, end, packet_type):
    placeholders = ",".join([f"'{d}'" for d in device_ids])
    query = f"""
        SELECT DATERECEIVED, PACKET_PAYLOAD, RESPONSE_PAYLOAD, DEVICEID
        FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
        WHERE DATERECEIVED BETWEEN %s AND %s
          AND DEVICEID IN ({placeholders})
          AND CONTAINS(PACKET_PAYLOAD, %s)
        ORDER BY DATERECEIVED
    """
    return pd.read_sql(query, conn, params=[start, end, packet_type])
   