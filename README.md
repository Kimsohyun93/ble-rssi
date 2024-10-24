# Beacon을 활용한 위치 측위 및 시각화

## 설치
 - pip install opencv-python numpy Pillow influxdb scipy Flask bleak pandas

## 폴더 설명
 ### bat_file 
  - rssi 데이터 처리 코드들을 window에서 자동 실행할 수 있도록 작성한 bat 코드
 ### ble
  - rssi 데이터를 처리하는 코드들
    - calculate_distance : 거리 계산
    - kalman_rssi : kalman filtering
    - max_rssi_per_tag : tag가 어떤 receiver에서 max rssi 값을 가지는지 확인
    - tag_location : receiver 까지의 거리 계산 및 삼각 측량을 활용한 tag 위치 계산 (임의의 lat, lng 사용)

 ### ble_rssi
    - rpi 가 수집하는 ble rssi 데이터

 ### location_visualization
  - 