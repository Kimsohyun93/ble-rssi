import asyncio
from bleak import BleakScanner
from datetime import datetime
from influxdb import InfluxDBClient

class BLEScanner:
    def __init__(self, device_mapping, config_data, max_data_points=300):
        # MAC 주소와 Device Name 매핑 딕셔너리
        self.device_mapping = device_mapping
        # RSSI 값을 저장하는 딕셔너리 (각 MAC 주소별로)
        self.rssi_data = {mac: [] for mac in device_mapping.keys()}
        # 시간 값도 저장 (시간대별로 RSSI 변화를 기록)
        self.time_data = {mac: [] for mac in device_mapping.keys()}
        # 저장할 데이터 포인트의 최대 개수
        self.max_data_points = max_data_points
        # Influxdb client 선언
        self.client = InfluxDBClient(host=config_data['influx_host'], port=config_data['influx_port'], database=config_data['influx_database'])
        # Receiver ID 선언
        self.receiver_name = config_data['receiver_name']

    def write_to_influxdb(self, tag_id, tag_name, rssi_value, receiver_timestamp):
        json_body = [
            {
                "measurement": "ble_rssi",
                "tags": {
                    "receiver_name": self.receiver_name,
                    "tag_id": tag_id
                },
                "fields": {
                    "rssi": int(rssi_value),
                    "tag_name": tag_name,
                    "receiver_timestamp": receiver_timestamp
                }
            }
        ]
        try :  
            self.client.write_points(json_body)
        except Exception as e:
            print(e)


    # 스캔 콜백 함수
    def detection_callback(self, device, advertisement_data):
        mac_address = device.address.lower()
        # MAC 주소가 매핑된 Device Name이 있는지 확인
        device_name = self.device_mapping.get(mac_address, None)
        
        # 매핑된 Device Name이 있을 경우만 데이터 기록
        if device_name:
            # 현재 시간 (밀리초까지 표시)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # RSSI 신호 강도
            rssi = advertisement_data.rssi

            # influxdb에 전송 
            self.write_to_influxdb(mac_address, device_name, rssi, current_time)

            # # MAC 주소에 따라 RSSI와 시간 데이터를 저장
            # self.rssi_data[mac_address].append(rssi)
            # self.time_data[mac_address].append(current_time)

            # # 리스트 크기 제한: 최신 100개의 데이터만 유지
            # if len(self.rssi_data[mac_address]) > self.max_data_points:
            #     self.rssi_data[mac_address] = self.rssi_data[mac_address][-self.max_data_points:]
            #     self.time_data[mac_address] = self.time_data[mac_address][-self.max_data_points:]

            # 출력 (MAC 주소 대신 Device Name 출력)
            print(f"TIME: {current_time} / DEVICE NAME: {device_name} / RSSI: {rssi}")

    # BLE 장치 스캔을 무한 루프로 실행하는 함수
    async def start_scan(self):
        scanner = BleakScanner(self.detection_callback)
        print("Scanning started...")
        await scanner.start()
        try:
            while True:
                await asyncio.sleep(1)  # 지속적으로 스캔 (1초마다 이벤트 처리)
        except KeyboardInterrupt:
            await scanner.stop()  # Ctrl+C로 중단될 때 안전하게 스캔 중지
            print("Scanning stopped.")

    # 스캐닝을 실행하는 메서드 (비동기 루프)
    def run(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start_scan())
        except KeyboardInterrupt:
            print("Scanning stopped.")
            loop.stop()

