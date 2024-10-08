import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from ble_scanner import BLEScanner
import asyncio
import threading
from filterpy.kalman import KalmanFilter
import numpy as np
import matplotlib.dates as mdates
from datetime import datetime

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

# 칼만 필터 초기화 함수
def initialize_kalman_filter():
    kf = KalmanFilter(dim_x=1, dim_z=1)
    kf.x = np.array([[0.]])  # 초기 상태
    kf.F = np.array([[1.]])  # 상태 전이 행렬
    kf.H = np.array([[1.]])  # 측정 함수
    kf.P *= 1000.  # 추정 오차 공분산 초기화
    kf.R = 5  # 측정 잡음 공분산
    kf.Q = 0.1  # 프로세스 잡음 공분산
    return kf

# 실시간으로 RSSI 변화를 그리는 함수
def animate(i, scanner, target_macs, kalman_filters, lines_original, lines_filtered):
    for idx, target_mac in enumerate(target_macs):
        time_data = scanner.time_data[target_mac]
        rssi_data = scanner.rssi_data[target_mac]

        # 데이터 크기가 다를 경우, 작은 리스트에 맞춰 자름
        min_len = min(len(time_data), len(rssi_data))
        time_data = time_data[-min_len:]
        rssi_data = rssi_data[-min_len:]

        # 최근 100개의 데이터만 유지
        if len(time_data) > 100:
            time_data = time_data[-100:]
            rssi_data = rssi_data[-100:]

        # 시간 데이터를 datetime 객체로 변환
        if time_data:
            time_data = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f") for t in time_data]

        # 데이터가 존재할 때만 그리기
        if time_data and rssi_data:
            # 칼만 필터 적용
            filtered_rssi_data = []
            for rssi in rssi_data:
                kalman_filters[idx].predict()  # 예측 단계
                kalman_filters[idx].update(rssi)  # 업데이트 단계
                filtered_rssi_data.append(kalman_filters[idx].x[0, 0])  # 필터된 값 저장

            # 기존 라인을 업데이트 (기존 그래프에 이어서 그리기)
            lines_original[idx].set_data(time_data, rssi_data)
            lines_filtered[idx].set_data(time_data, filtered_rssi_data)

            # X축을 시간 포맷에 맞춰 설정
            ax.relim()  # X축과 Y축 범위를 재조정
            ax.autoscale_view()  # 그래프가 동적으로 스케일 조정되도록 설정
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))  # 시간 포맷 설정
            fig.autofmt_xdate()  # X축 시간 포맷 맞추기

    plt.xlabel("Time")
    plt.ylabel("RSSI")
    plt.ylim(-100, -20)  # Y축 범위를 -100부터 -20까지로 설정
    plt.grid(True)  # 그리드 추가
    plt.tight_layout()
    # legend 위치를 그래프 바깥으로 설정하고, fontsize를 작게 조정
    plt.legend(loc='upper left', fontsize='small')

if __name__ == "__main__":
    # 다크 테마 적용
    plt.style.use('dark_background')
    
    # CSV 파일에서 MAC 주소와 Device Name 매핑 가져오기
    device_mapping = get_device_mapping_from_csv("tag-list-240829-1.csv")
    
    # BLE 스캐너 인스턴스화 (Device Name과 MAC 주소 매핑 전달)
    scanner = BLEScanner(device_mapping)

    # 대상 MAC 주소들 (실시간으로 모니터링할 MAC 주소 리스트)
    target_macs = [
        "d9:4e:21:88:ee:3e".lower(),
        "d5:35:04:87:15:0f".lower(),
        "d2:d2:46:a2:40:22".lower()
    ]

    # 칼만 필터 초기화 (각 MAC 주소별로 하나씩)
    kalman_filters = [initialize_kalman_filter() for _ in target_macs]

    # 그래프 설정 (각 MAC 주소별로 라인 생성)
    fig, ax = plt.subplots()
    
    # 색상 리스트 (각 MAC 주소별 동일한 색상으로 점과 선을 그리기 위함)
    colors = plt.get_cmap("tab10").colors  # 색상 팔레트
    
    # 각 MAC 주소별로 점과 선 생성
    lines_original = [ax.plot([], [], 'o', label=f"RSSI :{device_mapping[mac]}", ms = 1, color=colors[idx])[0] for idx, mac in enumerate(target_macs)]
    lines_filtered = [ax.plot([], [], '-', label=f"RSSI (Kalman) :{device_mapping[mac]}", color=colors[idx])[0] for idx, mac in enumerate(target_macs)]

    # 스캐너를 백그라운드 스레드에서 실행
    scan_thread = threading.Thread(target=run_scanner_in_thread, args=(scanner,))
    scan_thread.daemon = True
    scan_thread.start()

    # 실시간 그래프 설정
    ani = FuncAnimation(fig, animate, fargs=(scanner, target_macs, kalman_filters, lines_original, lines_filtered), interval=1000, cache_frame_data=False)

    # 그래프 표시
    plt.show()
