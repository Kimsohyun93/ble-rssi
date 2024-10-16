import time
import threading
from influxdb import InfluxDBClient
import pandas as pd

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')
last_query_time = int(time.time() * 1000) - 5000

def get_max_rssi_value_and_receiver(start):

    query = f"""
    SELECT tag_id, receiver_name, LAST(filtered_rssi) as rssi 
    FROM filtered_rssi
    WHERE time > {start}ms
    GROUP BY tag_id, receiver_name
    """
    result = client.query(query)
    points = list(result.get_points())

    data = []
    for point in points:
        data.append({
            'time': point['time'],
            'tag_id': point['tag_id'],
            'receiver_name': point['receiver_name'],
            'rssi': point['rssi']
        })

    df = pd.DataFrame(data)

    max_rssi_df = df.loc[df.groupby('tag_id')['rssi'].idxmax()].reset_index(drop=True)

    json_body = []

    for _, row in max_rssi_df.iterrows():
        json_body.append({
            "measurement": "max_rssi_receiver",
            "time": row['time'],
            "tags": {
                "tag_id": row['tag_id'],
            },
            "fields": {
                "receiver_name": row['receiver_name'],
                "max_rssi": row['rssi']
            }
        })

    if json_body:
        client.write_points(json_body)

def start_background_thread(start):
    thread = threading.Thread(target=get_max_rssi_value_and_receiver, args=(start, ))
    thread.daemon = True  
    thread.start()


if __name__ == "__main__":
    while True:
        current_time = int(time.time() * 1000)
        start_background_thread(last_query_time)
        last_query_time = current_time
        time.sleep(0.5)