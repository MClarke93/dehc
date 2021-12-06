'''The script that starts the main DEHC application.'''

import argparse
import sys

if sys.version_info.major == 3 and sys.version_info.minor == 9:
    import apps.baggage as ab
    import apps.ems as ae
    import apps.marshal as am
    import apps.timetable as at
    import mods.database as md
    import mods.log as ml
    import mods.dehc_hardware as hw
else:
    print("This application must be run using Python 3.9.X")
    sys.exit(1)

# ----------------------------------------------------------------------------

if __name__ == "__main__": # Multiprocessing library complains if this guard isn't used
    
    DBVERSION = "20211131"
    parser = argparse.ArgumentParser(description='Starts the Digital Evacuation Handling Center')
    parser.add_argument('app', nargs="?", default="EMS", help="which app to start: EMS, GC, TT or PB", choices=['EMS', 'GC', 'TT', 'PB'], metavar="APP")
    parser.add_argument('arg', nargs="?", default="", help="if app is GC, this specifies the vessel to gatecheck. If the app is TT, this specifies the container to look for vessels in. If the app is PB, this specifies the container to look for bags in", metavar="ARG")
    parser.add_argument('arg2', nargs="?", default="", help="if the app is PB, this specifies the container to move bags to", metavar="ARG")
    parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
    parser.add_argument('-b','--book', type=str, default="bookmarks.json", help="relative path to EMS screen bookmarks", metavar="PATH")
    parser.add_argument('-f','--forc', help="if included, forces the app to use the local copy of the database schema", action='store_true')
    parser.add_argument('-g','--godm', help="if included, opens the app in administrative mode", action='store_true')
    # '-h' brings up help
    parser.add_argument('-l','--logg', default="INFO", help="minimum level of logging messages that are printed: DEBUG, INFO, WARNING, ERROR, CRITICAL, or NONE", choices=["DEBUG","INFO","WARNING","ERROR","CRITICAL","NONE"], metavar="LEVL")
    parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
    parser.add_argument('-r','--read', help="if included, opens the app in read-only mode", action='store_true')
    parser.add_argument('-s','--sche', type=str, default="db_schema.json", help="relative path to database schema file", metavar="PATH")
    parser.add_argument('-u','--upda', help="if included, the app will save the loaded schema to the database during quickstart", action='store_true')
    parser.add_argument('-v','--vers', type=str, default=DBVERSION, help="schema version to expect", metavar="VERS")
    parser.add_argument('-w','--weba', type=str, default="web_auth.json", help="relative path to web server authentication file", metavar="PATH")
    parser.add_argument('-x','--xgui', help="if included, the gui won't be started", action='store_true')
    parser.add_argument('-H','--Hardware', help="if included, disables all hardware functionality", action='store_false')
    parser.add_argument('-HB','--HBarcode', help="if included, decactivates barcode scanner functionality", action='store_false')
    parser.add_argument('-HN','--HNFC', help="if included, decactivates NFC reader functionality", action='store_false')
    parser.add_argument('-HP','--HPrinter', help="if included, decactivates printer functionality", action='store_false')
    parser.add_argument('-HS','--HScale', help="if included, decactivates scale functionality", action='store_false')
    parser.add_argument('-O','--ovdb', help="if included, disables database version detection. Use with caution, as it may result in lost data", action='store_true')
    args = parser.parse_args()

    # ----------------------------------------------------------------------------

    logger = ml.get(name="Main", level=args.logg)
    logger.info("Application has started")

    if args.forc == True:
        logger.warning(f"Application will load schema from '{args.auth}' save it to the database")

    db = md.DEHCDatabase(config=args.auth, version=args.vers, forcelocal=args.forc, level=args.logg, namespace=args.name, overridedbversion=args.ovdb, schema=args.sche, updateschema=args.upda, quickstart=True)

    if args.app == "EMS":
        hardware = None
        try:
            if args.Hardware == True:
                hardware = hw.Hardware(makeNFCReader=args.HNFC, makeBarcodeReader=args.HBarcode, makePrinter=args.HPrinter, makeScales=args.HScale)
            else:
                hardware = hw.Hardware(makeNFCReader=False, makeBarcodeReader=False, makePrinter=False, makeScales=False)
        except RuntimeError: #TODO: determine if this is still valid, since __main__ check
            pass

        if args.xgui == False:
            if args.read == True:
                logger.warning("EMS application is starting in read-only mode")
            ae.EMS(db=db, bookmarks=args.book, godmode=args.godm, level=args.logg, readonly=args.read, web=args.weba, autorun=True, hardware=hardware)

        if hardware is not None:
            hardware.terminateProcesses()
    
    elif args.app == "GC":
        if args.arg != "":
            if args.xgui == False:
                am.GC(db=db, vessel=args.arg, level=args.logg, autorun=True)
        else:
            logger.critical("The vessel to be gatechecked must be specified")

    elif args.app == "TT":
        if args.arg != "":
            if args.xgui == False:
                at.TT(db=db, container=args.arg, level=args.logg, autorun=True)
        else:
            logger.critical("The container to look for vessels in must be specified")
    
    elif args.app == "PB":
        if args.arg != "" and args.arg != "":
            if args.xgui == False:
                ab.PB(db=db, baghold=args.arg, pallet=args.arg2, level=args.logg, autorun=True)
        else:
            logger.critical("The container to look for bags in, and the container to move bags to, must both be specified")

    logger.info("Application is ending")
    sys.exit(0)
