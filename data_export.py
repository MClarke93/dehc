'''The script that exports data from the CouchDB database to \csv.'''

import argparse
import csv
import os
import os.path
import sys

import mods.database as md

# ----------------------------------------------------------------------------

DBVERSION = "211020B"
parser = argparse.ArgumentParser(description='Exports data from the DEHC database to \\csv.')
parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
# '-h' brings up help
parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
parser.add_argument('-N','--ndir', type=str, default="csv", help="the directory to export the csv files to", metavar="NAME")
parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
args = parser.parse_args()


db = md.DEHCDatabase(config=args.auth, version=args.vers, forcelocal=args.forc, level="INFO", namespace=args.name, overridedbversion=args.ovdb, schema=args.sche, quickstart=False)
db.schema_load(schema=args.sche)

BASEDIR = args.ndir


def write_csv(filename: str, docs: list, keys: list):
    filepath = os.path.join(BASEDIR, f"{filename}.csv")
    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f=f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(docs)


os.mkdir(BASEDIR)

print("Exporting items...")
for cat in db.schema_cats():
    docs = db.items_list(cat=cat)
    schema = db.schema_schema(cat=cat)
    fields = [
        field for field, value in schema.items() 
        if value.get('type','') not in ['sum', 'count'] 
        and value.get('source','') != "PHYSIDS"
    ]
    keys = ['_id']+fields 
    write_csv(filename=f"items-{cat}", docs=docs, keys=keys)

print("Exporting containers...")
docs = db.containers_list()
docs = [doc for doc in docs if "container" in doc and "child" in doc]
keys = ["container", "child"]
write_csv(filename="containers", docs=docs, keys=keys)

print("Exporting physical IDs...")
docs = db.ids_list()
docs = [doc for doc in docs if "item" in doc and "physid" in doc]
keys = ["item", "physid"]
write_csv(filename="ids", docs=docs, keys=keys)

print("Exporting photos...")
docs = db.photos_list()
docs = [doc for doc in docs if "item" in doc and "photo" in doc]
keys = ["item", "photo"]
write_csv(filename="files", docs=docs, keys=keys)

print("Done exporting")
sys.exit(0)