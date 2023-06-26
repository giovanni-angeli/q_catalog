# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=broad-except
# pylint: disable=invalid-name
# pylint: disable=too-few-public-methods
# pylint: disable=logging-format-interpolation, consider-using-f-string, logging-fstring-interpolation

import os
import sys
import logging
import time
import uuid
import csv
import traceback

from flask_sqlalchemy import SQLAlchemy         # pylint: disable=import-error
from flask_socketio import SocketIO             # pylint: disable=import-error
from flask import (Flask, render_template, request) # pylint: disable=import-error
from flask_admin import (AdminIndexView, Admin)   # pylint: disable=import-error
from flask_admin.contrib.sqla import ModelView  # pylint: disable=import-error
from flask_admin.base import MenuLink # pylint: disable=import-error

here = os.path.dirname(os.path.abspath(__file__))
STORAGE_PATH = os.path.join(here, 'data')
sqlalchemy_database_uri = f'sqlite:///{STORAGE_PATH}/catalog.01.db'

LOG_LEVEL = "WARNING"
if sys.argv[1:]:
    LOG_LEVEL = sys.argv[1]

HOST = 'localhost'
PORT = 5000

CSV_ENCODING = 'utf-8-sig'
CSV_DELIMITER = ','
CSV_QUOTECHAR = '"'

CHUNK_SIZE_BYTES = 1024

os.makedirs(STORAGE_PATH, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_database_uri
socketio = SocketIO(app)
db = SQLAlchemy(app)


def generate_id():

    return str(uuid.uuid4())

def dump_from_csv_file_to_db(f_pth, sessid):  # pylint: disable=too-many-locals

    t0 = time.time()
    new_cntr = 0
    mod_cntr = 0
    err_cntr = 0
    row_cntr = 0
    with app.app_context():
        with open(f_pth, encoding=CSV_ENCODING) as f:
            csv_reader = csv.DictReader(f, delimiter=CSV_DELIMITER, quotechar=CSV_QUOTECHAR)

            for row in csv_reader:
                try:
                    old_ID = row.pop('ID')
                    q = db.session.query(Catalog)  # pylint: disable=no-member
                    old_c = q.filter_by(ID=old_ID).first()
                    if old_c:
                        for k, v in row.items():
                            setattr(old_c, k, v)
                        # ~ old_c.update(row)
                        db.session.commit() # pylint: disable=no-member
                        mod_cntr += 1
                    else:
                        c = Catalog(**row)
                        db.session.add(c) # pylint: disable=no-member
                        db.session.commit() # pylint: disable=no-member
                        new_cntr += 1

                    msg_ = f"{new_cntr} new and {mod_cntr} modified records..."

                    logging.debug(msg_)

                    if row_cntr%10 == 0:
                        socketio.emit('record_loaded_ack', {'message': msg_}, to=sessid)

                except Exception as e:
                    err_cntr += 1
                    db.session.rollback()  # pylint: disable=no-member
                    logging.error(f"{e}")

                row_cntr += 1

    dt = time.time() - t0
    logging.info(f"f_pth:{f_pth}, {new_cntr} new and {mod_cntr} modified records, dt:{dt}")

    return new_cntr, mod_cntr, err_cntr

class Catalog(db.Model):

    __tablename__ = 'catalog'

    ID = db.Column(db.Unicode, primary_key=True, nullable=False, default=generate_id)
    Name = db.Column(db.Unicode, nullable=False)
    Price = db.Column(db.Unicode, nullable=False)

class CatalogView(ModelView):

    can_view_details = True
    can_export = True
    export_max_rows = 1000
    export_types = ['csv', ]

    column_list = ('ID', 'Name', 'Price')
    # ~ column_exclude_list = ()



class SocketioServer:
    
    sessions = {}

    @staticmethod
    @socketio.on('connect')
    def handle_connect():
        logging.info(f'sessid:{request.sid} client connected')

    @staticmethod
    @socketio.on('disconnect')
    def handle_disconnect():
        logging.info(f'sessid:{request.sid} client disconnected')

    @staticmethod
    @socketio.on('start_file_upload')
    def handle_start_file_upload_ack(file_size, file_id):

        sessid = request.sid
        logging.debug(f'file_size:{file_size }, sessid:{sessid}, file_id:{file_id}')

        with open(os.path.join(STORAGE_PATH, f"{sessid}.{file_id}"), 'w', encoding=CSV_ENCODING):
            socketio.emit('start_file_upload_ack', {'message': 'Chunk acknowledged by the server'}, to=sessid)

    @staticmethod
    @socketio.on('upload_chunk')
    def handle_upload_chunk(chunk, file_id):

        sessid = request.sid
        logging.info(f'len(chunk):{len(chunk)}, sessid:{sessid}, file_id:{file_id}')
        with open(os.path.join(STORAGE_PATH, f"{sessid}.{file_id}"), 'a', encoding=CSV_ENCODING) as f:
            f.write(chunk.decode(CSV_ENCODING))
            socketio.emit('chunk_ack', {'message': 'Chunk acknowledged by the server'}, to=sessid)

    @staticmethod
    @socketio.on('file_uploaded')
    def handle_file_uploaded(file_size, file_id):

        sessid = request.sid
        logging.info(f'file_size:{file_size }, sessid:{sessid}, file_id:{file_id}')

        f_pth = os.path.join(STORAGE_PATH, f"{sessid}.{file_id}")

        socketio.emit('file_uploaded_ack', {'message': 'File received, loading records into db...'}, to=sessid)

        try:
            new_cntr, mod_cntr, err_cntr = dump_from_csv_file_to_db(f_pth, sessid)
            msg_ = f'{new_cntr} new and {mod_cntr} modified records into db. {err_cntr} invalid rows.'
            socketio.emit('file_stored_ack', {'message': msg_}, to=sessid)
        except Exception as e:
            logging.error(traceback.format_exc())
            socketio.emit('file_stored_ack', {'message': f'ERROR in storing data to db: {e}.'}, to=sessid)

        os.remove(f_pth)

def set_logging(log_level):
    fmt_ = logging.Formatter('[%(asctime)s]'
                             # ~ '%(name)s:'
                             '%(levelname)s:'
                             '%(funcName)s() '
                             '%(filename)s:'
                             '%(lineno)d: '
                             '%(message)s ')

    ch = logging.StreamHandler()
    ch.setFormatter(fmt_)
    logger_ = logging.getLogger()
    logger_.handlers = []
    logger_.addHandler(ch)
    logger_.setLevel(log_level)

    logging.warning(f"log_level:{log_level}")

@app.route('/')
def index():

    ctx = dict(
        csv_encoding=CSV_ENCODING,
        csv_delimiter=CSV_DELIMITER,
        csv_quotechar=CSV_QUOTECHAR,
        chunk_size_bytes=CHUNK_SIZE_BYTES,
    )
    return render_template('index.html', **ctx)


def main():

    set_logging(LOG_LEVEL)

    with app.app_context():
        db.create_all()

    admin = Admin(app, index_view=AdminIndexView())
    admin.add_view(CatalogView(Catalog, db.session))

    admin.add_link(MenuLink(name='file transfer page', url='/'))

    socketio.run(app, port=PORT, host=HOST, debug=(LOG_LEVEL=='DEBUG'))

if __name__ == '__main__':
    main()
