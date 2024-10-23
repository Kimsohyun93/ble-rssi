import cv2
import numpy as np
from PIL import Image, ImageTk
from influxdb import InfluxDBClient
from scipy.optimize import minimize
import tkinter as tk
from tkinter import ttk
import threading
import time as tm


client = InfluxDBClient(host='localhost', port=8086, database='ORBRO')

N = 10 # 거리 데이터를 시각적으로 표현하기 위해 적절한 배율 사용

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
root.geometry("1000x1200")

# 선택된 tag_id 저장
selected_tag_id = tk.StringVar(value=tag_ids[0])
selected_time = tk.IntVar(value=0)  # 슬라이더 초기 위치

# 기본 Unix 시간 범위 (초기값)
# start_time = (int(tm.time()) - 3600 ) # 현재 시간에서 1시간 전
# end_time = int(tm.time()) # 현재 시간

# start_time = 1728716400 # 2024-10-12 16:00:00 (Sat)
# end_time = 1728732600 # 2024-10-12 20:30:00 (Sat)

start_time = 1728716400 # 2024-10-12 13:00:00 (Sat)
end_time = 1728732600 # 2024-10-12 14:00:00 (Sat)

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

# Oval 정보 저장 (oval ID와 수신기 정보 매핑)
ovals = [] # receivers

# Oval 정보 저장 (oval ID와 수신기 정보 매핑)
tag_positions = []

# oval_id = canvas.create_oval(receivers[2]['position'][0] -50,receivers[2]['position'][1] -50,receivers[2]['position'][0] +50,receivers[2]['position'][1] +50, fill='yellow' )

for receiver in receivers :
    oval_id = canvas.create_oval(receiver['position'][0] -5,receiver['position'][1] -5,receiver['position'][0] +5,receiver['position'][1] +5, fill='blue' )
    ovals.append({'id': oval_id, 'name': receiver['name'], 'position': receiver['position']})


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


# 삼각측량 기법을 통해 tag의 위치 추정
def trilateration(distances, positions):
    def objective(x):
        return sum((np.linalg.norm(np.array(x) - np.array(pos)) - dist) ** 2 for pos, dist in zip(positions, [d["distance"] for d in distances]))
    initial_guess = np.mean(positions, axis=0)
    result = minimize(objective, initial_guess, method='L-BFGS-B')
    return result.x if result.success else None


# # 삼변측량 함수 (메트릭 좌표 기준)
# def trilateration(distances, positions):
#     # receivers를 딕셔너리로 변환
#     receiver_dict = {receiver["name"]: receiver["position"] for receiver in receivers}
#     distance_dict = {distance["receiver_name"]: distance["distance"] for distance in distances}
#     # 원하는 좌표 가져오기
#     x1, y1 = receiver_dict["receiver01"]  # Receiver 1 coordinates
#     x2, y2 = receiver_dict["receiver03"]  # Receiver 2 coordinates
#     x3, y3 = receiver_dict["receiver04"]  # Receiver 3 coordinates
#     d1 = distance_dict["receiver01"]
#     d2 = distance_dict["receiver03"]
#     d3 = distance_dict["receiver04"]

#     print("receiver1({}, {}) : {}".format(x1, y1, d1))
#     print("receiver3({}, {}) : {}".format(x2, y2, d2))
#     print("receiver4({}, {}) : {}".format(x3, y3, d3))

#     # # Calculate weights as inverse squares of distances
#     # w1 = 1 / (d1 ** 2) if d1 != 0 else 0
#     # w2 = 1 / (d2 ** 2) if d2 != 0 else 0
#     # w3 = 1 / (d3 ** 2) if d3 != 0 else 0

#     # Weighted trilateration calculations
#     A = 2 * (x2 - x1)
#     B = 2 * (y2 - y1)
#     C = (d1 ** 2 - d2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2)
#     D = 2 * (x3 - x1)
#     E = 2 * (y3 - y1)
#     F = (d1 ** 2 - d3 ** 2 - x1 ** 2 + x3 ** 2 - y1 ** 2 + y3 ** 2)

#     # # Solve for x and y, handling cases where B or E is zero
#     # if B == 0 and E == 0:
#     #     print("Invalid receiver configuration for trilateration.")
#     #     return None
#     # elif B == 0:
#     #     y = F / E
#     #     x = (C - B * y) / A if A != 0 else 0
#     # elif E == 0:
#     #     y = C / B
#     #     x = (F - E * y) / D if D != 0 else 0
#     # else:
#     #     x = (C - (B * F / E)) / (A - (B * D / E))
#     #     y = (C - A * x) / B
#     x = (C - (B * F / E)) / (A - (B * D / E))
#     y = (C - A * x) / B
    
