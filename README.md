# Digital Evacuation Handling Centre 

**Installation and Quickstart**:
1. Install [Python 3.9](https://www.python.org/downloads/) and [CouchDB](http://couchdb.apache.org/). Ensure the CouchDB service is running.
2. Clone this repository and navigate to its root folder using your favourite terminal.
3. Edit *db_auth.json* so that it contains the username, password and server you use for your particular CouchDB instance.
4. Run `pip install -r requirements.txt` to install this application's depedancies.
5. Run `py data.py` to populate the database with test data.
6. Run `py main.py` to start the application itself.
