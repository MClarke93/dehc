import argparse
import datetime
import json
import logging
import logging.handlers
import sys
import time

from ibmcloudant import CouchDbSessionAuthenticator
from ibmcloudant.cloudant_v1 import CloudantV1

# ----------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Inserts data into the DEHC database.')
parser.add_argument('-a','--auth', type=str, default="db_auth.json", help="relative path to database authentication file", metavar="PATH")
parser.add_argument('-c','--coun', type=int, default=20, help="maximum number of individual log files", metavar="INT")
parser.add_argument('-e','--ever', help="if included, the entire history of existing, past changes will be logged first", action='store_true')
# '-h' brings up help
parser.add_argument('-n','--name', type=str, default="dehc", help="which database namespace to use", metavar="NAME")
parser.add_argument('-p','--poll', type=float, default=2, help="wait time between database pollings in seconds", metavar="FLOAT")
parser.add_argument('-s','--size', type=int, default=1000000, help="maximum filesize of an individual log file in bytes", metavar="INT")
args = parser.parse_args()

# ----------------------------------------------------------------------------

with open(args.auth, "r") as f:
    DATA = json.loads(f.read())
USER      = DATA['user']
PASS      = DATA['pass']
URL       = DATA['url']

NAMESPACE = args.name
DBITEMS   = NAMESPACE+"-items"
DBCONTS   = NAMESPACE+"-containers"
DBIDS     = NAMESPACE+"-ids"
DBFILES   = NAMESPACE+"-files"
DBCONFIGS = NAMESPACE+"-configs"
DATABASES = [DBITEMS, DBCONTS, DBIDS, DBFILES, DBCONFIGS]

LOGTIME   = str(datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S'))
LOGNAME   = f'logs\\changes-{LOGTIME}.log'
LOGSIZE   = args.size  # In bytes
LOGCOUNT  = args.coun  # In files; when exceeded, oldest is replaced
POLLTIME  = args.poll  # In seconds

# ----------------------------------------------------------------------------

auth = CouchDbSessionAuthenticator(USER, PASS)
client = CloudantV1(authenticator=auth)
client.set_service_url(URL)

logger = logging.getLogger('Changes')
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(LOGNAME, maxBytes=LOGSIZE, backupCount=LOGCOUNT)
logger.addHandler(handler)

# This will be used to store the ID of the most recent change in each database 
last = {database: 0 for database in DATABASES}

# If -e wasn't given, query the databases outside of the loop first to obtain latest 'last_seq's
if args.ever == False:
    for database in DATABASES:
        response = client.post_changes(db=database, include_docs=True, since=last[database]).get_result()
        last[database] = response['last_seq']

# Main loop
while True:
    for database in DATABASES:
        response = client.post_changes(db=database, include_docs=True, since=last[database]).get_result()
        result = response['results']
        for row in result:
            output = {'db': database, 'log': row}
            logger.info(output)
        last[database] = response['last_seq']
    time.sleep(POLLTIME)

sys.exit(0)
