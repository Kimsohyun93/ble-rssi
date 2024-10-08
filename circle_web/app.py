from flask import Flask, render_template, jsonify
from influxdb import InfluxDBClient

app = Flask(__name__)
client = InfluxDBClient(host='10.252.73.96', port=8086, database='ORBRO')

# 고정된 Receiver 좌표 (임의의 예시)
receiver_coords = {
        'receiver01': [37.405505, 127.164109],
        'receiver02': [37.401542, 127.161244],
        'receiver03': [37.405386, 127.158401] 
}

# 특정 tag_id에 대한 거리 데이터 가져오기
def get_tag_distances(tag_id):
    query = f'''
    SELECT last("distance_receiver01") AS "distance_receiver01", 
           last("distance_receiver02") AS "distance_receiver02", 
           last("distance_receiver03") AS "distance_receiver03",
           last("latitude") AS "latitude", 
           last("longitude") AS "longitude"
    FROM "tag_location"
    WHERE "tag_id" = '{tag_id}'
    '''
    
    result = client.query(query)
    distances = {"distance_receiver01": 0, "distance_receiver02": 0, "distance_receiver03": 0, "latitude": 0, "longitude": 0}
    
    if result:
        for point in result.get_points():
            distances["distance_receiver01"] = point.get("distance_receiver01", 0)
            distances["distance_receiver02"] = point.get("distance_receiver02", 0)
            distances["distance_receiver03"] = point.get("distance_receiver03", 0)
            distances["latitude"] = point.get("latitude", 0)
            distances["longitude"] = point.get("longitude", 0)
    return distances

# 모든 tag_id에 대한 거리 데이터 가져오기
def get_all_tag_distances():
    query = f'''
    SELECT 
           last("distance_receiver01") AS "distance_receiver01", 
           last("distance_receiver02") AS "distance_receiver02", 
           last("distance_receiver03") AS "distance_receiver03",
           last("latitude") AS "latitude", 
           last("longitude") AS "longitude"
    FROM "tag_location"
    GROUP BY "tag_id"
    '''
    
    result = client.query(query)
    distances = {}
    if result:
        # for point in result.get_points():
        for point in result.raw['series']:
            tag_id = point['tags']["tag_id"]
            distances[tag_id] = {
                "distance_receiver01":  point['values'][0][1],
                "distance_receiver02": point['values'][0][2],
                "distance_receiver03": point['values'][0][3],
                "latitude": point['values'][0][4],
                "longitude": point['values'][0][5],
            }

    return distances

@app.route('/')
def index():
    return render_template('index.html')

# 태그 ID를 드롭다운에 제공
@app.route('/get_tag_ids')
def get_tag_ids():
    query = 'SHOW TAG VALUES FROM "tag_location" WITH KEY = "tag_id"'
    result = client.query(query)
    
    tag_ids = [tag['value'] for tag in result.get_points()]
    return jsonify(tag_ids)

# 태그별 거리 데이터 제공
@app.route('/get_distances/<tag_id>')
def get_distances(tag_id):
    distances = get_tag_distances(tag_id)
    return jsonify(distances)

# 모든 태그 거리 데이터 제공
@app.route('/get_all_distances')
def get_all_distances():
    distances = get_all_tag_distances()
    return jsonify(distances)


if __name__ == '__main__':
    app.run(debug=True)
