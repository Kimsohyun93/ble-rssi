import pandas as pd
from ble_scanner import BLEScanner
import asyncio
import threading
import numpy as np
from datetime import datetime
import configparser

# Conf 파일에서 InfluxDB와 Receiver Id 가져오는 함수
def read_config(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)

    return {
        'influx_host': config.get('InfluxDB', 'host').strip().replace('"', '').replace("'", ''),
        'influx_port': config.get('InfluxDB', 'port').strip().replace('"', '').replace("'", ''),
        'influx_database': config.get('InfluxDB', 'database').strip().replace('"', '').replace("'", ''),
        'receiver_id': config.get('Receiver', 'receiver_id').strip().replace('"', '').replace("'", ''),
        'receiver_name': config.get('Receiver', 'receiver_name').strip().replace('"', '').replace("'", ''),
    }

# CSV 파일에서 MAC 주소와 Device Name을 매핑하는 함수
def get_device_mapping_from_csv(file_path):
    df = pd.read_csv(file_path)
    device_mapping = dict(zip(df['Mac Address'].str.lower(), df['Device Name']))
    return device_mapping

# 스캐너를 별도의 스레드에서 실행하는 함수
def run_scanner_in_thread(scanner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(scanner.start_scan())  # BLE 스캐너 비동기 함수 실행

# # 칼만 필터 초기화 함수
# def initialize_kalman_filter():
#     kf = KalmanFilter(dim_x=1, dim_z=1)
#     kf.x = np.array([[0.]])  # 초기 상태
#     kf.F = np.array([[1.]])  # 상태 전이 행렬
#     kf.H = np.array([[1.]])  # 측정 함수
#     kf.P *= 1000.  # 추정 오차 공분산 초기화
#     kf.R = 5  # 측정 잡음 공분산
#     kf.Q = 0.1  # 프로세스 잡음 공분산
#     return kf

if __name__ == "__main__":

    config_file = '/home/keti/ble/ble-rssi/config.conf'

    # 설정 파일에서 정보 읽기
    config_data = read_config(config_file)
    
    # CSV 파일에서 MAC 주소와 Device Name 매핑 가져오기
    device_mapping = get_device_mapping_from_csv("tag-list-240829-1.csv")
    
    # BLE 스캐너 인스턴스화 (Device Name과 MAC 주소 매핑 전달)
    scanner = BLEScanner(device_mapping, config_data)

    # 대상 MAC 주소들 (실시간으로 모니터링할 MAC 주소 리스트)
    # target_macs = [
    #     "df:42:a7:61:3e:2e".lower(),
    #     "ea:75:a6:51:fd:b4".lower(),
    #     "f7:5c:64:04:89:36".lower(),
    #     "df:d7:43:b8:c9:40".lower(),
    #     "c1:ae:67:82:50:18".lower()
    # ]
    
    # 칼만 필터 초기화 (각 MAC 주소별로 하나씩)
    # kalman_filters = [initialize_kalman_filter() for _ in target_macs]

    # 스캐너를 백그라운드 스레드에서 실행
    scan_thread = threading.Thread(target=run_scanner_in_thread, args=(scanner,))
    scan_thread.daemon = False
    scan_thread.start()
