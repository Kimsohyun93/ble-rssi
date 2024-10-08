import time
import asyncio
import threading
from filterpy.kalman import KalmanFilter
from influxdb import InfluxDBClient
import numpy as np
from datetime import datetime

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')
kalman_filters = {}
last_query_time = int(time.time() * 1000) - 100

def initialize_kalman_filter(tag_id, receiver_name):
    print("initialize kalman filter")

    kf = KalmanFilter(dim_x=1, dim_z=1)
    kf.x = np.array([[0.]])  # 초기 추정 값 (0으로 초기화)
    kf.F = np.array([[1.]])  # 상태 변환 행렬
    kf.H = np.array([[1.]])  # 관측 행렬
    kf.P *= 1000.  # 추정 오차 공분산 초기화
    kf.R = 5  # 측정 잡음 공분산
    kf.Q = 0.1  # 프로세스 잡음 공분산

    kalman_filters[(tag_id, receiver_name)] = kf

def fetch_and_store_filtered_rssi(start, end):
    query = f"SELECT * FROM ble_rssi WHERE time > {start}ms and time < {end}ms"
    result = client.query(query)
    points = list(result.get_points())

    for point in points:
        tag_id = point['tag_id']
        receiver_name = point['receiver_name']
        rssi_value = point['rssi']
        timestamp = point['time']

        # print(f"원본 RSSI (tag_id={tag_id}, receiver_name={receiver_name}): {rssi_value}")

        # Kalman 필터가 없는 경우 초기화
        if (tag_id, receiver_name) not in kalman_filters:
            initialize_kalman_filter(tag_id, receiver_name)

        # 칼만 필터 예측 단계
        kalman_filters[(tag_id, receiver_name)].predict()

        # 칼만 필터 업데이트 단계 (새로운 RSSI 값 적용)
        kalman_filters[(tag_id, receiver_name)].update(rssi_value)

        # 필터링된 값 가져오기
        filtered_rssi = kalman_filters[(tag_id, receiver_name)].x[0, 0]
        # print(f"필터링된 RSSI (tag_id={tag_id}, receiver_name={receiver_name}): {filtered_rssi}")

        json_body = [{
            "measurement": "filtered_rssi",
            "time": timestamp,
            "tags": {
                "tag_id": tag_id,
                "receiver_name": receiver_name
            },
            "fields": {
                "filtered_rssi": filtered_rssi
            }
        }]
        client.write_points(json_body)

def start_background_thread(start, end):
    thread = threading.Thread(target=fetch_and_store_filtered_rssi, args=(start, end, ))
    thread.daemon = True  # 메인 스레드 종료 시 백그라운드 스레드도 자동으로 종료
    thread.start()

if __name__ == "__main__":
    while True:
        current_time = int(time.time() * 1000)
        start_background_thread(last_query_time, current_time)
        last_query_time = current_time
        time.sleep(0.1)