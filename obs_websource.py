from flask import Flask, render_template, Response, request
from math import sqrt
from time import sleep
import threading
import json
import logging
app = Flask(__name__)
my_closed_caption = "Welcome"
@app.route("/")
async def index():
    return render_template("index.html")

@app.route("/closed_captions")
def closed_captions():
    return render_template("closed_captions.html")
@app.route("/closed_service")
def caption_service():
    global my_closed_caption
    return json.dumps({'success':True, "caption": my_closed_caption}), 200, {'ContentType':'application/json'}

@app.route("/update_closed_caption", methods=["POST"])
def update_caption():
    if request.form.get("new_caption"):
        new_caption = request.form.get("new_caption")
        global my_closed_caption
        my_closed_caption = new_caption
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
    else:
        return json.dumps({'success':False, 'message':"no new_caption sent."}), 500, {'ContentType':'application/json'}


#if __name__ == "__main__":
#    print("you are here")
#    threading.Thread(target=lambda: app.run(use_reloader=False, debug=False), args=()).start()

