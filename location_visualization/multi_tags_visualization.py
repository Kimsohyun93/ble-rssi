import cv2
import numpy as np
from PIL import Image, ImageTk
from influxdb import InfluxDBClient
from scipy.optimize import minimize
import tkinter as tk
from tkinter import ttk
import threading
import time as tm
from datetime import datetime
import pytz


def kst_to_utc_timestamp(datetime_str):
    # 문자열을 datetime 객체로 변환
    kst = pytz.timezone("Asia/Seoul")
    dt_kst = kst.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S"))
    # UTC로 변환하여 UNIX 타임스탬프로 변환
    dt_utc = dt_kst.astimezone(pytz.utc)
    return int(dt_utc.timestamp())

# UNIX 타임스탬프를 KST 시간으로 변환하는 함수
def timestamp_to_kst(unix_time):
    kst = pytz.timezone("Asia/Seoul")            # KST 타임존 객체 생성
    dt = datetime.fromtimestamp(unix_time, kst)  # KST 시간으로 변환
    return dt.strftime("%Y-%m-%d %H:%M:%S")

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

N = 3 # 거리 데이터를 시각적으로 표현하기 위해 적절한 배율 사용

receivers = [
    {"name": "receiver01", "position": (429, 538)},
    {"name": "receiver02", "position": (375, 464)},
    {"name": "receiver03", "position": (422, 607)},
    {"name": "receiver04", "position": (459, 583)}
]

# GUI 설정
root = tk.Tk()
root.title("Select Tag ID")
root.geometry("1000x1200")

selected_time = tk.IntVar(value=0)  # 슬라이더 초기 위치

# 기본 Unix 시간 범위 (초기값)
# start_time = (int(tm.time()) - 3600 ) # 현재 시간에서 1시간 전
# end_time = int(tm.time()) # 현재 시간

start_time_str = "2024-10-12 15:35:00"
end_time_str = "2024-10-12 15:40:00"

start_time = kst_to_utc_timestamp(start_time_str)
end_time = kst_to_utc_timestamp(end_time_str)

print("Start Time (Unix UTC):", start_time)
print("End Time (Unix UTC):", end_time)

# 재생 여부를 제어하는 변수
is_playing = False

# 이미지 표시용 Canvas
canvas = tk.Canvas(root, width=1000, height=900)
canvas.pack(pady=3)

# PNG 파일 불러오기
image_path = '241012_stage_layout.png' 
pil_image = Image.open(image_path).convert("RGB")
pil_image = pil_image.resize((1000, 900), Image.ANTIALIAS)
bg_photo = ImageTk.PhotoImage(pil_image)

# 배경 이미지 추가
canvas.create_image(0, 0, anchor=tk.NW, image=bg_photo)

# 수신기 이름을 표시할 텍스트 위젯
name_label = tk.Label(root, text="", bg="yellow")
name_label.place_forget()  # 처음에는 보이지 않게 설정

# Receiver Oval 정보 저장
ovals = []

# Tag Oval 정보 저장
tags = []

# oval_id = canvas.create_oval(receivers[2]['position'][0] -50,receivers[2]['position'][1] -50,receivers[2]['position'][0] +50,receivers[2]['position'][1] +50, fill='yellow' )

for receiver in receivers :
    oval_id = canvas.create_oval(receiver['position'][0] -5,receiver['position'][1] -5,receiver['position'][0] +5,receiver['position'][1] +5, fill='blue' )
    ovals.append({'id': oval_id, 'name': receiver['name'], 'position': receiver['position']})


