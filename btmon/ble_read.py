import subprocess
import re
from datetime import datetime 
def scan_ble_rssi(target_mac):
	process = subprocess.Popen(['btmon'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	buffer = ''
	try:
		while True:
			line = process.stdout.readline().decode('utf-8').strip()
			buffer += line + "\n"
			#print(line)
			
			mac_match = re.search(r"Address: ([0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5})", buffer)
			rssi_match = re.search(r"RSSI: (-\d+) dBm", buffer)
			
			if mac_match and rssi_match:
				mac_address = mac_match.group(1)
				rssi_value = rssi_match.group(1)
				
				if mac_address.lower() in [mac.lower() for mac in target_macs]:
					print(f"[{datetime.now()}] MAC: {mac_address}, RSSI: {rssi_value} dBm")
				mac_match = None
				rssi_match = None
				buffer = ''
				
	except KeyboardInterrupt:
		process.terminate()
		print("BLE 스캔 중단")
		
#target_macs = ["df:42:a7:61:3e:2e", "ea:75:a6:51:fd:b4", "f7:5c:64:04:89:36", "df:d7:43:b8:c9:40", "c1:ae:67:82:50:18"]
target_macs = [ "ea:75:a6:51:fd:b4"]
scan_ble_rssi(target_macs)


