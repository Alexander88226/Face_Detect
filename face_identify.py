import requests
import json
import os
import sys

import pyodbc
cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=DESKTOP-7F2VT38\SQLEXPRESS;"
                      "Database=Face_DB;"
                      "Trusted_Connection=yes;")
cursor = cnxn.cursor()
CREATE_FACE_TABLE_SQL = '''IF  NOT EXISTS (SELECT * FROM sys.objects 
    WHERE object_id = OBJECT_ID(N'[dbo].[face_tbl]') AND type in (N'U'))
    CREATE TABLE [dbo].[face_tbl](
	[faceId] [varchar](50) NULL,
	[faceRectangle] [text] NULL,
	[faceAttributes] [text] NULL,
	[fileName] [text] NULL,
	[faceBlurLevel] [varchar](50) NULL,
	[faceBlurValue] [float] NULL,	
    [PersonName] [varchar](50) NULL,
	[GroupName] [varchar](50) NULL
    
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
'''
cursor.execute(CREATE_FACE_TABLE_SQL)

subscription_key = '387e6e9e5f074295b441b68c37a26570'
uri_base = 'https://westeurope.api.cognitive.microsoft.com'
json_headers = {
    'Content-Type': 'application/json',
    'Ocp-Apim-Subscription-Key': subscription_key,
}

stream_headers = {
    'Content-Type': 'application/octet-stream',
    'Ocp-Apim-Subscription-Key': subscription_key,
}
simple_headers = {
    'Ocp-Apim-Subscription-Key': subscription_key,
}

