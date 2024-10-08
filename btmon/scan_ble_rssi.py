import subprocess
import re
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from influxdb import InfluxDBClient
from datetime import datetime
# source ble/bin/activate

# 로그 설정 (하루마다 새로운 파일 생성)
handler = TimedRotatingFileHandler("ble_rssi", when="midnight", interval=1, backupCount=30)
handler.suffix = "%Y-%m-%d.log"  # 파일 이름 뒤에 날짜 추가

# 로그 포맷 설정
formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)


# InfluxDB 설정
INFLUXDB_ADDRESS = '10.252.73.35'
#INFLUXDB_ADDRESS = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = 'ORBRO'
READER_MAC_ADDRESS = "2c:cf:67:2a:74:a5"  # rpi mac address

# 원하는 BLE 디바이스의 MAC 주소 리스트
target_macs = ["df:42:a7:61:3e:2e", "ea:75:a6:51:fd:b4", "f7:5c:64:04:89:36", "df:d7:43:b8:c9:40", "c1:ae:67:82:50:18"]

# InfluxDB 클라이언트 연결
client = InfluxDBClient(host=INFLUXDB_ADDRESS, port=INFLUXDB_PORT, database=INFLUXDB_DATABASE)

def write_to_influxdb(mac_address, rssi_value, receiver_timestamp):
    json_body = [
        {
            "measurement": "ble_rssi",
            "tags": {
                "receiver_id": READER_MAC_ADDRESS,
                "tag_id": mac_address
            },
            "fields": {
                "rssi": int(rssi_value),
                "receiver_timestamp": receiver_timestamp
            }
        }
    ]
    client.write_points(json_body)

def scan_ble_rssi(target_macs):
    # btmon을 subprocess로 실행하여 BLE 패킷을 실시간으로 수신
    process = subprocess.Popen(['btmon'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    buffer = ''
    mac_address = None
    rssi_value = None
    inside_hci_event = False  # HCI Event 블록 내에서만 처리

    try:
        while True:
            line = process.stdout.readline().decode('utf-8').strip()

            if line.startswith("> HCI Event:"):
                inside_hci_event = True
                mac_match = None
                rssi_match = None
                buffer = ''
            elif line.startswith(("@ MGMT Command:", "< HCI Command:", "@ MGMT Event:")):
                inside_hci_event = False
                mac_match = None
                rssi_match = None
                buffer = ''

            buffer += line + "\n"
            #print(line)
            
            mac_match = re.search(r"Address: ([0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5})", buffer)
            rssi_match = re.search(r"RSSI: (-\d+) dBm", buffer)
            
            if mac_match and rssi_match:
                mac_address = mac_match.group(1)
                rssi_value = rssi_match.group(1)
                
                if mac_address.lower() in [mac.lower() for mac in target_macs] and inside_hci_event:
                    logger.info(f"RECEIVER_MAC: {READER_MAC_ADDRESS}, TAG_MAC: {mac_address}, RSSI: {rssi_value} dBm")
                    write_to_influxdb(mac_address, rssi_value, time.time())

				
    except KeyboardInterrupt:
        # 프로그램 종료 시 btmon 프로세스도 종료
        process.terminate()
        print("BLE 스캔 중단")


# BLE 태그의 RSSI 값 스캔
scan_ble_rssi(target_macs)
