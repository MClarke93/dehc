'''The script that exports data from the CouchDB database to \csv.'''

import argparse
import ast
import csv
import os.path
import sys

import mods.database as md

# ----------------------------------------------------------------------------

DBVERSION = "20211130"
parser = argparse.ArgumentParser(description='Exports data from the DEHC database to \\csv.')
parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
parser.add_argument('-d','--dele', help="if included, deletes the files from the existing database before importing", action='store_true')
parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
# '-h' brings up help
parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
parser.add_argument('-D','--drop', help="if included, drops databases instead of deleting files from them; requires -d too", action='store_true')
parser.add_argument('-N','--ndir', type=str, default="csv", help="the directory to import the csv files from", metavar="NAME")
parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
args = parser.parse_args()

BASEDIR = args.ndir

db = md.DEHCDatabase(config=args.auth, version=args.vers, forcelocal=args.forc, level="INFO", namespace=args.name, overridedbversion=args.ovdb, schema=args.sche, quickstart=False)
db.schema_load(schema=args.sche)
if args.dele == True:
    if args.drop == True:
        db.databases_delete(lazy=True)
    else:
        db.databases_clear(lazy=True)
db.databases_create(lazy=True)
db.schema_save()


def read_csv(filename: str):
    filepath = os.path.join(BASEDIR, f"{filename}.csv")
    with open(filepath, 'r', newline='') as f:
        reader = csv.DictReader(f=f)
        return [row for row in reader]


print("Importing items...")
for cat in db.schema_cats():
    address = f"items-{cat}"
    if os.path.isfile(os.path.join(BASEDIR, address+".csv")):
        schema = db.schema_schema(cat=cat)
        eval_fields = [field for field, value in schema.items() if value.get('type','') == 'list' and value.get('source','') == 'IDS']
        docs = read_csv(address)
        ids = []
        for doc in docs:
            id = doc.pop('_id')
            for field in eval_fields:
                if doc.get(field,'') != '':
                    doc[field] = ast.literal_eval(doc[field])
            if "Locked" in doc:
                if doc["Locked"] == "1":
                    doc["Locked"] = 1
                else:
                    doc["Locked"] = 0
            ids.append(id)
        db.items_create(cat=cat, docs=docs, ids=ids)

print("Importing containers...")
if os.path.isfile(os.path.join(BASEDIR, "containers.csv")):
    docs = read_csv("containers")
    for doc in docs:
        db.container_add(container=doc['container'], item=doc['child'])

print("Importing physical IDs...")
db.index_prepare()
if os.path.isfile(os.path.join(BASEDIR, "ids.csv")):
    docs = read_csv("ids")
    physid_dict = {}
    for doc in docs:
        item = doc["item"]
        if item not in physid_dict:
            physid_dict[item] = []
        physid_dict[item].append(doc["physid"])
    for item in physid_dict.keys():
        db.ids_edit(item=item, ids=physid_dict[item])

print("Importing photos...")
if os.path.isfile(os.path.join(BASEDIR, "files.csv")):
    docs = read_csv("files")
    for doc in docs:
        db.photo_save_base64(item=doc['item'], img=doc['photo'])

sys.exit(0)