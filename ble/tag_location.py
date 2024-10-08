import math
import numpy as np
from influxdb import InfluxDBClient
import time

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

# 지구 반지름 (미터 단위)
EARTH_RADIUS = 6371000

# Receiver 좌표 (한 변의 길이가 5m인 삼각형)
receiver_coords = {
    'receiver01': (37.566122, 126.877365),   # 위도, 경도
    # 37.409831, 127.154135
    'receiver02': (37.566169, 126.877360),   # 위도, 경도
    # 37.401880, 127.148716
    'receiver03': (37.566148, 126.877413)    # 위도, 경도
    # 37.401905, 127.160143
}


# 위도/경도 -> 메트릭 변환 함수 (좌표 기준점 설정)
def latlon_to_metric(lat, lon, ref_lat, ref_lon):
    dlat = math.radians(lat - ref_lat)
    dlon = math.radians(lon - ref_lon)
    lat_avg = math.radians((lat + ref_lat) / 2)
    x = EARTH_RADIUS * dlon * math.cos(lat_avg)
    y = EARTH_RADIUS * dlat
    return (x, y)

# 메트릭 -> 위도/경도 변환 함수
def metric_to_latlon(x, y, ref_lat, ref_lon):
    lat_avg = math.radians(ref_lat)
    dlat = y / EARTH_RADIUS
    dlon = x / (EARTH_RADIUS * math.cos(lat_avg))
    lat = ref_lat + math.degrees(dlat)
    lon = ref_lon + math.degrees(dlon)
    return (lat, lon)

# Receivers의 메트릭 좌표로 변환
ref_lat, ref_lon = receiver_coords['receiver01']  # 기준점 (receiver01 좌표)
receiver_metric_coords = {receiver: latlon_to_metric(lat, lon, ref_lat, ref_lon) 
                          for receiver, (lat, lon) in receiver_coords.items()}

# RSSI -> 거리 변환 함수
def rssi_to_distance(rssi, tx_power=-59, n=2):
    return 10 ** ((tx_power - rssi) / (10 * n))

# 삼변측량 함수 (메트릭 좌표 기준)
def trilateration(d1, d2, d3, coords):
    x1, y1 = coords['receiver01']
    x2, y2 = coords['receiver02']
    x3, y3 = coords['receiver03']

    A = 2 * (x2 - x1)
    B = 2 * (y2 - y1)
    C = d1 ** 2 - d2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2
    D = 2 * (x3 - x1)
    E = 2 * (y3 - y1)
    F = d1 ** 2 - d3 ** 2 - x1 ** 2 + x3 ** 2 - y1 ** 2 + y3 ** 2

    x = (C - (B * F / E)) / (A - (B * D / E))
    y = (C - A * x) / B

    return (x, y)

# InfluxDB에서 데이터를 읽어오기
def get_rssi_data(tag_id):
  # 5초 이내에 들어온 데이터 중 3개의 평균...
    query = f"SELECT mean(filtered_rssi) AS rssi FROM filtered_rssi WHERE tag_id='{tag_id}' and time > now() - 5s GROUP BY receiver_name ORDER BY time DESC LIMIT 3"
    result = client.query(query)
    # points = list(result.get_points())
    points = result.raw['series']
    if len(points) < 3:
        raise ValueError("Not enough RSSI data for trilateration")
    # rssi_values = {point['receiver_name']: point['rssi'] for point in points}
    rssi_values = {}
    for point in points:
        receiver_name = point['tags']['receiver_name']
        rssi = point['values'][0][1]  # 'values'에서 RSSI 값을 가져옴
        rssi_values[receiver_name] = rssi

    return rssi_values

# InfluxDB에 태그 위치 저장하기
def save_tag_location(tag_id, x, y, lat, lon, distances):
    json_body = [
        {
            "measurement": "tag_location",
            "tags": {
                "tag_id": tag_id
            },
            "fields": {
                "x_metric": x,
                "y_metric": y,
                "latitude": lat,
                "longitude": lon,
                "distance_receiver01": distances['receiver01'],
                "distance_receiver02": distances['receiver02'],
                "distance_receiver03": distances['receiver03']
            }
        }
    ]
    client.write_points(json_body)

# 메인 함수
def calculate_and_store_tag_position(tag_id):
    # 1. InfluxDB에서 RSSI 데이터 가져오기
    rssi_data = get_rssi_data(tag_id)
    print(f"RSSI_DATA : \n {rssi_data}")
    # 2. RSSI 값을 거리로 변환
    distances = {}
    for receiver, rssi in rssi_data.items():
        distances[receiver] = rssi_to_distance(rssi)
    print(f"DISTANCE : \n {distances}")

    # 3. 삼변측량으로 태그의 메트릭 좌표 계산
    x, y = trilateration(distances['receiver01'], distances['receiver02'], distances['receiver03'], receiver_metric_coords)

    # 4. 메트릭 좌표 -> 실제 위도/경도 변환
    lat, lon = metric_to_latlon(x, y, ref_lat, ref_lon)
    print(f"LOCATION : \n {lat}, {lon}")


    # 5. InfluxDB에 태그 위치 저장
    save_tag_location(tag_id, x, y, lat, lon, distances)


# 태그별 좌표를 계산하고 InfluxDB에 저장하는 함수
def monitor_tag_positions(tag_ids):
    while True:
        for tag_id in tag_ids:
            try:
                calculate_and_store_tag_position(tag_id)
            except Exception as e:
                print(f"Error processing tag {tag_id}: {e}")
        
        # 1초마다 반복
        time.sleep(1)

if __name__ == "__main__" :
      
    # 모니터링할 태그 리스트
    tag_ids = [
        "C1:AE:67:82:50:18".lower(), 
        "DF:42:A7:61:3E:2E".lower(),
        "DF:D7:43:B8:C9:40".lower(),
        "EA:75:A6:51:FD:B4".lower(),
        "F7:5C:64:04:89:36".lower()]

    # 태그 위치 모니터링 실행
    monitor_tag_positions(tag_ids)