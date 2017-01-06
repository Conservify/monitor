import sys
import logging
import os
import threading
import atexit
import shelve

from database import MonitorDatabase

from dateutil import parser
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from slackclient import SlackClient

class Transmissions:
    def __init__(self, slack):
        self.instances = {}
        self.slack = slack

    def save(self, instance, time, data, source):
        with MonitorDatabase('/app/data/monitor.db') as db:
            db.add_transmission(instance, time, data, source)

    def rockblock(self, instance, time, data):
        self.save(instance, time, data, 'rockblock')

    def particle(self, instance, time, data):
        self.save(instance, time, data, 'particle')

slack_token = os.environ["SLACK_API_TOKEN"]
sc = SlackClient(slack_token)
transmissions = Transmissions(sc)

app = Flask(__name__)

@app.route('/monitor')
def welcome():
    with MonitorDatabase('/app/data/monitor.db') as db:
        data = db.fetch_and_parse_latest()
        app.logger.info(data)
        return jsonify({ 'transmissions': data })

@app.route('/monitor/rockblock', methods=['GET', 'POST'])
def rockblock():
    serial = request.form['serial']
    time = parser.parse(request.form['transmit_time'], yearfirst=True)
    data = request.form['data'].decode('hex').decode('utf-8')
    app.logger.info([serial, time, data])
    transmissions.rockblock(serial, time, data)
    return 'Ok'

@app.route('/monitor/particle', methods=['GET', 'POST'])
def particle():
    serial = request.form['coreid']
    time = parser.parse(request.form['published_at'])
    data = request.form['data']
    app.logger.info([serial, time, data])
    transmissions.particle(serial, time, data)
    return 'Ok'

lock = threading.Lock()
checking_thread = threading.Thread()
def turn_on_checking_thread():
    def run_check():
        global transmissions
        global checking_thread
        global lock
        with lock:
            with MonitorDatabase('/app/data/monitor.db') as db:
                try:
                    rows = db.fetch_and_parse_latest()
                    lines = []
                    for row in rows:
                        if row:
                            lines.append("%s: %smins (%f)" % (row['name'], (row['age'] / 60), row['charge']))
                    sc.api_call(
                        "chat.postMessage",
                        channel="#testing",
                        text="Status Update\n```" + "\n".join(lines) + "\n```"
                    )
                finally:
                    start_checking_thread(15 * 60)

    def start_checking_thread(delay):
        global checking_thread
        checking_thread = threading.Timer(delay, run_check, ())
        checking_thread.daemon = True
        checking_thread.start()

    app.logger.info("Starting thread...")
    start_checking_thread(5)
    return app

if __name__ == '__main__':
    # handler = RotatingFileHandler('foo.log', maxBytes=10000, backupCount=1)
    # handler.setLevel(logging.INFO)
    # app.logger.addHandler(handler)
    turn_on_checking_thread()
    app.run(debug=True, host='0.0.0.0', use_reloader=False)