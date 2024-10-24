import math
import numpy as np
from influxdb import InfluxDBClient
import time
from scipy.optimize import minimize


client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

# 사용하는 receiver 위치에 따라 변경 
# 지구 반지름 (미터 단위)
EARTH_RADIUS = 6371000
N = 30 # 축적(5m --> 500m)

# Receiver 좌표 (한 변의 길이가 5m인 삼각형)
receiver_coords = {
    'receiver01': (37.405386, 127.158401),
    'receiver02': (37.405455, 127.152693),
    'receiver03': (37.401542, 127.164244),
    'receiver04': (37.405505, 127.164109)
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
ref_lat, ref_lon = receiver_coords['receiver03']  # 기준점 (receiver01 좌표)
receiver_metric_coords = {receiver: latlon_to_metric(lat, lon, ref_lat, ref_lon) 
                          for receiver, (lat, lon) in receiver_coords.items()}

# RSSI -> 거리 변환 함수
def rssi_to_distance(rssi, tx_power=-52, n=2):
    return N * 10 ** ((tx_power - rssi) / (10 * n))

# 삼변측량 함수 (메트릭 좌표 기준)
def trilateration(d1, d2, d3, coords):
    x1, y1 = coords['receiver01']  # Receiver 1 coordinates
    x2, y2 = coords['receiver03']  # Receiver 2 coordinates
    x3, y3 = coords['receiver04']  # Receiver 3 coordinates


    ########### spicy minimize
    #####################################################
    # positions = [(x1, y1), (x2, y2), (x3, y3)]
    # def objective(x):
    #     return sum((np.linalg.norm(np.array(x) - np.array(pos)) - dist) ** 2 for pos, dist in zip(positions, [d1, d2, d3]))
    # initial_guess = np.mean(positions, axis=0)
    # result = minimize(objective, initial_guess, method='L-BFGS-B')
    # tag_position = result.x if result.success else None
    # if tag_position is not None:
    #     return tuple(tag_position)

    #####################################################

    ############# No Weights
    ######################################################
    # A = 2 * (x2 - x1)
    # B = 2 * (y2 - y1)
    # D = d1**2 - d2**2 - x1**2 + x2**2 - y1**2 + y2**2
    # E = 2 * (x3 - x1)
    # F = 2 * (y3 - y1)
    # G = d1**2 - d3**2 - x1**2 + x3**2 - y1**2 + y3**2

    # x = (D - (B * G) / F) / (A - (B * E) / F)
    # if F != 0:
    #     y = (G - E * x) / F
    # else:
    #     y = (D - A * x) / B
    ######################################################

    ############# with Weights
    ######################################################
    # Calculate weights as inverse squares of distances
    w1 = 1 / (d1 ** 2) if d1 != 0 else 0
    w2 = 1 / (d2 ** 2) if d2 != 0 else 0
    w3 = 1 / (d3 ** 2) if d3 != 0 else 0
    print("receiver1({}, {}, w: {}) : {}".format(x1, y1, w1, d1))
    print("receiver3({}, {}, w: {}) : {}".format(x2, y2, w2, d2))
    print("receiver4({}, {}, w: {}) : {}".format(x3, y3, w3, d3))

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
    ######################################################

    return (x, y)

# InfluxDB에서 데이터를 읽어오기
def get_rssi_data(time):
  # 5초 이내에 들어온 데이터 중 3개의 평균...
    query = f"SELECT tag_id, receiver_name, last(filtered_rssi) as rssi FROM filtered_rssi WHERE time <= {time}ms and time > {time-5000}ms GROUP BY tag_id, receiver_name"
    result = client.query(query)
    points = result.get_points()
    rssi_values = {}

    for point in points :
        tag_id = point['tag_id']
        receiver_name = point['receiver_name']
        if tag_id not in rssi_values :
            rssi_values[tag_id]={}
        if receiver_name not in rssi_values[tag_id]:
            rssi_values[tag_id][receiver_name] = {}
        rssi_values[tag_id][receiver_name] = point
    
    rssi_values = {tag_id: items for tag_id, items in rssi_values.items() if len(items) == 4}
    
    return rssi_values

# InfluxDB에 태그 위치 저장하기
def save_tag_location(time, tag_id, x, y, lat, lng, distances):
    json_body = [
        {
            "measurement": "1012_cry",
            "time": time,
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
def calculate_and_store_tag_position(time):
    # 1. InfluxDB에서 RSSI 데이터 가져오기
    rssi_data = get_rssi_data(time)
    if rssi_data :
        print(f"RSSI_DATA : \n {rssi_data}")
    # 2. RSSI 값을 거리로 변환
    distances = {}
    for tag_id, tag_items in rssi_data.items():
        data_time = ''
        for receiver_name, items in tag_items.items() :
            distances[receiver_name] = rssi_to_distance(items['rssi'])
            current_time = items['time']
            if data_time == '' or current_time > data_time:
                data_time = current_time
        print(f"DISTANCE : \n {distances}")

        # 3. 삼변측량으로 태그의 메트릭 좌표 계산
        x, y = trilateration(distances['receiver01'], distances['receiver03'], distances['receiver04'], receiver_metric_coords)
        print(f"LOCATION : \n {x}, {y}")

        # # 4. 메트릭 좌표 -> 실제 위도/경도 변환
        lat, lon = metric_to_latlon(x, y, ref_lat, ref_lon)

        # 5. InfluxDB에 태그 위치 저장
        save_tag_location(data_time, tag_id, x, y, lat, lon, distances)


# 태그별 좌표를 계산하고 InfluxDB에 저장하는 함수
def monitor_tag_positions(start_time, end_time):
    current_time = start_time

    while current_time <= end_time:
        try:
            calculate_and_store_tag_position(current_time)
        except Exception as e:
            print(f"Error processing : {e}")
        current_time += 500

if __name__ == "__main__" :
    # 시작과 끝 시간을 Unix timestamp (밀리초 단위)로 설정
    # start_time = int(time.time() * 1000)  # 현재 시간을 밀리초 단위로
    # end_time = start_time + 10000  # 예: 10초 후에 종료 (원하는 시간으로 변경 가능)

    start_time = 1728720000000
    end_time = 1728732600000

    # 태그 위치 모니터링 실행
    monitor_tag_positions(start_time, end_time)

    # get_rssi_data(1728730891)