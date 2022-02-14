#!/bin/bash

# the app gets cranky if it's started before the database is ready
sleep 3;

# install some minimal databases
curl -X PUT http://admin:Creative@couchdb:5984/_users;
curl -X PUT http://admin:Creative@couchdb:5984/_replicator;

# move to the app directory
cd /dehc/;

# select python 3.9 using on the venv created in the dockerfile
. env/bin/activate;


# prepare some example data
python data_gen.py 5 5;


# start the application
python main.py -H
#python3.9 main.py TT "airfield"
