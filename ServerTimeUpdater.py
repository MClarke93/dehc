#import json
#import ibm_cloud_sdk_core
#from ibm_cloud_sdk_core import api_exception
#from ibmcloudant import CouchDbSessionAuthenticator
#from ibmcloudant.cloudant_v1 import BulkDocs, CloudantV1, Document, ReplicationDatabase, ReplicationDatabaseAuth, ReplicationDatabaseAuthIam, ReplicationDocument
import argparse  
import datetime
import time
import mods.database as md

DBVERSION = "RC1"
parser = argparse.ArgumentParser(description='Starts the Digital Evacuation Handling Center')
parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
parser.add_argument('-b','--book', type=str, default="bookmarks.json", help="relative path to EMS screen bookmarks", metavar="PATH")
parser.add_argument('-l','--logg', default="DEBUG", help="minimum level of logging messages that are printed: DEBUG, INFO, WARNING, ERROR, CRITICAL, or NONE", choices=["DEBUG","INFO","WARNING","ERROR","CRITICAL","NONE"], metavar="LEVL")
parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
parser.add_argument('-w','--weba', type=str, default="web_auth.json", help="relative path to web server authentication file", metavar="PATH")
parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
args = parser.parse_args()

localusername = "admin"
localpass = "Creative"
localserver = "http://127.0.0.1:5984/"
level=args.logg
config=args.auth
namespace=args.name 
db = md.Database(config=config, level=level)

print("DBTime Updater running")

if __name__ == "__main__":
    db_name = namespace + "-configs"
    db.document_delete(db_name,"timecheck", lazy=True)
    newtime = datetime.datetime.now().replace(microsecond=0).isoformat()
    doc = {"Server Time": newtime}
    time_check_doc = db.document_create(db_name,doc,"timecheck") 
    time.sleep(3)
    while True:
        newtime = datetime.datetime.now().replace(microsecond=0).isoformat()
        doc = {"Server Time": newtime}
        db.document_edit(db_name,doc,"timecheck",lazy=True)
        time.sleep(10)