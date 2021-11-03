'''The script that exports data from the CouchDB database.'''

import argparse
import base64
import datetime
import io
import json
import os
import os.path
import sys
import zipfile

from PIL import Image

import mods.database as md

# ----------------------------------------------------------------------------

DBVERSION = "RC1"
parser = argparse.ArgumentParser(description='Exports data from the DEHC database to \\csv.')
parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
# '-h' brings up help
parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
parser.add_argument('-N','--ndir', type=str, default="export", help="the directory to export the database to", metavar="NAME")
parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
args = parser.parse_args()

db = md.DEHCDatabase(config=args.auth, version=args.vers, forcelocal=args.forc, level="INFO", namespace=args.name, overridedbversion=args.ovdb, schema=args.sche, quickstart=False)
db.schema_load(schema=args.sche)


# ----------------------------------------------------------------------------

STARTTIME = str(datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
BASEDIR = args.ndir
ITEMDICT = {}
PHOTODICT = {}
IDDICT = {}
NAMEFIELD = "Display Name"


# TO DO...
# - Dealing with illegal file names (weird characters)


def sanitize_name(name: str):
    new_name = ""
    for letter in name.strip():
        if letter in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-~_()[] ':
            new_name += letter
        else:
            new_name += "_"
    if len(name) > 0:
        return new_name
    else:
        return "_"


def write_json(filepath: str, doc: dict):
    with open(filepath+".json", "w") as f:
        f.write(json.dumps(doc))


def write_txt(filepath: str, docs: list):
    docs = [line+"\n" for line in docs]
    with open(filepath+".txt", "w") as f:
        f.writelines(docs)


def write_jpg(filepath: str, b64: str):
    img = base64.b64decode(b64)
    buffer = io.BytesIO(img)
    img = Image.open(buffer)
    img.save(filepath+".jpg")


def write_odt(template_filepath: str, target_filepath: str, doc: dict, img: str = None):
    try:
        with zipfile.ZipFile(template_filepath+".odt", "r") as zipfin, zipfile.ZipFile(target_filepath+".odt", "w") as zipfout:
            fields = ['_id', 'category', 'flags']+db.schema_fields(cat=doc['category'])
            physid = db.ids_get(item=doc["_id"])
            for info in zipfin.infolist():
                with zipfin.open(info, "r") as f:
                    content = f.read()
                    if info.filename == "content.xml":
                        for field in fields:
                            content = content.replace(bytes(f"##{field}##", encoding='utf8'), bytes(f"{doc.get(field,'')}", encoding='utf8'))
                        content = content.replace(bytes(f"##physid##", encoding='utf8'), bytes(f"{physid}", encoding='utf8'))
                    elif img != None and info.filename.endswith(".jpg"):
                        content = base64.b64decode(img)
                    zipfout.writestr(info.filename, content)
    except FileNotFoundError:
        pass


def create_node(rootpath: str, uuid: str):
    # Obtain the sanitized display name
    name = ITEMDICT[uuid][NAMEFIELD]
    name = sanitize_name(name=name)

    # Create the item's associated directory
    dup = 0
    while True:
        dup += 1
        try:
            dirpath = os.path.join(rootpath, f"{name}{' ('+str(dup)+')' if dup > 1 else ''}")
            os.mkdir(path=dirpath)
        except FileExistsError:
            if dup < 10:
                continue
            else:
                print(f"Unable to export {uuid}.")
                return
        else:
            break

    # Create the item's files within that directory
    print(f"Exporting \"{uuid}\" to \"{dirpath}\"")
    filepath = os.path.join(dirpath, name)
    write_json(filepath=filepath, doc=ITEMDICT[uuid])
    if uuid in IDDICT:
        write_txt(filepath=filepath, docs=IDDICT[uuid])
    if uuid in PHOTODICT:
        img = PHOTODICT[uuid]
        write_jpg(filepath=filepath, b64=img)
        write_odt(template_filepath=os.path.join('templates', ITEMDICT[uuid]['category']), target_filepath=filepath, doc=ITEMDICT[uuid], img=img)
    else:
        write_odt(template_filepath=os.path.join('templates', ITEMDICT[uuid]['category']), target_filepath=filepath, doc=ITEMDICT[uuid])

    # Create the children directories
    children = db.container_children(container=uuid, result="DOC")
    for child in children:
        uuid = child["_id"]
        if uuid not in ITEMDICT:
            ITEMDICT[uuid] = child
            create_node(rootpath=dirpath, uuid=uuid)
        else:
            print(f"Infinite loop detected, as {uuid} already exists.")
            return


# ----------------------------------------------------------------------------

# Find the top of the tree
evacuations = db.items_query(cat="Evacuation")
if len(evacuations) == 1:
    base, = evacuations
else:
    raise RuntimeError("Expected one Evacuation in the database.")

# Prepopulate a list of photos
photos = db.photos_list()
PHOTODICT = {photo["item"]: photo["photo"] for photo in photos if "item" in photo and "photo" in photo}

# Prepopulate a list of physical IDs
physids = db.ids_list()
for physid in physids:
    if "item" in physid and "physid" in physid:
        item = physid["item"]
        id = physid["physid"]
        if item not in IDDICT:
            IDDICT[item] = []
        IDDICT[item].append(id)

# Prepopulate the item list with the top of the tree
base_uuid = base["_id"]
ITEMDICT[base_uuid] = base

# Export the top level files
os.mkdir(BASEDIR)
schemapath = os.path.join(BASEDIR, "schema")
write_json(filepath=schemapath, doc=db.schema)
try:
    timepath = os.path.join(BASEDIR, "timecheck")
    timedoc = db.time_get(doc=True)
    write_json(filepath=timepath, doc=timedoc)
except:
    pass
logpath = os.path.join(BASEDIR, "log")
write_txt(filepath=logpath, docs=["Export initiated at:", STARTTIME])

# Export the item tree
create_node(rootpath=BASEDIR, uuid=base_uuid)

sys.exit(0)
