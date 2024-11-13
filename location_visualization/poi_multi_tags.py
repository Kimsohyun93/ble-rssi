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

# listbox 에 띄울 tag 별 alias
alias_dict = {
    "c0:4f:e4:d1:f9:66" : "가수 1",
    "c1:65:15:eb:76:7e" : "가수 2",
    "c3:5a:a3:7e:99:e5" : "무대 STAFF 1",
    "c6:64:fd:91:58:81" : "무대 STAFF 2",
    "d0:65:59:a7:c6:52" : "무대 STAFF 3",
    "d6:08:cc:2d:fc:47" : "무대 STAFF 4",
    "dc:9e:24:5b:d8:12" : "무대 STAFF 5",
    "de:eb:0b:9f:a8:06" : "무대 STAFF 6",
    "de:eb:55:8d:fb:1c" : "무대 STAFF 7",
    "e2:9c:f4:5a:06:ca" : "무대 STAFF 8",
    "e7:b0:02:5f:47:a5" : "안전 STAFF 1",
    "e8:76:58:5a:be:38" : "안전 STAFF 2",
    "eb:f2:b2:90:f0:c0" : "안전 STAFF 3",
    "ee:20:0c:25:98:fb" : "안전 STAFF 4",
    "f7:80:d7:63:28:59" : "안전 STAFF 5",
    "fc:66:33:71:b5:85" : "안전 STAFF 6",
    "fc:f8:8a:c6:a0:a6" : "안전 STAFF 7",
    "fe:c9:33:9a:30:1b" : "안전 STAFF 8"
}

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
root.geometry("1200x1200")

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

main_frame = tk.Frame(root, width=1000)
main_frame.pack(side=tk.RIGHT, fill=tk.Y)

canvas = tk.Canvas(main_frame, width=1000, height=900)
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

# polygon의 좌표와 visible 플래그 변수 초기화
polygon_coords = [(337, 461), (399, 423), (530, 621), (465, 662)]

poi_rect = canvas.create_polygon(*polygon_coords, fill='yellow', outline='yellow', stipple='gray25')
# poi 사각형 클릭 시 update_tag_list 함수 호출
# canvas.tag_bind(poi_rect, '<Button-1>', lambda event: clicked_tag_list(is_polygon_clicked=True))

for receiver in receivers :
    oval_id = canvas.create_oval(receiver['position'][0] -5,receiver['position'][1] -5,receiver['position'][0] +5,receiver['position'][1] +5, fill='blue' )
    ovals.append({'id': oval_id, 'name': receiver['name'], 'position': receiver['position']})

# Listbox를 위한 프레임
poi_frame = tk.Frame(root, width=200)
poi_frame.pack(side=tk.LEFT, fill=tk.Y)

# Check button용 boolean var
oval_visible = tk.BooleanVar(value=True)

def toggle_oval_visibility():
    update_image()

visibility_button = tk.Checkbutton(poi_frame, text="Tags Visibility", variable=oval_visible, command=toggle_oval_visibility)
visibility_button.pack(side=tk.TOP, pady=3)

# Listbox와 Scrollbar를 담을 Frame 생성
listbox_frame = tk.Frame(poi_frame)
listbox_frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(listbox_frame)
listbox = tk.Listbox(listbox_frame, width=200, yscrollcommand=scrollbar.set, selectmode='single')
listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=listbox.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


# Ray Casting Algorithm
def is_point_in_poi_area(tag_position):
    x, y = tag_position
    num_vertices = len(polygon_coords)
    inside = False

    # Iterate over each edge of the polygon
    for i in range(num_vertices):
        x1, y1 = polygon_coords[i]
        x2, y2 = polygon_coords[(i + 1) % num_vertices]  # Next vertex, looping back to the start

        # Check if point is within y-bounds of the edge and x-position is to the left of the edge's x bound
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside

    return inside

