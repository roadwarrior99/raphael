import boto3
import os.path
import irc.client
import irc.connection
import sys
import asyncio
import numpy as np
from openai import OpenAI
import functools
import math
import yaml
import time
from twitchrealtimehandler import (TwitchAudioGrabber, TwitchImageGrabber)
import ssl
import itertools
envfile  = '.' + os.sep + '.env'
import json

class raphael_bot():
    config_file = "config.yml"
    twitchChatCon = ""
    twitchServer = "irc.chat.twitch.tv"
    twitchNick = ""
    twitchChannel = ""
    aiclient = ""
    secrets = ""
    irc_reactor = irc.client.Reactor()
    secmgrclient = ""
    config_data = {}
    def __init__(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as ymlfile:
                self.config_data = yaml.safe_load(ymlfile)
                self.twitchServer = self.config_data['twitch_irc_server']
        self.secmgrclient = boto3.client('secretsmanager', region_name=self.config_data['aws_region_id'])
        secResponse = self.secmgrclient.get_secret_value(SecretId=self.config_data['aws_secret_id'])
        if secResponse['SecretString']:
            self.secrets = json.loads(secResponse['SecretString'])
            if self.secrets['TwitchNickName']:
                self.twitchNick = self.secrets['TwitchNickName']
                self.twitchChannel = self.config_data['twitch_irc_channel']
                self.irc_connect()
                self.ai_login()
                prompt = "Your purpose is to provide helpful information."
                if os.path.exists(self.config_data["ai_setup_prompt_file"]):
                    with open(self.config_data["ai_setup_prompt_file"], 'r') as promptfile:
                        prompt = promptfile.read()
                self.ai_query(prompt)
            else:
                print("Problem pulling AWS Secret")

    def irc_on_connect(self, con,event):
        if irc.client.is_channel(self.twitchChannel):
            con.join(self.twitchChannel)
            return
        self.main_irc_loop(con)
    def irc_on_join(self,con, event):
        print("Joined " + self.twitchChannel)
        self.twitchChatCon.privmsg(self.twitchChannel, "Raphael is listening from the hell.")
        self.main_irc_loop(con)

    def irc_on_disconnect(self, connection, event):
        raise SystemExit()
    def get_lines(self):
        while True:
            yield sys.stdin.readline().strip()
    def main_irc_loop(self, con):
        print("main loop")
    def irc_connect(self):
        #self.twitchChatCon = twitch_chat_irc.TwitchChatIRC(self.twitchNick, self.secrets['TwitchPassword'])
        try:
            context = ssl.create_default_context()
            wrapper = functools.partial(context.wrap_socket, server_hostname=self.twitchServer)
            ssl_factory = irc.connection.Factory(wrapper=wrapper)
            c = self.irc_reactor.server().connect(server=self.twitchServer, port=self.config_data['twitch_irc_port'],
                                                  nickname=self.twitchNick,
                                                  password=self.secrets['TwitchPassword'],
                                                  username=self.secrets['TwitchNickName'],
                                                  connect_factory=ssl_factory)
        except irc.client.ServerConnectionError:
            print("IRC Connection failure.")
            print(sys.exc_info()[1])
            raise SystemExit(1) from None
        print("Connected to IRC Server")
        c.add_global_handler("welcome", self.irc_on_connect)
        c.add_global_handler("join", self.irc_on_join)
        c.add_global_handler("disconnect", self.irc_on_disconnect)
        self.twitchChatCon = c
        self.irc_reactor.process_timeout()


    def sendTwitchMessage(self, message):
        if self.twitchChatCon:
            if self.twitchChatCon.connected:
                self.twitchChatCon.privmsg(self.twitchChannel,message)
            else:
                print("Twitch channel not connected")
            #self.twitchChatCon.send('#' + self.twitchNick, message)
        else:
            print("Problem sending message")

    def ai_login(self):
        #OpenAIOrganizationID
        #OpenAIKey
        #OpenAIProjectID
        aiclient = OpenAI(
        organization=self.secrets['OpenAIOrganizationID'],
        project=self.secrets['OpenAIProjectID'],
        api_key=self.secrets['OpenAIKey'],
        )
        self.aiclient = aiclient
        print("Connected to OpenAI")
    def ai_query(self, prompt):
        if self.aiclient:
            stream = self.aiclient.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            message_out = "Raphael_bot: "
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    #print(chunk.choices[0].delta.content, end="")
                    message_out += chunk.choices[0].delta.content
            message_out = message_out.replace("\n","")
            message_parts = 1
            if len(message_out) > 255:
                message_parts = math.ceil(len(message_out) / 255)

            if self.twitchChatCon.connected:
                if message_parts >1:
                    for m in range(1, message_parts):

                        if m > 1:
                            msgStart = m * 255
                            time.sleep(1)
                        else:
                            msgStart = 0
                        msgEnd = msgStart + 255
                        if msgEnd > len(message_out):
                            msgEnd = len(message_out)
                        self.twitchChatCon.privmsg(self.twitchChannel, message_out[msgStart:msgEnd])
                else:
                    self.twitchChatCon.privmsg(self.twitchChannel, message_out)
            else:
                print(message_out)
        else:
            print("OpenAI is not connected")
    def listen_to_stream(self, url):
        audio_grabber = TwitchAudioGrabber(
            twitch_url=url,
            blocking=True,  # wait until a segment is available
            segment_length=2,  # segment length in seconds
            rate=16000,  # sampling rate of the audio
            channels=2,  # number of channels
            dtype=np.int16  # quality of the audio could be [np.int16, np.int32, np.float32, np.float64]
            )
        audio_segment = audio_grabber.grab()
        return audio_segment
if __name__ == '__main__':
    raph = raphael_bot()
    raph.sendTwitchMessage("Starting questions for Raphael...")
    raph.ai_query("Raphael please tell me about the first of the seven hells in DnD.")
    transcription = raph.listen_to_stream("https://www.twitch.tv/road_warrior99")