# detect face of all images for image folder
def face_detect(path):
    path_to_face_api = '/face/v1.0/detect'
    headers = {
     'Content-Type': 'application/octet-stream',
     'Ocp-Apim-Subscription-Key': subscription_key,
    }
    params = {
        'returnFaceId': 'true',
        'returnFaceLandmarks': 'false',
        'recognitionModel':'recognition_02',
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
    cursor.commit()

# face-group per each 1000 faceIds
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
        group_no = 0
        for group in parsed['groups']:
            for faceId in group:
                cursor.execute("UPDATE face_tbl SET PersonName = ? WHERE faceId = ?", 'person' + str(group_no + start_group_id), faceId)
            group_no += 1
        for faceId in parsed['messyGroup']:
            group_no += 1
            cursor.execute("UPDATE face_tbl SET PersonName = ? WHERE faceId = ?", 'person' + str(group_no), faceId)
        cursor.commit()
        return group_no
    except Exception as e:
        print('Error:')
        print(e)
        return 0

# face-group for all faceIds of DataBase
def face_group():
    
    rows = cursor.execute("SELECT * FROM face_tbl WHERE CONVERT(VARCHAR, faceBlurLevel) <> 'high'").fetchall()
    face_list = []
    face_cnt = 0
    group_cnt = 0
    start_group_id = 0
    for row in rows:
        face_list.append(row[0])
        if face_cnt >= 1000:
            group_cnt = request_face_group(face_list, start_group_id)
            start_group_id += group_cnt
            face_cnt = 0
            face_list = []
        face_cnt+=1
    if face_list:
        request_face_group(face_list, start_group_id)


def create_Person(personGroupId, person_dir, person_path):
    body = dict()
    body["name"] = person_dir
    body["userData"] = "this person is " + person_dir
    #Request URL
    path_to_face_api_person = '/face/v1.0/persongroups/'+personGroupId+'/persons'
    if personGroupId == 'visitor':
        path_to_face_api_person = '/face/v1.0/largepersongroups/'+personGroupId+'/persons'

    try:
        # REST Call 
        response = requests.post(uri_base + path_to_face_api_person, headers=json_headers,json=body)
        print("Create Person RESPONSE:" + str(response.status_code))
        parsed = response.json()
        # if response.status_code == 200:
        #     sql = "INSERT INTO person_tbl (name, userData, personId, groupId) VALUES (?,?,?,?)"
        #     cursor.execute(sql, body["name"], body["userData"], parsed["personId"], personGroupId)
        #     cursor.commit()
        return parsed["personId"]
    except Exception as e:
        print(e)
        return ""

def add_person_face(personGroupId, personName, personId, person_path, faceRectangle):
    faceRectangle = eval(faceRectangle)
    target_face = [faceRectangle['left'],faceRectangle['top'], faceRectangle['width'], faceRectangle['height']]
    target_face = ' ,'.join([str(elem) for elem in target_face])
    print(target_face)
    params = {
        'userData': personName,
        'detectionModel': 'detection_02',
        'targetFace' : target_face
        }
    path_to_face_api_add_face = '/face/v1.0/persongroups/'+personGroupId+'/persons/'+personId+'/persistedFaces'
    if personGroupId == 'visitor':
        path_to_face_api_add_face = '/face/v1.0/largepersongroups/'+personGroupId+'/persons/'+personId+'/persistedFaces'
    with open(person_path, 'rb') as f:
        img_data = f.read()
    try:
        response = requests.post(uri_base + path_to_face_api_add_face,
                                data=img_data, 
                                headers=stream_headers,
                                params=params)
        parsed = response.json()
        print(parsed)
        print("add person face RESPONSE:" + str(response.status_code))
        # if response.status_code == 200:
        #     sql = "INSERT INTO persistedface_table (persistedFaceId, fileName, personId) VALUES (?,?,?)"
        #     cursor.execute(sql, parsed['persistedFaceId'], person_path, personId)
        #     cursor.commit()
    except Exception as e:
        print(e)
def train_PersonGroup(personGroupId):

    path_to_face_api_train_group = '/face/v1.0/persongroups/' + personGroupId+'/train'
    if personGroupId == 'visitor':
        path_to_face_api_train_group = '/face/v1.0/largepersongroups/' + personGroupId+'/train'
    try:
        response = requests.post(uri_base + path_to_face_api_train_group, headers=simple_headers)
        if response.status_code == 202:
            print("Trained group successuflly")
    except Exception as e:
        print(e)


def request_face_identify(face_list, personGroupId):
    path_to_face_api = '/face/v1.0/identify'
    # Request Body
    body = dict()
    if personGroupId == 'visitor':
        body["largePersonGroupId"] = personGroupId
    else:
        body["personGroupId"] = personGroupId
    body["faceIds"] = face_list
    body["maxNumOfCandidatesReturned"] = 1 
    body["confidenceThreshold"] = 0.5
    try:
        # REST Call 
        response = requests.post(uri_base + path_to_face_api, json=body, headers=json_headers)
        responseJson = response.json()
        print(responseJson)
        if not responseJson:
            print("not found matched person id")
            return []
        return responseJson
            
    except Exception as e:
        print(e)
        print("Could not identify the face")
        return []

def detect_person(personGroupId, personId):
    # Request URL 
    path_to_face_api = '/face/v1.0/persongroups/'+personGroupId+'/persons/'+personId
    if personGroupId == 'visitor':
        path_to_face_api = '/face/v1.0/largepersongroups/'+personGroupId+'/persons/'+personId

    try:
        response = requests.get(uri_base + path_to_face_api, headers=simple_headers) 
        responseJson = response.json()
        if not responseJson:
            print("not found matched person")
            return ""
        print("This is "+str(responseJson["name"]))
        return responseJson["name"]
        
    except Exception as e:
        print(e)
        return ""
def get_group_list():
    path_to_face_api = '/face/v1.0/persongroups'
    group_list = []
    try:
        response = requests.get(uri_base + path_to_face_api, headers=simple_headers) 
        responseJson = response.json()
        if not responseJson:
            print("Group list isn't exist")
            return []
        for group in responseJson:
            group_list.append(group['personGroupId'])
        return group_list
    except Exception as e:
        print(e)
        return []

def get_largegroup_list():
    path_to_face_api = '/face/v1.0/largepersongroups'
    group_list = []
    try:
        response = requests.get(uri_base + path_to_face_api, headers=simple_headers) 
        responseJson = response.json()
        if not responseJson:
            print("Large Group list isn't exist")
            return []
        for group in responseJson:
            group_list.append(group['largePersonGroupId'])
        return group_list
    except Exception as e:
        print(e)
        return []

def face_identify():
    person_sql = "select PersonName from face_tbl where PersonName IS NOT NULL group by PersonName"
    persons = cursor.execute(person_sql).fetchall()
    for person in persons:
        sql = "select top 10 faceId, fileName, faceRectangle from face_tbl where PersonName = ? order by faceBlurValue"
        top10_faceIds = cursor.execute(sql, str(person[0])).fetchall()
        faceId_list = []
        fileName_list = []
        faceRectangle_list = []
        for faceId in top10_faceIds:
            faceId_list.append(faceId[0])
            fileName_list.append(faceId[1])
            faceRectangle_list.append(faceId[2])

        detected_group = ""
        flag = False
        for group in group_list:
            responses = request_face_identify(faceId_list, group)
            for i, response in enumerate(responses):
                print(response)
                image_path = os.path.join(image_folder_path, fileName_list[i])
                faceRectangle = faceRectangle_list[i]
                if response['candidates']:
                    personId = response['candidates'][0]['personId']
                    confidence = response['candidates'][0]['confidence']
                    personName = detect_person(group, personId)
                    add_person_face(group,  personName, personId, image_path, faceRectangle)
                    cursor.execute("UPDATE face_tbl SET GroupName = ? WHERE PersonName = ?", group, personName)
                    print(confidence)
                    flag = True
        if flag:
            continue
        for largegroup in largegroup_list:
            responses = request_face_identify(faceId_list, largegroup)
            for i, response in enumerate(responses):
                print(response)
                image_path = os.path.join(image_folder_path, fileName_list[i])
                faceRectangle = faceRectangle_list[i]
                if response['candidates']:
                    personId = response['candidates'][0]['personId']
                    confidence = response['candidates'][0]['confidence']
                    personName = detect_person(largegroup, personId)
                    cursor.execute("UPDATE face_tbl SET GroupName = ? WHERE PersonName = ?", largegroup, personName)
                    print(confidence)
                    add_person_face(largegroup,  personName, personId, image_path, faceRectangle)
                
                else:
                    personId = create_Person(largegroup, person[0], image_path)
                    add_person_face(largegroup, person[0], personId, image_path, faceRectangle)

def process_flow(image_path):
    face_detect(image_path)
    face_group()
    face_identify()
    for group in group_list:
        train_PersonGroup(group)
    for group in largegroup_list:
        train_PersonGroup(group)

group_list = get_group_list()
largegroup_list = get_largegroup_list()
print(group_list)
print(largegroup_list)
image_folder_path = sys.argv[1]
process_flow(image_folder_path) 
cnxn.commit()
cnxn.close()
