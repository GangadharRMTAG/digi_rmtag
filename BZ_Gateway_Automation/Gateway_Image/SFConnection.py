import snowflake.connector
import pandas as pd

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
   