'''The script that starts the main DEHC application.'''

import argparse
import sys

#import apps.ems as ae
import mods.database as md
import mods.log as ml

#import mods.dehc_hardware as hw

import mariadb
import sys

from pprint import pprint
import time
from datetime import datetime

# ----------------------------------------------------------------------------

DBVERSION = "RC1"

def count_people(indata):
    total_people = 0
    for data in indata:
        #print(type(data))
        #pprint.pprint(data)
        if data[0:6] == "Person":
            total_people += 1
    return total_people

def list_people(indata,result_list):
    for data in indata:
        #print(type(data))
        #pprint.pprint(data)

        if data[0:6] == "Person":
            result_list.append(data)
    #return  result_list

if __name__ == "__main__": # Multiprocessing library complains if this guard isn't used

    parser = argparse.ArgumentParser(description='Starts the Digital Evacuation Handling Center')
    parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
    parser.add_argument('-b','--book', type=str, default="bookmarks.json", help="relative path to EMS screen bookmarks", metavar="PATH")
    parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
    parser.add_argument('-O','--ovdb', help="if included, Overrides database version detection, development only, you will lose data", action='store_true')
    # '-h' brings up help
    parser.add_argument('-l','--logg', type=str, default="DEBUG", help="minimum level of logging messages that are printed: DEBUG, INFO, WARNING, ERROR, CRITICAL, or NONE", choices=["DEBUG","INFO","WARNING","ERROR","CRITICAL","NONE"], metavar="LEVL")
    parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
    parser.add_argument('-r','--read', help="if included, opens the app in read-only mode", action='store_true')
    parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
    parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
    parser.add_argument('-m','--mysqlserv', type=str, default="127.0.0.1", help="Mysql Server", metavar="mysqlserv")    

    args = parser.parse_args()

    # ----------------------------------------------------------------------------

    logger = ml.get(name="Main", level=args.logg)
    logger.debug("Monitoring has started.")
    db = md.DEHCDatabase(config=args.auth, version=args.vers,overridedbversion=args.ovdb, forcelocal=args.forc, level=args.logg, namespace=args.name, schema=args.sche, quickstart=True)

 #quit()
    # Connect to MariaDB Platform
    try:
        conn = mariadb.connect(
            user="dehc_admin",
            password="Creative",
            host=args.mysqlserv,
            port=3306,
            database="vps_dehc"
        )
        print("Mariadb Connected")
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)

    # Get Cursor
    cursor = conn.cursor()

    all_containers = db.container_children_all(db.items_query(cat="Evacuation")[0]['_id'])
    #pprint.pprint(all_containers)
    total_count = count_people(all_containers)
    print()
    stations = db.items_list(cat="Station")
    #pprint.pprint(stations)
    containers_current_people = {}
    monitored_containter_types = ["Station","Vessel","Lane"]    
    while True:
        airside = db.items_query(cat="Station", selector={'Display Name': {'$eq':'5. Airside'}}, fields=["_id"])[0]["_id"] #fun times, get this each loop so when the db is restarted it just rolls with it.
        vessels = db.container_children_all(airside,cat="Vessel",result="DOC")
        
        print("Vessels in Airside")
        cursor.execute("DELETE FROM vessel_stats") #OUT WITH THE OLD
        for vessel in vessels:
            #pprint(vessel)
            cap_soul = 0
            if "Capacity (Souls)" in vessel: #not all vessels have capacity listed
                if vessel["Capacity (Souls)"].isnumeric():
                    cap_soul = vessel["Capacity (Souls)"] # not all listings are numbers

            souls = len(db.container_children_all(vessel["_id"],cat="Person") )

            print(vessel["_id"] + " " + vessel["Display Name"] + " " + str(souls) + " of " + str(cap_soul))
            
                
            cursor.execute(
            "INSERT INTO vessel_stats (record_time,container_id,display_name,max_souls,current_souls) VALUES (now(),?,?,?,?)",
            (vessel["_id"],vessel['Display Name'],cap_soul,souls))
            
        conn.commit()

#        quit()
        #all_containers = db.container_children_all_dict(db.items_query(cat="Evacuation")[0]['_id'])
        #pprint.pprint(all_containers)
        #total_count = count_people(all_containers)
        #print()
        print("Time %s "  % (datetime.now()))
        for containter_type in monitored_containter_types:
            stations = db.items_list(cat=containter_type)
            print("Station type %s" %  containter_type)
            for station in stations:

                containers = db.container_children_all(station['_id'])
                #cont_ppl = count_people(containers)
                id_list = [] #note this is passed to and mucked with by the list_people function
                ppl_leaving = 0
                ppl_entering = 0
                list_people(containers,id_list) #note id_list is passed to and mucked with by the list_people function, recusion baby
                if station['_id'] not in containers_current_people:
                    containers_current_people[station['_id']] = list()
                else:
                    #need to skip counting everybody as entering on the first run through
                    for current_person in containers_current_people[station['_id']]:
                        if current_person not in id_list:
                            print("Leaving : " + current_person)
                            ppl_leaving += 1

                    for current_person in id_list:
                        if current_person not in containers_current_people[station['_id']]:
                            print("Entering : " + current_person)
                            ppl_entering += 1

                containers_current_people[station['_id']] = id_list

                cont_ppl = len(id_list)
                #pprint.pprint(id_list)
                print("Id %s Name : %s Qty %s : Enter %s : Leave %s" % (station['_id'], station['Display Name'], cont_ppl,ppl_entering,ppl_leaving))

                try:
                    cursor.execute(
                    "INSERT INTO container_stats (record_time,container_type,container_id,container_name,item_total,items_in,items_out) VALUES (now(),?,?,?,?,?,?)",
                    (containter_type,station['_id'],station['Display Name'],cont_ppl,ppl_entering,ppl_leaving))
                except mariadb.Error as e:
                    print(f"Error: {e}")
            conn.commit()

            # update vessels currently in airside


        time.sleep(60)
        #input()