#     # return np.array([x, y])

#     return (x, y)


# 태그의 거리 정보로 원을 그리고 태그 위치를 표시하는 함수
def draw_tag_position(tag_position, distances):
    # 태그 위치에 점 찍기
    tag_id = canvas.create_oval(tag_position[0] - 5, tag_position[1] - 5, tag_position[0] + 5, tag_position[1] + 5, fill='red')
    tag_positions.append(tag_id)
    # 각 수신기로부터 태그까지의 거리 표시 (원을 그림)
    for d in distances:
        receiver_name = d["receiver_name"]
        radius = d["distance"]
        receiver_pos = [r["position"] for r in receivers if r["name"] == receiver_name][0]
        tag_distance = canvas.create_oval(receiver_pos[0] - radius, receiver_pos[1] - radius, receiver_pos[0] + radius, receiver_pos[1] + radius, outline='red',  width=2)
        tag_positions.append(tag_distance)


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
        if receiver_name != 'receiver02' :
            points = list(result.get_points(tags={"receiver_name": receiver_name}))
            if points:
                distance = points[0]["distance"] * N
                distances.append({"receiver_name":receiver_name, "distance": distance})
                positions.append(receiver_position)
    print(f"distances : {distances}")
    # 삼각측량을 통해 태그의 위치 계산
    if len(distances) == 3:
        tag_position = trilateration(distances, positions)
        print(f"trilateration tag position : {tag_position}")
        if tag_position is not None:
            tag_position = tuple(map(int, tag_position))  # 정수로 변환
            return tag_position, distances
    return None, distances
    

# 이미지와 태그 위치 업데이트 함수
def update_image():
    tag_id = selected_tag_id.get()
    timestamp = selected_time.get()

    # 태그 위치 및 거리 데이터 가져오기
    tag_position, distances = fetch_data_and_update_tag(tag_id, timestamp)

    # 기존에 그려진 태그와 원을 삭제
    for ovals in tag_positions:

        canvas.delete(ovals)

    
    if tag_position:
        # 태그 위치와 원 그리기
        draw_tag_position(tag_position, distances)


# 슬라이더를 업데이트하는 함수
def update_slider_range():
    try:
        new_start_time = int(start_entry.get())
        new_end_time = int(end_entry.get())

        if new_start_time < new_end_time:
            slider.config(from_=new_start_time, to=new_end_time)
            selected_time.set(new_start_time)
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
    end_time = int(end_entry.get())  # 슬라이더의 종료 위치 (실제 시간 범위로 조정)


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

dropdown_frame = tk.Frame(root)
dropdown_frame.pack(pady=5)

# 드롭다운 메뉴 생성
label = tk.Label(dropdown_frame, text="Select Tag ID:")
label.pack(side=tk.LEFT, padx=10)

dropdown = ttk.Combobox(dropdown_frame, textvariable=selected_tag_id, values=tag_ids)
dropdown.bind("<<ComboboxSelected>>", on_dropdown_change)
dropdown.pack(side=tk.LEFT, padx=5)


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
start_label = tk.Label(timestamp_frame, text="Start Time (Unix Timestamp(s)):")
start_label.pack(side=tk.LEFT, padx=10)

start_entry = tk.Entry(timestamp_frame)
start_entry.insert(0, int(start_time))  # 초기값으로 start_time 설정
start_entry.pack(side=tk.LEFT, padx=5)

# Unix timestamp 입력을 위한 Label과 Entry 생성 (endtime)
end_label = tk.Label(timestamp_frame, text="End Time (Unix Timestamp(s)):")
end_label.pack(side=tk.LEFT, padx=10)

end_entry = tk.Entry(timestamp_frame)
end_entry.insert(0, int(end_time))  # 초기값으로 end_time 설정
end_entry.pack(side=tk.LEFT, padx=5)

# 입력된 값으로 슬라이더 범위를 업데이트하는 버튼
update_button = tk.Button(timestamp_frame, text="Update Time Range", command=update_slider_range)
update_button.pack(side=tk.LEFT, padx=5)
# 초기 이미지 설정
update_image()

root.mainloop()