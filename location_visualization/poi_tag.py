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

client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

N = 3 # 거리 데이터를 시각적으로 표현하기 위해 적절한 배율 사용

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

receivers = [
    {"name": "receiver01", "position": (429, 538)},
    {"name": "receiver02", "position": (375, 464)},
    {"name": "receiver03", "position": (422, 607)},
    {"name": "receiver04", "position": (459, 583)}
]

tag_query = 'SHOW TAG VALUES FROM "tag_location" WITH KEY = "tag_id"'
tag_ids = [point['value'] for point in client.query(tag_query).get_points()]

# GUI 설정
root = tk.Tk()
root.title("Select Tag ID")
root.geometry("1200x1200")

# 선택된 tag_id 저장
selected_tag_id = tk.StringVar(value=tag_ids[0])
selected_time = tk.IntVar(value=0)  # 슬라이더 초기 위치

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

# 이미지 표시용 Canvas
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

# Receiver oval 저장
ovals = [] # receivers

# Tags oval 저장
tag_positions = []

# polygon의 좌표와 visible 플래그 변수 초기화
polygon_coords = [(337, 461), (399, 423), (530, 621), (465, 662)]
poi_rect = canvas.create_polygon(*polygon_coords, fill='yellow', outline='yellow', stipple='gray25')

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

def update_tag_list(tag_id, tag_position):
    listbox.delete(0, tk.END)
    tag_alias = alias_dict.get(tag_id, "Unknown")
    if tag_position :
        if is_point_in_poi_area(tag_position):
            listbox.insert(tk.END, tag_alias)

# 마우스가 움직일 때 호출되는 함수
def on_mouse_move(event):
    # 마우스의 x, y 좌표
    mouse_x, mouse_y = event.x, event.y

    # 각 수신기 영역에 마우스가 들어갔는지 확인
    for oval in ovals:
        oval_id = oval['id']
        receiver_name = oval['name']
        x0, y0, x1, y1 = canvas.coords(oval_id)  # Oval의 좌표 가져오기

        # 마우스가 Oval 범위 내에 있을 때 수신기 이름을 표시
        if x0 <= mouse_x <= x1 and y0 <= mouse_y <= y1:
            name_label.config(text=receiver_name)
            name_label.place(x=mouse_x-10, y=mouse_y-25)  # 마우스 위치 근처에 이름 표시
            break
    else:
        name_label.place_forget()  # Oval 밖으로 나가면 이름 숨기기

# Canvas에 마우스 이동 이벤트 바인딩
canvas.bind("<Motion>", on_mouse_move)

def trilateration(distances, positions):
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
def draw_tag_position(tag_position, distances):
    radius = 5
    if tag_position:
        if oval_visible.get() :
            tag_id = canvas.create_oval(tag_position[0] - radius, tag_position[1] - radius, tag_position[0] + radius, tag_position[1] + radius, fill='red')
            tag_positions.append(tag_id)
    # 각 수신기로부터 태그까지의 거리 표시 (원을 그림)
    for d in distances:
        receiver_name = d["receiver_name"]
        d_radius = d["distance"]
        receiver_pos = [r["position"] for r in receivers if r["name"] == receiver_name][0]
        if oval_visible.get() :
            tag_distance = canvas.create_oval(receiver_pos[0] - d_radius, receiver_pos[1] - d_radius, receiver_pos[0] + d_radius, receiver_pos[1] + d_radius, outline='red',  width=2)
            tag_positions.append(tag_distance)


def get_top_3_closest(distances, positions):
    # distance 값을 기준으로 distances와 positions을 함께 정렬
    sorted_distances_positions = sorted(zip(distances, positions), key=lambda x: x[0]['distance'])
    
    # 상위 3개의 distances와 positions을 분리하여 반환
    selected_distances = [item[0] for item in sorted_distances_positions[:3]]
    selected_positions = [item[1] for item in sorted_distances_positions[:3]]
    
    return selected_distances, selected_positions

# InfluxDB에서 태그 위치 데이터를 가져오는 함수
def fetch_data_and_update_tag(tag_id, timestamp):
    # 거리 데이터를 가져오기 위한 쿼리
    query = f"""
        SELECT last(distance) as distance, receiver_name 
        FROM calculate_distance 
        WHERE tag_id = '{tag_id}' AND time <= {timestamp}s AND time >= {timestamp - 10}s
        GROUP BY receiver_name
    """
    result = client.query(query)

    # 거리 데이터 수집
    distances = []
    positions = []
    for receiver in receivers:
        receiver_name = receiver['name']
        receiver_position = receiver['position']
        # if receiver_name != 'receiver01' :
        
        points = list(result.get_points(tags={"receiver_name": receiver_name}))
        if points:
            distance = points[0]["distance"] * N
            # distances.append({"receiver_name":receiver_name, "distance": distance})
            distances.append({"receiver_name":receiver_name, "centerX":receiver_position[0], "centerY":receiver_position[1], "distance": distance})
            positions.append(receiver_position)

    print("distances", distances)
    print("positions", positions)

    selected_distances, selected_positions = get_top_3_closest(distances, positions)
    # selected_distances, selected_positions = distances, positions

    # print(f"distances : {distances}")
    # 삼각측량을 통해 태그의 위치 계산
    if len(selected_distances) >= 3:
        tag_position = trilateration(selected_distances, selected_positions)
        print(f"trilateration tag position : {tag_position}")
        if tag_position is not None:
            tag_position = tuple(map(int, tag_position))  # 정수로 변환
            return tag_position, selected_distances
    return None, selected_distances
    

# 이미지와 태그 위치 업데이트 함수
def update_image():
    tag_id = selected_tag_id.get()
    timestamp = selected_time.get()

    kst_time_str = timestamp_to_kst(timestamp)  # 선택된 시간을 KST 형식으로 변환
    time_label.config(text=kst_time_str)     

    # 태그 위치 및 거리 데이터 가져오기
    tag_position, distances = fetch_data_and_update_tag(tag_id, timestamp)

    # 기존에 그려진 태그와 원을 삭제
    for ovals in tag_positions:
        canvas.delete(ovals)

    if tag_position:
    # 태그 위치와 원 그리기
        draw_tag_position(tag_position, distances)

    update_tag_list(tag_id, tag_position)


# 슬라이더를 업데이트하는 함수
def update_slider_range():
    try:
        new_start_time = kst_to_utc_timestamp(start_entry.get())
        new_end_time = kst_to_utc_timestamp(end_entry.get())

        if new_start_time < new_end_time:
            # slider from to update
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

dropdown_frame = tk.Frame(main_frame)
dropdown_frame.pack(pady=5)

# 드롭다운 메뉴 생성
label = tk.Label(dropdown_frame, text="Select Tag ID:")
label.pack(side=tk.LEFT, padx=10)

dropdown = ttk.Combobox(dropdown_frame, textvariable=selected_tag_id, values=tag_ids)
dropdown.bind("<<ComboboxSelected>>", on_dropdown_change)
dropdown.config(font=("Arial", 10))
dropdown.pack(side=tk.LEFT, padx=5)

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