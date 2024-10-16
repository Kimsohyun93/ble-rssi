import time
import math
import numpy as np
from influxdb import InfluxDBClient
import threading
from datetime import datetime

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')
last_query_time = int(time.time() * 1000) - 1100

def calculate_distance(rssi, rssi_at_1m=-52, path_loss_exponent=2.0):
    """
    RSSI 값을 사용하여 송신기와 수신기 사이의 거리를 추정합니다.
    
    :param rssi: 현재 수신된 RSSI 값
    :param rssi_at_1m: 1m 거리에서의 RSSI 값 (기본값: -59dBm)
    :param path_loss_exponent: 경로 손실 지수 (환경에 따라 다름, 기본값: 2.0)
    :return: 추정된 거리 (미터)
    """
    distance = 10 ** ((rssi_at_1m - rssi) / (10 * path_loss_exponent))
    return distance

def fetch_rssi_and_calculate_distance(start, end):
    query = f"SELECT * AS rssi_value FROM filtered_rssi WHERE time > {start}ms and time < {end}ms"
    print(query)

    result = client.query(query)
    points = list(result.get_points())
    json_body = []
    for point in points:
        tag_id = point['tag_id']
        receiver_name = point['receiver_name']
        rssi_value = point['filtered_rssi']
        timestamp = point['time']

        # print(f"원본 RSSI (tag_id={tag_id}, receiver_name={receiver_name}): {rssi_value}")

        distance = calculate_distance(rssi_value)
        # print(f"추정 거리: {distance:.2f} 미터")

        # 필터링된 값을 다시 InfluxDB에 저장
        json_data = {
            "measurement": "calculate_distance",
            "time": timestamp,
            "tags": {
                "tag_id": tag_id,
                "receiver_name": receiver_name
            },
            "fields": {
                "distance": distance
            }
        }
        json_body.append(json_data)

    try :    
        client.write_points(json_body)
    except Exception as e:
        print(e)


def start_background_thread(start, end):
    thread = threading.Thread(target=fetch_rssi_and_calculate_distance, args=(start, end, ))
    thread.daemon = True  # 메인 스레드 종료 시 백그라운드 스레드도 자동으로 종료
    thread.start()

if __name__ == "__main__":
    while True:
        current_time = int(time.time() * 1000) -100
        start_background_thread(last_query_time, current_time)
        last_query_time = current_time
        time.sleep(1)