# 마우스가 움직일 때 호출되는 함수
def on_mouse_move(event):
    # 마우스의 x, y 좌표
    global ovals, tags
    mouse_x, mouse_y = event.x, event.y
    all_ovals = ovals + tags
    # 각 수신기 영역에 마우스가 들어갔는지 확인
    for oval in all_ovals:
        oval_id = oval['id']
        name = oval['name']
        x0, y0, x1, y1 = canvas.coords(oval_id)  # Oval의 좌표 가져오기
        print(f"oval id : {oval_id}, oval: {oval}, coords : {canvas.coords(oval_id)}")
        # 마우스가 Oval 범위 내에 있을 때 수신기 이름을 표시
        if x0 <= mouse_x <= x1 and y0 <= mouse_y <= y1:
            name_label.config(text=name)
            name_label.place(x=mouse_x-10, y=mouse_y-25)  # 마우스 위치 근처에 이름 표시
            break
    else:
        name_label.place_forget()  # Oval 밖으로 나가면 이름 숨기기

# Canvas에 마우스 이동 이벤트 바인딩
canvas.bind("<Motion>", on_mouse_move)

def circle_intersection_points(circle1, circle2):
    """
    두 개의 원이 주어졌을 때 교점을 계산합니다.
    각 원은 (x, y, r) 형식의 튜플로 제공됩니다.
    """
    x1, y1, r1 = circle1
    x2, y2, r2 = circle2
    d = np.hypot(x2 - x1, y2 - y1)

    # 교점이 없거나 한 원이 다른 원을 포함하는 경우
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None

    # 두 원의 교점 좌표 계산
    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h = np.sqrt(r1**2 - a**2)
    x0 = x1 + a * (x2 - x1) / d
    y0 = y1 + a * (y2 - y1) / d
    rx = -(y2 - y1) * (h / d)
    ry = (x2 - x1) * (h / d)

    intersection1 = (x0 + rx, y0 + ry)
    intersection2 = (x0 - rx, y0 - ry)

    return [intersection1, intersection2]

def trilateration(distances):
    receiver_dict = {receiver["name"]: receiver["position"] for receiver in receivers}
    distance_dict = {distance["receiver_name"]: distance["distance"] for distance in distances}
    # 원하는 좌표 가져오기
    x1, y1 = receiver_dict["receiver01"]  # Receiver 1 coordinates
    x2, y2 = receiver_dict["receiver03"]  # Receiver 2 coordinates
    x3, y3 = receiver_dict["receiver04"]  # Receiver 3 coordinates
    d1 = distance_dict["receiver01"]
    d2 = distance_dict["receiver03"]+30
    d3 = distance_dict["receiver04"]
    # 각 원의 중심과 반경
    circle1 = (x1, y1, d1)
    circle2 = (x2, y2, d2)
    circle3 = (x3, y3, d3)

    # 각 원 쌍 간의 교점을 찾습니다.
    points = []
    for (c1, c2) in [(circle1, circle2), (circle1, circle3), (circle2, circle3)]:
        intersections = circle_intersection_points(c1, c2)
        if intersections:
            points.extend(intersections)

    # 교점이 없거나 2개 미만이면, 교차 영역이 없다고 판단합니다.
    if len(points) < 2:
        print("교차하는 영역이 없습니다.")
        return None

    # 교점들의 평균을 내어 교차 영역의 중심을 구합니다.
    center_x = np.mean([p[0] for p in points])
    center_y = np.mean([p[1] for p in points])

    return center_x, center_y

# 삼변측량 함수 (메트릭 좌표 기준)
# def trilateration(distances):
#     # receivers를 딕셔너리로 변환
#     receiver_dict = {receiver["name"]: receiver["position"] for receiver in receivers}
#     distance_dict = {distance["receiver_name"]: distance["distance"] for distance in distances}
#     # 원하는 좌표 가져오기
#     x1, y1 = receiver_dict["receiver01"]  # Receiver 1 coordinates
#     x2, y2 = receiver_dict["receiver03"]  # Receiver 2 coordinates
#     x3, y3 = receiver_dict["receiver04"]  # Receiver 3 coordinates
#     d1 = distance_dict["receiver01"]
#     d2 = distance_dict["receiver03"]+20
#     d3 = distance_dict["receiver04"]

