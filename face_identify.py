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

def create_Person(personGroupId, person_dir, person_path):
    body = dict()
    body["name"] = person_dir
    body["userData"] = "this person is " + person_dir
    #Request URL 
    path_to_face_api_person = '/face/v1.0/persongroups/'+personGroupId+'/persons'

    try:
        # REST Call 
        response = requests.post(uri_base + path_to_face_api_person, headers=json_headers,json=body)
        print("RESPONSE:" + str(response.status_code))
        parsed = response.json()
        if response.status_code == 200:
            sql = "INSERT INTO person_tbl (name, userData, personId, groupId) VALUES (?,?,?,?)"
            cursor.execute(sql, body["name"], body["userData"], parsed["personId"], personGroupId)
            cursor.commit()
        return parsed["personId"]
    except Exception as e:
        print(e)
        return ""
def add_person_face(personGroupId, personName, personId, person_path):
    params = {
        'userData': personName,
        'detectionModel': 'detection_02',
        }
    path_to_face_api_add_face = '/face/v1.0/persongroups/'+personGroupId+'/persons/'+personId+'/persistedFaces'
    with open(person_path, 'rb') as f:
        img_data = f.read()
    try:
        response = requests.post(uri_base + path_to_face_api_add_face,
                                data=img_data, 
                                headers=stream_headers,
                                params=params)
        parsed = response.json()
        if response.status_code == 200:
            sql = "INSERT INTO persistedface_table (persistedFaceId, fileName, personId) VALUES (?,?,?)"
            cursor.execute(sql, parsed['persistedFaceId'], person_path, personId)
            cursor.commit()
    except Exception as e:
        print(e)
def train_PersonGroup(personGroupId):
    path_to_face_api_train_group = '/face/v1.0/persongroups/' + personGroupId+'/train'
    try:
        response = requests.post(uri_base + path_to_face_api_train_group, headers=simple_headers)
        if response.status_code == 202:
            print("Trained group successuflly")
    except Exception as e:
        print(e)

def face_detect(file_path):
    print(file_path)
    path_to_face_api = '/face/v1.0/detect'
    with open(file_path, 'rb') as f:
        img_data = f.read()
    
    params = {'returnFaceId': 'true','recognitionModel':'recognition_02'}

    try:
        response = requests.post(uri_base + path_to_face_api, data=img_data, headers=stream_headers, params=params)
        if response.status_code == 200:
            parsed = response.json()
            if not parsed:
                print("not found any face")
                return ""
            return parsed[0]['faceId']
        return ""
    except Exception as e:
        print('Error:')
        print(e)
        return ""

def face_identify(face_list, personGroupId):
    path_to_face_api = '/face/v1.0/identify'
    # Request Body
    body = dict()
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
            return ""
        if not responseJson[0]["candidates"]:
            print("not found matched person id")
            return ""
        personId = responseJson[0]["candidates"][0]["personId"]
        confidence = responseJson[0]["candidates"][0]["confidence"]
        print("PERSON ID: "+str(personId)+ ", CONFIDENCE :"+str(confidence))
        return personId
            
    except Exception as e:
        print(e)
        print("Could not identify the face")
        return ""

def detect_person(personGroupId, personId):
    # Request URL 
    path_to_face_api = '/face/v1.0/persongroups/'+personGroupId+'/persons/'+personId

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
group_list = get_group_list()
print(group_list)
def process_flow(image_path):
    faceId = face_detect(image_path)
    if faceId == "":
        return
    personId = ""
    detected_group = ""
    for group in group_list:
        personId = face_identify([faceId], group)
        if personId != "":
            personName = detect_person(group, personId)
            detected_group = group
            add_person_face(detected_group,  personName, personId, image_path)
            train_PersonGroup(detected_group)
            break
    if personId == "":
        personGroupId = 'visitor'
        personId = create_Person(personGroupId, image_path, image_path)
        add_person_face(personGroupId, image_path, personId, image_path)
        train_PersonGroup(personGroupId)
image_path = sys.argv[1]
process_flow(image_path)
cnxn.commit()
cnxn.close()

