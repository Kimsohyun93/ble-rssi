import math
import numpy as np
from influxdb import InfluxDBClient
import time

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

# 사용하는 receiver 위치에 따라 변경 
# 지구 반지름 (미터 단위)
EARTH_RADIUS = 6371000
N = 30 # 축적(5m --> 500m)

# Receiver 좌표 (한 변의 길이가 5m인 삼각형)
receiver_coords = {
    # 'receiver01': (37.566122, 126.877365),
    # 'receiver02': (37.566169, 126.877360),
    # 'receiver03': (37.566148, 126.877413) 
        # 'receiver01': (37.405505, 127.164109),
        # 'receiver02': (37.401542, 127.164244),
        # 'receiver03': (37.401550, 127.158301),
        # 'receiver04': (37.405386, 127.158401)
    'receiver01': (37.405386, 127.158401),
    'receiver02': (37.405455, 127.152693),
    'receiver03': (37.401542, 127.164244),
    'receiver04': (37.405505, 127.164109)
}

# receiver_metric_coords = {
#     'coord01': (-6, 4),
#     'coord02': (-1, 4),
#     'coord03': (1, 4) ,
#     'coord04': (6, 4),
#     'coord05': (-6, -4),
#     'coord06': (-1, -4) ,
#     'coord07': (1, -4),
#     'coord08': (6, -4)
# }

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
def rssi_to_distance(rssi, tx_power=-52, n=2):
    return 30 ** ((tx_power - rssi) / (10 * n)) * N

# 삼변측량 함수 (메트릭 좌표 기준)
def trilateration(d1, d2, d3, coords):
    x1, y1 = coords['receiver01']  # Receiver 1 coordinates
    x2, y2 = coords['receiver03']  # Receiver 2 coordinates
    x3, y3 = coords['receiver04']  # Receiver 3 coordinates

    print("receiver1({}, {}) : {}".format(x1, y1, d1))
    print("receiver3({}, {}) : {}".format(x2, y2, d2))
    print("receiver4({}, {}) : {}".format(x3, y3, d3))

    # Calculate weights as inverse squares of distances
    w1 = 1 / (d1 ** 2) if d1 != 0 else 0
    w2 = 1 / (d2 ** 2) if d2 != 0 else 0
    w3 = 1 / (d3 ** 2) if d3 != 0 else 0

    # Weighted trilateration calculations
    A = 2 * (x2 - x1) * w2
    B = 2 * (y2 - y1) * w2
    C = (d1 ** 2 - d2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2) * w2
    D = 2 * (x3 - x1) * w3
    E = 2 * (y3 - y1) * w3
    F = (d1 ** 2 - d3 ** 2 - x1 ** 2 + x3 ** 2 - y1 ** 2 + y3 ** 2) * w3

    # Solve for x and y, handling cases where B or E is zero
    if B == 0 and E == 0:
        print("Invalid receiver configuration for trilateration.")
        return None
    elif B == 0:
        y = F / E
        x = (C - B * y) / A if A != 0 else 0
    elif E == 0:
        y = C / B
        x = (F - E * y) / D if D != 0 else 0
    else:
        x = (C - (B * F / E)) / (A - (B * D / E))
        y = (C - A * x) / B

    return (x, y)

# InfluxDB에서 데이터를 읽어오기
def get_rssi_data(tag_id):
  # 5초 이내에 들어온 데이터 중 3개의 평균...
    query = f"SELECT mean(filtered_rssi) AS rssi FROM filtered_rssi WHERE tag_id='{tag_id}' and time > now() - 30s GROUP BY receiver_name ORDER BY time DESC LIMIT 3"
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
def save_tag_location(tag_id, x, y, lat, lng, distances):
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
                "longitude": lng,
                "distance_receiver01": distances['receiver01'],
                "distance_receiver02": distances['receiver02'],
                "distance_receiver03": distances['receiver03'],
                "distance_receiver04": distances['receiver04']
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
    x, y = trilateration(distances['receiver01'], distances['receiver03'], distances['receiver04'], receiver_metric_coords)
    print(f"LOCATION : \n {x}, {y}")

    # # 4. 메트릭 좌표 -> 실제 위도/경도 변환
    lat, lon = metric_to_latlon(x, y, ref_lat, ref_lon)

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
        "E8:76:58:5A:BE:38".lower(),
        "FF:E2:C4:F7:87:3C".lower(),
        "E7:B0:02:5F:47:A5".lower(),
        "F7:80:D7:63:28:59".lower(),
        "EB:F2:B2:90:F0:C0".lower(),
        "C6:64:FD:91:58:81".lower(),
        "DE:EB:0B:9F:A8:06".lower(),
        "FC:F8:8A:C6:A0:A6".lower(),
        "D6:08:CC:2D:FC:47".lower(),
        "C0:4F:E4:D1:F9:66".lower(),
        "FE:C9:33:9A:30:1B".lower(),
        "C3:5A:A3:7E:99:E5".lower(),
        "DC:9E:24:5B:D8:12".lower(),
        "EE:20:0C:25:98:FB".lower(),
        "D0:65:59:A7:C6:52".lower(),
        "E2:9C:F4:5A:06:CA".lower(),
        "FC:F7:48:13:CE:E1".lower(),
        "DE:EB:55:8D:FB:1C".lower(),
        "FC:66:33:71:B5:85".lower(),
        "C1:65:15:EB:76:7E".lower(),
        "F3:C6:C2:EA:60:DC".lower(),
        "E0:5F:E7:87:2E:A5".lower(),
        "E6:D7:17:CE:CB:7F".lower(),
        "C7:9B:34:6A:37:65".lower(),
        "C1:DC:86:09:2E:FA".lower(),
        "F8:04:38:34:B9:9E".lower(),
        "F8:4B:C0:85:D7:4E".lower(),
        "F6:F4:BD:77:6B:B3".lower(),
        "E6:37:A1:F3:57:0E".lower(),
        "D8:08:8B:B5:AD:77".lower(),
        "CB:74:40:BF:68:92".lower(),
        "DD:9A:D2:4F:50:41".lower(),
        "DF:32:54:53:AD:A2".lower(),
        "CA:A8:BC:8B:68:F7".lower(),
        "C7:EE:E5:68:B2:41".lower(),
        "E5:79:38:DF:BA:A2".lower(),
        "C5:E1:A0:77:EE:33".lower(),
        "E5:AB:DE:A7:3E:AE".lower(),
        "FA:20:BB:FE:A3:46".lower(),
        "DB:97:B7:EE:AF:B8".lower(),
        "DF:52:54:78:7D:E7".lower(),
        "F8:F2:F8:A6:64:27".lower(),
        "D2:D2:46:A2:40:22".lower(),
        "D5:35:04:87:15:0F".lower(),
        "D9:4E:21:88:EE:3E".lower(),
        "DF:D7:43:B8:C9:40".lower(),
        "EA:75:A6:51:FD:B4".lower(),
        "F7:5C:64:04:89:36".lower(),
        "DF:42:A7:61:3E:2E".lower(),
        "C1:AE:67:82:50:18".lower()
        ]

    # 태그 위치 모니터링 실행
    monitor_tag_positions(tag_ids)