from flask import Flask, render_template, Response, request, send_from_directory
from math import sqrt
from time import sleep
import threading
import os
import json
import datetime

import logging
app = Flask(__name__)
my_closed_caption = "Welcome"
my_speach_file = "speech.mp3"
@app.route("/")
async def index():
    return render_template("index.html")

@app.route("/speach")
def speach():
    global my_speach_file
    if os.path.exists(os.path.dirname(os.path.realpath(__file__)) + my_speach_file):
        return send_from_directory(os.path.dirname(os.path.realpath(__file__)), my_speach_file, mimetype='audio/mpeg')
    else:
        return "",404

@app.route("/closed_captions")
def closed_captions():
    file_hash = ""
    crc_file_path = os.path.dirname(os.path.realpath(__file__)) + "/speech.mp3.crc"
    if os.path.exists(crc_file_path):
        with open(crc_file_path, 'r') as f:
            file_hash = f.readline()
    return render_template("closed_captions.html", file_hash=file_hash)
@app.route("/closed_service")
def caption_service():
    global my_closed_caption
    file_hash = ""
    crc_file_path = "/home/colin/PycharmProjects/raphael/speech.mp3.crc"
    if os.path.exists(crc_file_path):
        with open(crc_file_path, 'r') as f:
            file_hash = f.readline()
    timestamp = os.path.getmtime("speech.mp3")
    filetime = datetime.datetime.fromtimestamp(timestamp)
    nowtime = datetime.datetime.now()
    how_old_is_the_file = (nowtime - filetime).total_seconds()
    caption_json  = {
        'success':True,
        "caption": my_closed_caption,
        "speach_age_seconds": how_old_is_the_file,
        "speach_hash": file_hash
    }
    return json.dumps(caption_json), 200, {'ContentType':'application/json'}

@app.route("/update_closed_caption", methods=["POST"])
def update_caption():
    if request.form.get("new_caption"):
        new_caption = request.form.get("new_caption")
        global my_closed_caption
        my_closed_caption = new_caption
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
    else:
        return json.dumps({'success':False, 'message':"no new_caption sent."}), 500, {'ContentType':'application/json'}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