#     print("receiver1({}, {}) : {}".format(x1, y1, d1))
#     print("receiver3({}, {}) : {}".format(x2, y2, d2))
#     print("receiver4({}, {}) : {}".format(x3, y3, d3))

#     # Calculate weights as inverse squares of distances
#     w1 = 1 / (d1 ** 2) if d1 != 0 else 0
#     w2 = 1 / (d2 ** 2) if d2 != 0 else 0
#     w3 = 1 / (d3 ** 2) if d3 != 0 else 0
#     # Weighted trilateration calculations
#     A = 2 * (x2 - x1) * w2
#     B = 2 * (y2 - y1) * w2
#     C = (d1 ** 2 - d2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2) * w2
#     D = 2 * (x3 - x1) * w3
#     E = 2 * (y3 - y1) * w3
#     F = (d1 ** 2 - d3 ** 2 - x1 ** 2 + x3 ** 2 - y1 ** 2 + y3 ** 2) * w3


#     if B == 0 and E == 0:
#         print("Invalid receiver configuration for trilateration.")
#         return None
#     elif B == 0:
#         y = F / E
#         x = (C - B * y) / A if A != 0 else 0
#     elif E == 0:
#         y = C / B
#         x = (F - E * y) / D if D != 0 else 0
#     else:
#         x = (C - (B * F / E)) / (A - (B * D / E))
#         y = (C - A * x) / B

#     return (x, y)


# 태그의 거리 정보로 원을 그리고 태그 위치를 표시하는 함수
def draw_tag_position(tag_positions):
    radius = 3
    for tag in tag_positions:
        # {'id': oval_id, 'name': receiver['name'], 'position': receiver['position']}
        # 태그 위치에 점 찍기
        position = tag['position']
        tag['id'] = canvas.create_oval(position[0] - radius, position[1] - radius, position[0] + radius, position[1] + radius, fill='red')
        tags.append(tag)

# InfluxDB에서 태그 위치 데이터를 가져오는 함수
def fetch_data_and_update_tag(timestamp):
    # 거리 데이터를 가져오기 위한 쿼리
    query = f"""
        SELECT last(distance) as distance, receiver_name, tag_id
        FROM calculate_distance 
        WHERE time <= {timestamp}s AND time >= {timestamp - 10}s
        GROUP BY tag_id, receiver_name
    """
    result = client.query(query)

    points = result.get_points()
    distance_values = {}

    for point in points :
        tag_id = point['tag_id']
        receiver_name = point['receiver_name']
        if tag_id not in distance_values :
            distance_values[tag_id]={}
        if receiver_name not in distance_values[tag_id]:
            distance_values[tag_id][receiver_name] = {}
        distance_values[tag_id][receiver_name] = point

    results = []
    for tag_id, tag_items in distance_values.items():
        distances = []
        for receiver_name, items in tag_items.items() :
            if receiver_name != 'receiver02':
                distances.append({"receiver_name":receiver_name, "distance": items['distance'] * N})
        if len(distances) >= 3 :
            tag_position = trilateration(distances)
            print(f"trilateration tag position : {tag_position}")
            results.append({'name': tag_id, 'position': tag_position})

    return results
    

# 이미지와 태그 위치 업데이트 함수
def update_image():
    timestamp = selected_time.get()

    kst_time_str = timestamp_to_kst(timestamp)  # 선택된 시간을 KST 형식으로 변환
    time_label.config(text=kst_time_str)     

    # 태그 위치 및 거리 데이터 가져오기
    tag_positions = fetch_data_and_update_tag(timestamp)

    # 기존에 그려진 태그와 원을 삭제
    for ovals in tags:
        canvas.delete(ovals['id'])
    tags.clear()
    if tag_positions:
        # 태그 위치와 원 그리기
        draw_tag_position(tag_positions)