# # tag list 업데이트 함수
# def clicked_tag_list(is_polygon_clicked):
#     listbox.delete(0, tk.END)
#     if is_polygon_clicked:
#         print("**************")
#         for tag in tags:
#             print(tag)
#             if is_point_in_poi_area(tag['position']):
#                 print(tag)
#                 listbox.insert(tk.END, tag['name'])
#         # listbox.update()
#     else:
#         listbox.delete(0, tk.END)

def update_tag_list():
    listbox.delete(0, tk.END)
    for tag in tags:
        if is_point_in_poi_area(tag['position']):
            listbox.insert(tk.END, tag['name'])


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
        # 마우스가 Oval 범위 내에 있을 때 수신기 이름을 표시
        if x0 <= mouse_x <= x1 and y0 <= mouse_y <= y1:
            name_label.config(text=name)
            name_label.place(x=mouse_x+130, y=mouse_y-20)  # 마우스 위치 근처에 이름 표시
            break
    else:
        name_label.place_forget()  # Oval 밖으로 나가면 이름 숨기기

# Canvas에 마우스 이동 이벤트 바인딩
canvas.bind("<Motion>", on_mouse_move)

def trilateration(distances):
    matrixA = []
    matrixB = []

    x0, y0, r0 = distances[0]['centerX'], distances[0]['centerY'], distances[0]['distance']

    for idx in range(1, len(distances)) :
        x,y,r = distances[idx]['centerX'], distances[idx]['centerY'], distances[idx]['distance']
        matrixA.append([x - x0, y - y0])
        matrixB.append([
            (x**2 + y**2 - r**2) - (x0**2 + y0**2 - r0**2)
        ])

    matrixA = np.array(matrixA)
    matrixB = np.array(matrixB).reshape(-1, 1) / 2  # 나눗셈은 2로 나눈 결과로 처리
    # (A^T * A)^-1 * A^T * B 계산
    matrixA_transpose = matrixA.T
    matrix_inverse = np.linalg.inv(np.dot(matrixA_transpose, matrixA))
    matrix_dot = np.dot(matrix_inverse, matrixA_transpose)
    position = np.dot(matrix_dot, matrixB)

    return position.flatten()

# 태그의 거리 정보로 원을 그리고 태그 위치를 표시하는 함수
def draw_tag_position(tag_positions):
    radius = 3
    for tag in tag_positions:
        # {'id': oval_id, 'name': receiver['name'], 'position': receiver['position']}
        # 태그 위치에 점 찍기
        position = tag['position']
        if oval_visible.get() :
            tag['id'] = canvas.create_oval(position[0] - radius, position[1] - radius, position[0] + radius, position[1] + radius, fill='red')
        else :
            tag['id'] = position
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
                position = next((receiver["position"] for receiver in receivers if receiver["name"] == receiver_name), None)
                distance = items['distance'] * N
                distances.append({"receiver_name":receiver_name, "centerX":position[0], "centerY":position[1], "distance": distance})
        if len(distances) >= 3 :
            tag_position = trilateration(distances)
            # print(f"trilateration tag position : {tag_position}")
            tag_alias = alias_dict.get(tag_id, "Unknown")
            results.append({'tag_id' : tag_id, 'name': tag_alias, 'position': tag_position})

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
    update_tag_list()


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


timelabel_frame = tk.Frame(main_frame)
timelabel_frame.pack(pady=5)

# 드롭다운 메뉴 생성
label = tk.Label(timelabel_frame, text="Time :")
label.pack(side=tk.LEFT, padx=10)

time_label = tk.Label(timelabel_frame, text=timestamp_to_kst(start_time), font=("Arial", 10))
time_label.pack(side=tk.LEFT, padx=5)

slider_frame = tk.Frame(main_frame)
slider_frame.pack(pady=5)

# 슬라이더 생성
slider = tk.Scale(slider_frame, from_=start_time, to=end_time, orient='horizontal', length=800, variable=selected_time, command=on_slider_change)
slider.pack(side=tk.LEFT, padx=5)

play_button = tk.Button(slider_frame, text="Play", command=start_playback)
play_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(slider_frame, text="Stop", command=stop_play)
stop_button.pack(side=tk.LEFT, padx=5)

timestamp_frame = tk.Frame(main_frame)
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