import requests

import pyodbc
import json
import os
import sys

cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=DESKTOP-7F2VT38\SQLEXPRESS;"
                      "Database=Face_DB;"
                      "Trusted_Connection=yes;")
cursor = cnxn.cursor()

subscription_key = '387e6e9e5f074295b441b68c37a26570'
uri_base = 'https://westeurope.api.cognitive.microsoft.com'

image_dir_path = sys.argv[1]

def face_detect(path):
    path_to_face_api = '/face/v1.0/detect'
    headers = {
     'Content-Type': 'application/octet-stream',
     'Ocp-Apim-Subscription-Key': subscription_key,
    }
    params = {
        'returnFaceId': 'true',
        'returnFaceLandmarks': 'false',
        'returnFaceAttributes': 'age,gender,headPose,smile,facialHair,glasses,emotion,hair,makeup,occlusion,accessories,blur,exposure,noise',
        }

    valid_images = [".jpg",".bmp",".png", ".jpeg"]
    for file in os.listdir(path):
        ext = os.path.splitext(file)[1]
        if ext.lower() in valid_images:
            filename = os.path.join(path, file)
            with open(filename, 'rb') as f:
                img_data = f.read()
            try:
                response = requests.post(uri_base + path_to_face_api,
                                        data=img_data, 
                                        headers=headers,
                                        params=params)
                parsed = response.json()
                print(parsed)
                for person in parsed:
                    cursor.execute('INSERT into face_tbl (faceId, faceRectangle, faceAttributes, fileName, faceBlurLevel, faceBlurValue) values (?, ?, ?, ?, ?, ?)',\
                        str(person['faceId']), str(person['faceRectangle']), str(person['faceAttributes']), str(file), str(person['faceAttributes']['blur']['blurLevel']), float(person['faceAttributes']['blur']['value']))
            except Exception as e:
                print('Error:')
                print(e)

def request_face_group(faceId_list, start_group_id):
    path_to_face_api_group = '/face/v1.0/group'
    headers = {
     'Content-Type': 'application/json',
     'Ocp-Apim-Subscription-Key': subscription_key,
    }
    m_json = {"faceIds": faceId_list}
    try:
        response = requests.post(uri_base + path_to_face_api_group, headers=headers,json=m_json)
        parsed = response.json()
        for group_no, group in enumerate(parsed['groups']):
            for faceId in group:
                cursor.execute("UPDATE face_tbl SET faceGroup = ? WHERE faceId = ?", 'group' + str(group_no + start_group_id), faceId)
        for faceId in parsed['messyGroup']:
            cursor.execute("UPDATE face_tbl SET faceGroup = ? WHERE faceId = ?", 'messyGroup', faceId)
    except Exception as e:
        print('Error:')
        print(e)
    return len(parsed['groups'])



def face_group():

    rows = cursor.execute("SELECT * FROM face_tbl WHERE CONVERT(VARCHAR, faceBlurLevel) <> 'high'").fetchall()
    face_list = []
    face_cnt = 0
    group_cnt = 0
    start_group_id = 0
    for row in rows:
        print(row)
        face_list.append(row[0])
        if face_cnt >= 1000:
            start_group_id = request_face_group(face_list, start_group_id)
            group_cnt += start_group_id
            face_cnt = 0
            face_list = []
        face_cnt+=1
    request_face_group(face_list, start_group_id)



face_detect(image_dir_path)

# face_group()

cnxn.commit()
cnxn.close()
