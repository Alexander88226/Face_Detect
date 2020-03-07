import requests

import pyodbc
import json

cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=DESKTOP-7F2VT38\SQLEXPRESS;"
                      "Database=Face_DB;"
                      "Trusted_Connection=yes;")
cursor = cnxn.cursor()

subscription_key = '387e6e9e5f074295b441b68c37a26570'
filename = 'detection1.jpg'
uri_base = 'https://westeurope.api.cognitive.microsoft.com'
headers = {
     'Content-Type': 'application/json',
     'Ocp-Apim-Subscription-Key': subscription_key,
}
params = {
    'returnFaceId': 'true',
    'returnFaceLandmarks': 'false',
    'returnFaceAttributes': 'age,gender,headPose,smile,facialHair,glasses,emotion,hair,makeup,occlusion,accessories,blur,exposure,noise',
}
# route to the face api
path_to_face_api = '/face/v1.0/detect'
path_to_face_api_group = '/face/v1.0/group'
# open jpg file as binary file data for intake by the MCS api
with open(filename, 'rb') as f:
    img_data = f.read()
try:
    # response = requests.post(uri_base + path_to_face_api,
    #                          data=img_data, 
    #                          headers=headers,
    #                          params=params)


    cursor.execute('SELECT * FROM detect_face')

    face_list = []
    for row in cursor:
        face_list.append(row[0])
        print(type(row[0]))
    print("face_list")

    m_json = {"faceIds": face_list}
    response = requests.post(uri_base + path_to_face_api_group, headers=headers,json=m_json)

    # cursor.execute('INSERT into detect_face (faceId, faceRectangle, faceAttributes) values (?, ?, ?)', str(parsed[0]['faceId']), str(parsed[0]['faceRectangle']), str(parsed[0]['faceAttributes']))
    print ('Response:')
    parsed = response.json()
    print (parsed)

        
except Exception as e:
    print('Error:')
    print(e)


# cursor.execute('SELECT * FROM detect_face')

# for row in cursor:
#     print('row = %r' % (row,))
cnxn.commit()
cnxn.close()
