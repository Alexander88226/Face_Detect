import requests

import pyodbc
import json
import os
import sys
import time
cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=DESKTOP-7F2VT38\SQLEXPRESS;"
                      "Database=Face_DB;"
                      "Trusted_Connection=yes;")
cursor = cnxn.cursor()
CREATE_GROUP_TABLE_SQL = '''IF  NOT EXISTS (SELECT * FROM sys.objects 
    WHERE object_id = OBJECT_ID(N'[dbo].[group_tbl]') AND type in (N'U'))
    CREATE TABLE [dbo].[group_tbl](
        [id] [int] IDENTITY(1,1) NOT NULL,
        [name] [nvarchar](50) NULL,
        [userData] [text] NULL,
        [personGroupId] [varchar](50) NULL
    ) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]'''
cursor.execute(CREATE_GROUP_TABLE_SQL)

CREATE_PERSON_TABLE_SQL = '''IF NOT EXISTS (SELECT * FROM sys.objects 
    WHERE object_id = OBJECT_ID(N'[dbo].[person_tbl]') AND type in (N'U'))
    CREATE TABLE [dbo].[person_tbl](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[name] [varchar](50) NULL,
	[userData] [text] NULL,
	[personId] [varchar](50) NULL,
	[groupId] [varchar](50) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]'''
cursor.execute(CREATE_PERSON_TABLE_SQL)

CREATE_PERSISTEDFACE_TABLE_SQL = '''IF NOT EXISTS (SELECT * FROM sys.objects 
    WHERE object_id = OBJECT_ID(N'[dbo].[persistedface_tbl]') AND type in (N'U'))
    CREATE TABLE [dbo].[persistedface_tbl](
	[persistedFaceId] [varchar](50) NULL,
	[fileName] [text] NULL,
	[personId] [varchar](50) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
'''
cursor.execute(CREATE_PERSISTEDFACE_TABLE_SQL)


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
# https://westeurope.api.cognitive.microsoft.com/face/v1.0/persongroups/
valid_images = [".jpg",".bmp",".png", ".jpeg"]

image_root_path = sys.argv[1]

def create_PersonGroup(path):

    subdirs = [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]
    for group_name in subdirs:

        personGroupId = group_name.lower()

        json = {'name' : group_name, 'userData':"this group is " + group_name + " Group", 'recognitionModel':'recognition_02'}
        #Request URL 
        path_to_face_api_group = '/face/v1.0/persongroups/'+personGroupId
        if personGroupId == "visitor":
            path_to_face_api_group = '/face/v1.0/largepersongroups/'+personGroupId

        try:
            # REST Call 
            response = requests.put(uri_base + path_to_face_api_group, headers=json_headers,json=json)
            print("RESPONSE:" + str(response.status_code))
            if response.status_code == 200:
                sql = "INSERT INTO group_tbl (name, userData, personGroupId) VALUES (?,?,?)"
                cursor.execute(sql, group_name, json["userData"], personGroupId)
                cursor.commit()

            group_path = os.path.join(path, group_name)
            person_dirs = [name for name in os.listdir(group_path) if os.path.isdir(os.path.join(group_path, name))]
            for person_dir in person_dirs:
                person_path = os.path.join(group_path, person_dir)
                create_Person(personGroupId, person_dir, person_path)
        except Exception as e:
            print(e)

def create_Person(personGroupId, person_dir, person_path):
    body = dict()
    body["name"] = person_dir
    body["userData"] = "this person is " + person_dir
    #Request URL 
    path_to_face_api_person = '/face/v1.0/persongroups/'+personGroupId+'/persons'
    if personGroupId == "visitor":
        path_to_face_api_person = '/face/v1.0/largepersongroups/'+personGroupId+'/persons'


    try:
        # REST Call 
        response = requests.post(uri_base + path_to_face_api_person, headers=json_headers,json=body)
        print("RESPONSE:" + str(response.status_code))
        parsed = response.json()
        if response.status_code == 200:
            sql = "INSERT INTO person_tbl (name, userData, personId, groupId) VALUES (?,?,?,?)"
            cursor.execute(sql, body["name"], body["userData"], parsed["personId"], personGroupId)
            cursor.commit()
        time.sleep(1)

        add_person_face(personGroupId, person_dir, parsed["personId"], person_path)
    except Exception as e:
        print(e)
def add_person_face(personGroupId, personName, personId, person_path):
    params = {
        'userData': personName,
        'detectionModel': 'detection_02',
        }
    path_to_face_api_add_face = '/face/v1.0/persongroups/'+personGroupId+'/persons/'+personId+'/persistedFaces'
    if personGroupId == "visitor":
        path_to_face_api_add_face = '/face/v1.0/largepersongroups/'+personGroupId+'/persons/'+personId+'/persistedFaces'

    for file in os.listdir(person_path):
        ext = os.path.splitext(file)[1]
        if ext.lower() in valid_images:
            file_path = os.path.join(person_path, file)
            with open(file_path, 'rb') as f:
                img_data = f.read()
            try:
                response = requests.post(uri_base + path_to_face_api_add_face,
                                        data=img_data, 
                                        headers=stream_headers,
                                        params=params)
                parsed = response.json()
                if response.status_code == 200:
                    sql = "INSERT INTO persistedface_tbl (persistedFaceId, fileName, personId) VALUES (?,?,?)"
                    cursor.execute(sql, parsed['persistedFaceId'], file, personId)
                    cursor.commit()
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

create_PersonGroup(image_root_path)

rows = cursor.execute("SELECT * FROM group_tbl").fetchall()
for row in rows:
    train_PersonGroup(row[3])

cnxn.commit()
cnxn.close()
