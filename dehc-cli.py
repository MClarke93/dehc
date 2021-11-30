'''The script that starts the main DEHC application.'''

import argparse
import sys

if sys.version_info.major == 3 and sys.version_info.minor == 9:    
    import mods.database as md
    import mods.log as ml    
else:
    print("This application must be run using Python 3.9.X.")
    sys.exit(1)

# ----------------------------------------------------------------------------

if __name__ == "__main__": # Multiprocessing library complains if this guard isn't used
    
    DBVERSION = "20211131"
    parser = argparse.ArgumentParser(description='DEHC cli tools')
    parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
    parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
    # '-h' brings up help
    parser.add_argument('-l','--logg', type=str, default="DEBUG", help="minimum level of logging messages that are printed: DEBUG, INFO, WARNING, ERROR, CRITICAL, or NONE", choices=["DEBUG","INFO","WARNING","ERROR","CRITICAL","NONE"], metavar="LEVL")
    parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
    parser.add_argument('-r','--read', help="if included, opens the app in read-only mode", action='store_true')
    parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
    parser.add_argument('-u','--upda', help="if included, the app will save the loaded schema to the database during quickstart", action='store_true')
    parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
    parser.add_argument('-w','--weba', type=str, default="web_auth.json", help="relative path to web server authentication file", metavar="PATH")
    parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
    parser.add_argument("command", nargs='?', type=str, help="command to run , rflag -  recursive flag") 
    parser.add_argument("arg1", nargs='?', type=str, help="arg1")    
    parser.add_argument("arg2", nargs='?', type=str, help="arg2")    
    args = parser.parse_args()

    # ----------------------------------------------------------------------------

    logger = ml.get(name="Main", level=args.logg)
    logger.info("Application has started.")

    if args.read == True:
        logger.warning("Application is starting in read-only mode")
    
    if args.forc == True:
        logger.warning(f"Application will load schema from '{args.auth}' save it to the database")

    db = md.DEHCDatabase(config=args.auth, version=args.vers, forcelocal=args.forc, level=args.logg, namespace=args.name, overridedbversion=args.ovdb, schema=args.sche, updateschema=args.upda, quickstart=True)

    #poor mans switch section, replace with match in 3.10
    def rflag():        
        print("Recursivley flagging %s with %s" % (args.arg1,args.arg2))
        db.flag_assign_tree(args.arg1,args.arg2)


    def orphan():
        print("Outputting list of orphaned items to orphans.txt")

        evacuations = db.items_query(cat="Evacuation", fields=["_id", "Display Name"])
        if len(evacuations) == 1:
            base, = evacuations
        else:
            raise RuntimeError("Expected one Evacuation in the database.")

        orphans = [line+"\n" for line in db.orphans_list(container=base["_id"])]
        with open("orphans.txt", "w") as f:
            f.writelines(orphans)


    commands = {"rflag": rflag, "orphan": orphan}
    commands[args.command]()

    logger.info("Application is ending.")
    sys.exit(0)
