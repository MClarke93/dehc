import argparse
import base64
import copy
import json
import sys
import time
import uuid

import ibm_cloud_sdk_core
from ibm_cloud_sdk_core import api_exception
from ibmcloudant import CouchDbSessionAuthenticator
from ibmcloudant.cloudant_v1 import CloudantV1

# -----------------

parser = argparse.ArgumentParser(description='sets up repliaction from central server to local machine.')
parser.add_argument('-f','--force', help="if included, skips any 'Are you sure?' dialogs during running", action="store_true")
parser.add_argument('-l','--localauth', type=str, default="db_auth.json", help="relative path to database authentication file for the local db", metavar="LOCALPATH")
parser.add_argument('-r','--remoteauth', type=str, default=None, help="relative path to database authentication file for the remote db, if different to local", metavar="REMOTEPATH")
parser.add_argument('-n','--localname', type=str, default="dehc", help="local database namespace to use", metavar="NAME")
parser.add_argument('-p','--remotename', type=str, default=None, help="remote database namespace to use, if different to local", metavar="NAME")

args = parser.parse_args()

localauth = args.localauth
with open(localauth, "r") as f:
    localdata = json.loads(f.read())
localname = args.localname
localusername = localdata["user"]
localpass = localdata["pass"]
localserver = localdata["url"]

remoteauth = args.remoteauth if args.remoteauth != None else localauth
with open(remoteauth, "r") as f:
    remotedata = json.loads(f.read())
remotename = args.remotename if args.remotename != None else localname
remoteusername = remotedata["user"]
remotepass = remotedata["pass"]
remoteserver = remotedata["url"]

dblist = ["items", "containers", "configs", "ids", "files"]

# -----------------

def add_replication(dbcon, source_host, source_user, source_pass, source_db, destination_host, destination_user, destination_pass, destination_db, owner):
    print(f"Replicating from db {source_db} @ {source_host} to db {destination_db} @ {destination_host}")

    replication_json_dict = {
        '_id': '.',
        "user_ctx": {
            "name": "admin",
            "roles": [
            "_admin",
            "_reader",
            "_writer"
            ]},        
        'source': {
            'url': '.',
            'headers': {
                'Authorization': '.'
            }
        },
        'target': {
            'url': '.',
            'headers': {
                'Authorization': '.'
            }
        },
        'create_target': 'true',
        'continuous': 'true',
        'owner': 'admin'
    }

    replication_doc = copy.deepcopy(replication_json_dict)

    replication_doc['_id'] = "auto_" + str(uuid.uuid1())
    replication_doc['source']['url'] = source_host + "/" + source_db
    replication_doc['source']['headers']['Authorization'] = 'Basic ' + base64.b64encode((source_user+':'+source_pass).encode()).decode()
    replication_doc['target']['url'] = destination_host + "/" + destination_db
    replication_doc['target']['headers']['Authorization'] = 'Basic ' + base64.b64encode((destination_user+':'+destination_pass).encode()).decode()
    replication_doc['create_target'] = True
    replication_doc['continuous'] = True
    replication_doc['owner'] = owner

    try:
        dbcon.put_document(db='_replicator', doc_id=replication_doc['_id'], document=json.dumps(replication_doc))
    except ibm_cloud_sdk_core.api_exception.ApiException as err:
        if err.code == 409:
            print('Replication document already exists')
        else:
            print('Unhandled exception...')
            print(err)

# -----------------

if __name__ == "__main__":
    local_auth = CouchDbSessionAuthenticator(username=localusername, password=localpass)
    local_couchdb_connection = CloudantV1(authenticator=local_auth)
    local_couchdb_connection.set_service_url(localserver)
    local_info = local_couchdb_connection.get_all_dbs().get_result()

    if args.force == False:
        print(f"\nTHIS SCRIPT WILL OVERWRITE ALL DATA STORED AT {localname} @ {localserver}. ARE YOU SURE YOU WANT TO CONTINUE?")
        confirm = input("ENTER \"YES\" IN CAPS TO CONFIRM: ")
    else:
        confirm = "YES"

    if confirm == "YES":
        print(f'\nSetting up replication between {localname} @ {localserver} and {remotename} @ {remoteserver}')  
        
        for working_database in dblist:
            local_database = localname + "-" + working_database
            remote_database = remotename + "-" + working_database
            try:
                local_couchdb_connection.delete_database(db=local_database)
                print(f"Deleted local db {local_database} successfully")
            except:
                print(f"Could not delete local db {local_database}")

            add_replication(dbcon=local_couchdb_connection, 
            source_host=remoteserver, 
            source_user=remoteusername, 
            source_pass=remotepass, 
            source_db=remote_database, 
            destination_host=localserver, 
            destination_user=localusername, 
            destination_pass=localpass, 
            destination_db=local_database, 
            owner=localusername)
            time.sleep(1)

        for working_datbase in dblist:
            local_database = localname + "-" + working_database
            remote_database = remotename + "-" + working_database

            add_replication(dbcon=local_couchdb_connection, 
            source_host=localserver, 
            source_user=localusername, 
            source_pass=localpass, 
            source_db=local_database, 
            destination_host=remoteserver, 
            destination_user=remoteusername, 
            destination_pass=remotepass, 
            destination_db=remote_database, 
            owner=localusername)
            time.sleep(1)

        print(f'Done setting up replication between {localname} @ {localserver} and {remotename} @ {remoteserver}\n') 

    else:
        print("EXITING...")   

    sys.exit(0)