# 슬라이더를 업데이트하는 함수
def update_slider_range():
    try:
        new_start_time = kst_to_utc_timestamp(start_entry.get())
        new_end_time = kst_to_utc_timestamp(end_entry.get())

        if new_start_time < new_end_time:
            slider.config(from_=new_start_time, to=new_end_time)
            selected_time.set(new_start_time)
            # slider time label
            kst_time_str = timestamp_to_kst(new_start_time)  # 선택된 시간을 KST 형식으로 변환
            time_label.config(text=kst_time_str)
        else:
            print("Start time must be less than end time.")
    except ValueError:
        print("Invalid Unix timestamp entered.")

# 슬라이더 이동 시 호출되는 함수
def on_slider_change(event):
    update_image()

# 드롭다운 선택 시 호출되는 함수
def on_dropdown_change(event):
    update_image()

def stop_play():
    global is_playing
    is_playing = False  # 재생 중지를 위한 변수 설정

# 데이터 재생 함수
def play_data():

    global is_playing
    is_playing = True  # 재생 시작을 위한 변수 설정

    start_time = selected_time.get()  # 슬라이더의 시작 위치
    end_time = kst_to_utc_timestamp(end_entry.get())  # 슬라이더의 종료 위치 (실제 시간 범위로 조정)

    # 범위 내에서 데이터를 처리
    for t in range(start_time, end_time + 1):
        if not is_playing:  # 중지 버튼이 눌리면 루프를 중단
            break
        selected_time.set(t)
        update_image()
        tm.sleep(0.01)  # 재생 속도 조정 (1초 간격으로 재생)


# 스레드를 사용해 데이터 재생
def start_playback():
    playback_thread = threading.Thread(target=play_data)
    playback_thread.start()


timelabel_frame = tk.Frame(root)
timelabel_frame.pack(pady=5)

# 드롭다운 메뉴 생성
label = tk.Label(timelabel_frame, text="Time :")
label.pack(side=tk.LEFT, padx=10)

time_label = tk.Label(timelabel_frame, text=timestamp_to_kst(start_time), font=("Arial", 10))
time_label.pack(side=tk.LEFT, padx=5)

slider_frame = tk.Frame(root)
slider_frame.pack(pady=5)

# 슬라이더 생성
slider = tk.Scale(slider_frame, from_=start_time, to=end_time, orient='horizontal', length=800, variable=selected_time, command=on_slider_change)
slider.pack(side=tk.LEFT, padx=5)

play_button = tk.Button(slider_frame, text="Play", command=start_playback)
play_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(slider_frame, text="Stop", command=stop_play)
stop_button.pack(side=tk.LEFT, padx=5)

timestamp_frame = tk.Frame(root)
timestamp_frame.pack(pady=5)

# Unix timestamp 입력을 위한 Label과 Entry 생성 (starttime)
start_label = tk.Label(timestamp_frame, text="Start Time (KST YYYY-mm-dd hh:mm:ss):")
start_label.pack(side=tk.LEFT, padx=10)

start_entry = tk.Entry(timestamp_frame)
start_entry.insert(0, start_time_str)  # 초기값으로 start_time 설정
start_entry.pack(side=tk.LEFT, padx=5)

# Unix timestamp 입력을 위한 Label과 Entry 생성 (endtime)
end_label = tk.Label(timestamp_frame, text="End Time (KST YYYY-mm-dd hh:mm:ss):")
end_label.pack(side=tk.LEFT, padx=10)

end_entry = tk.Entry(timestamp_frame)
end_entry.insert(0, end_time_str)  # 초기값으로 end_time 설정
end_entry.pack(side=tk.LEFT, padx=5)

# 입력된 값으로 슬라이더 범위를 업데이트하는 버튼
update_button = tk.Button(timestamp_frame, text="Update Time Range", command=update_slider_range)
update_button.pack(side=tk.LEFT, padx=5)
# 초기 이미지 설정
update_image()

root.mainloop()