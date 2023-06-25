# q_catalog
Simple demo web app using Flask-admin, sqlalchemy, socketio.

this is not packed up as a python wheel, so:

* clone the repo, 
* install the requirements (in a virtualenv) **pip install flask_sqlalchemy flask_socketio flask_admin**,
* run **python server.py**, 
* open the browser at **http:<localhost>:5000**


### Possible Improvements:

#### Security

* Use a production http server, and use HTTPS in the communication.
* Authentication and Authorization: only authorized users can upload or download files.
* Server-Side Validation on each uploaded chunk to ensure its integrity (e.g., SHA256).
* Rate Limiting to prevent abuse and protect.

#### Usability
 
* design a user friendly HTML interface 
* zip data on client and unzip on server

#### Test

* add a test suite based on a client impelemented in python

### Possible Variations:

* use websockets python module and a ASGI server (e.g. uvicorn) to serve in asyncio
* allow the users to upload the csv files in batch mode e.g. emailing them

