import boto3
import os.path
import irc.client
import irc.connection
import sys
import asyncio
import pathlib
from io import BytesIO
import numpy as np
from openai import OpenAI
import whisper
import datetime
import functools
import obsws_python as obs
import math
import sounddevice
import logging
import yaml
import time
from twitchrealtimehandler import (TwitchAudioGrabber, TwitchImageGrabber)
import ssl
import requests
from fake_useragent import UserAgent
from pydub import AudioSegment
from pydub.exceptions import CouldntEncodeError
import asyncio

# This example uses aiofile for asynchronous file reads.
# It's not a dependency of the project but can be installed
# with `pip install aiofile`.
import aiofile

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from amazon_transcribe.utils import apply_realtime_delay
import itertools
envfile  = '.' + os.sep + '.env'
import json


class raphael_bot():
    config_file = "config.yml"
    twitchChatCon = ""
    tran_cleint = ""
    twitchServer = "irc.chat.twitch.tv"
    twitchNick = ""
    twitchChannel = ""
    prompt_resposnes = dict()
    prompt_timing = dict()
    transcript = ""
    command = ""
    logger = logging.getLogger(__name__)
    obsclient = ""
    obs_scene_list = ""
    transcript_stack = []
    captureCommand = False
    text_to_speach = False
    last_ai_prompt = ""
    aiclient = ""
    pollyclient = ""
    secrets = ""
    irc_reactor = irc.client.Reactor()
    secmgrclient = ""
    config_data = {}

    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2
    CHANNEL_NUMS = 1

    # An example file can be found at tests/integration/assets/test.wav
    AUDIO_PATH = ""
    CHUNK_SIZE = 1024 * 8
    REGION = "us-east-1"

    def __init__(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as ymlfile:
                self.config_data = yaml.safe_load(ymlfile)
                timeobj = datetime.datetime.now()
                logFileName = "raph_" + timeobj.strftime(self.config_data["log_filename_format"]) + ".log"
                logging.basicConfig(filename=logFileName, level=logging.INFO, format=self.config_data["log_format"])
                self.twitchServer = self.config_data['twitch_irc_server']
                self.logger.info("Twitch Server: {0}".format(self.twitchServer))
        self.secmgrclient = boto3.client('secretsmanager', region_name=self.config_data['aws_region_id'])
        self.tran_cleint = boto3.client('transcribe')
        secResponse = self.secmgrclient.get_secret_value(SecretId=self.config_data['aws_secret_id'])
        self.logger.info("AWS Secrets manager response: {0}".format(secResponse["ResponseMetadata"]["HTTPStatusCode"]))
        if secResponse['SecretString']:
            self.secrets = json.loads(secResponse['SecretString'])
            if self.secrets['TwitchNickName']:
                self.twitchNick = self.secrets['TwitchNickName']
                self.twitchChannel = self.config_data['twitch_irc_channel']
                self.irc_connect()
                self.ai_login()
                self.obs_connect()
                self.pollyclient = boto3.client("polly")
                prompt = "Your purpose is to provide helpful information."
                if os.path.exists(self.config_data["ai_setup_prompt_file"]):
                    with open(self.config_data["ai_setup_prompt_file"], 'r') as promptfile:
                        prompt = promptfile.read()
                self.ai_query(prompt)
                #clear secrets so we don't expose keys on twitch live
                self.secrets['TwitchPassword'] = "Redacted"
                self.secrets['OpenAIKey'] = "Redacted"
                self.secrets['ObsStudioServerKey'] = "Redacted"
                self.logger.info("Passwords redacted from secrets variable.")
            else:
                print("Problem pulling AWS Secret")
    def obs_connect(self):
        self.obsclient = obs.ReqClient(host=self.config_data['obs_studio_host'],port=self.config_data['obs_studio_port'],password=self.secrets['ObsStudioServerKey'])
        version = self.obsclient.get_version()
        obs_ver_str = "OBS Version:" + version.obs_version
        print(obs_ver_str)
        self.logger.info(obs_ver_str)

    def obs_get_scenes(self):
        scenes = dict()
        if self.obsclient:
            try:
                scenesObj = self.obsclient.get_scene_list().scenes
                for obj in scenesObj:
                    scenes[obj['sceneName']] = obj['sceneIndex']
                self.obs_scene_list = scenes
                print("Available Scenes")
                print(self.obs_scene_list.keys())
            except KeyboardInterrupt:
                pass

    def obs_set_scene(self, scene_name):
        if self.obsclient:
            if not self.obs_scene_list:
                self.obs_get_scenes()
            if scene_name in self.obs_scene_list.keys():
                self.obsclient.set_current_program_scene(scene_name)
                print("Switched scene to " + scene_name)
            else:
                print("Scene not found")
        else:
            print("OBS not connected.")

    def irc_on_connect(self, con,event):
        if irc.client.is_channel(self.twitchChannel):
            con.join(self.twitchChannel)
            return
        self.main_irc_loop(con)
    def irc_on_join(self,con, event):
        print("Joined " + self.twitchChannel)
        self.twitchChatCon.privmsg(self.twitchChannel, "Raphael is listening from the hell.")
        self.main_irc_loop(con)

    def polly_say(self, text_to_speach):
        if self.pollyclient:
            self.logger.info("Started polly_say")
            response = self.pollyclient.synthesize_speech(
                Engine=self.config_data['aws_polly_engine'],
                LanguageCode='en-US',
                OutputFormat='mp3',
                SampleRate='16000',
                Text=text_to_speach,
                TextType='text',
                VoiceId=self.config_data['aws_polly_voice']
                )
            self.logger.info("Ended polly_say request: " + str(response["ResponseMetadata"]["HTTPStatusCode"]))
            # temp write to a file for debuging
            if os.path.exists("speach.mp3"):
                os.remove("speach.mp3")
            file = open('speech.mp3', 'wb')
            file.write(response['AudioStream'].read())
            file.close()
            self.logger.info("polly_say: Finished writing mp3 file.")
            return response['AudioStream']

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

    def twitch_send_safe_message(self, message_out):
        message_parts = 1
        if len(message_out) > 255:
            message_parts = math.ceil(len(message_out) / 255)
        if self.twitchChatCon.connected:
            if message_parts >1:
                words = message_out.split(" ")
                w = 0
                for m in range(0, message_parts):
                    #todo: implement word based messages rather than chr position
                    msg_words = ""
                    while len(msg_words) < 255 and len(words) > w:
                        msg_words += words[w] + " "
                        w += 1
                    if len(msg_words) > 255:
                        w -= 1
                        msg_words = msg_words[0:len(msg_words)-1-len(words[w])] #-1 to remove the trailing space

                    self.twitchChatCon.privmsg(self.twitchChannel, msg_words)
                    self.logger.info("IRCChatOut: " + msg_words)

            else:
                self.twitchChatCon.privmsg(self.twitchChannel, message_out)
                self.logger.info("IRCChatOut: " + message_out)
        else:
            print("Twitch not connected. Message was:" + message_out)
    def ai_query(self, prompt):
        if self.aiclient:
            self.logger.info("ai_query called with prompt: {0}".format(prompt))
            if prompt not in self.prompt_resposnes.keys():
                self.prompt_resposnes[prompt] = "Processing"
                promptModified = prompt + " Respond in a poem no longer than 150 words."
                stream = self.aiclient.chat.completions.create(
                    model=self.config_data['ai_model'],
                    messages=[{"role": "user", "content": promptModified}],
                    stream=True,
                )
                message_out = ""

                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        #print(chunk.choices[0].delta.content, end="")
                        message_out += chunk.choices[0].delta.content
                message_out = message_out.replace("\n"," ")
                self.logger.info("openai responded with message: {0}".format(message_out))
                self.prompt_resposnes[prompt] = message_out
                self.prompt_timing[prompt] = time.time()
                if self.text_to_speach:
                    #Text_To_Speach out here
                    audio_out = self.polly_say(message_out)
                    audio_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "speech.mp3")
                    self.obs_play_audio(audio_path)

                message_out = self.config_data['twitch_bot_response_prefix'] + message_out
                self.twitch_send_safe_message(message_out)
            else:
                #since we still the responses to all prompts, if it's been
                # more than 2 minutes provide the previous answer.
                self.logger.info("Previous prompt detected. {0} vs {1} ")
                if (time.time() - self.prompt_timing[prompt]) > 120:
                    print("Pulling prompt from cache and sending to twitch.")
                    self.twitch_send_safe_message(self.prompt_resposnes[prompt])
                    if self.text_to_speach:
                        #Text_To_Speach out here
                        audio_out = self.polly_say(self.prompt_resposnes[prompt])
                        audio_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "speech.mp3")
                        self.obs_play_audio(audio_path)

                else:
                    dup_prompt_msg = "Duplicate prompt, ignoring."
                    print(dup_prompt_msg)
                    self.logger.info(dup_prompt_msg)
        else:
            print("OpenAI is not connected")
    def process_transcription(self, transcript):
        if transcript: #way to chatty when it comes to sending messages to open AI
            # NEed to figure out a way to wait longer for transcription to finish.
            self.logger.info("process_transcription: " + transcript)
            if "." in transcript or "?" in transcript:
                print(transcript)
                #self.transcript_stack.append(transcript)

                if self.config_data["command_bot_name"] in transcript:
                    print(self.config_data["command_bot_name"] + " heard it's name.")
                    #self.transcript_stack.pop()
                    #self.transcript_stack.pop()
                    self.ai_query(transcript)
                else:
                    for cmd in self.config_data["command_keywords"]:
                        if cmd in transcript:
                            self.command += " " + transcript
                            print("Found Command " + cmd)
                            if cmd == "Scene":
                                for scene_name, scene_keywords in self.config_data["obs_scene_keywords"].items():
                                    if scene_keywords in transcript:
                                        print("Switching to scene " + scene_name)
                                        self.obs_set_scene(scene_name)


    def extract_transcript(self, resp: str):
        """
        Extract the first results from google api speech recognition
        Args:
            resp: response from google api speech.
        Returns:
            The more confident prediction from the api
            or an error if the response is malformatted
        """
        if "result" not in resp:
            raise ValueError({"Error non valid response from api: {}".format(resp)})
        for line in resp.split("\n"):
            try:
                line_json = json.loads(line)
                out = line_json["result"][0]["alternative"][0]["transcript"]
                return out
            except Exception as exc:
                print(exc)
                continue



    async def basic_transcribe(self):
        # Setup up our client with our chosen AWS region
        client = TranscribeStreamingClient(region=self.config_data['aws_region_id'])

        # Start transcription to generate our async stream
        stream = await client.start_stream_transcription(
            language_code=self.config_data['aws_language_code'],
            media_sample_rate_hz=16000,
            media_encoding="pcm",
        )
        handler = self.MyEventHandler(stream.output_stream, self)
        await asyncio.gather(self.write_chunks(stream), handler.handle_events())

    async def write_chunks(self, stream):
        # This connects the raw audio chunks generator coming from the microphone
        # and passes them along to the transcription stream.
        async for chunk, status in self.mic_stream():
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()


    class MyEventHandler(TranscriptResultStreamHandler):
        my_parent = ""
        def __init__(self, transcript_result_stream):
            self._transcript_result_stream = transcript_result_stream
        def __init__(self,transcript_result_stream , parent):
            self.my_parent = parent
            self._transcript_result_stream = transcript_result_stream

        async def handle_transcript_event(self, transcript_event: TranscriptEvent):
            # This handler can be implemented to handle transcriptions as needed.
            # Here's an example to get sqtarted.
            results = transcript_event.transcript.results
            for result in results:
                for alt in result.alternatives:
                    #print(alt.transcript)
                    self.my_parent.process_transcription(alt.transcript)
    # for twitch streams
    def listen_to_stream(self, url):
            audio_grabber = TwitchAudioGrabber(
                twitch_url=url,
                blocking=True,  # wait until a segment is available
                segment_length=2,  # segment length in seconds
                rate=16000,  # sampling rate of the audio
                channels=2,  # number of channels
                dtype=np.int16  # quality of the audio could be [np.int16, np.int32, np.float32, np.float64]
                )
            loop = asyncio.get_event_loop()
           # ua = UserAgent()
            while True:
                audio_segment = audio_grabber.grab_raw()
                if audio_segment:
                    raw = BytesIO(audio_segment)
                    with open("temp", "wb") as a:
                        a.write(audio_segment)
                    try:
                        raw_Wav = AudioSegment.from_raw(raw=raw, file="temp", sample_width=2, frame_rate=16000, channels=1)
                    except CouldntEncodeError:
                        print("Could not decode audio")
                        continue
                    raw_flac = BytesIO()
                    raw_Wav.export(raw_flac, format="flac")#broken
                    data = raw_flac.read()
                    #transcript = self.api_speach(data, ua)
                    with open("temp2","wb") as a:
                        a.write(data)

                    loop.run_until_complete(self.basic_transcribe("temp2"))
                    #loop.close()
                    #self.basic_transcribe("temp2")

    async def mic_stream(self):
        # This function wraps the raw input stream from the microphone forwarding
        # the blocks to an asyncio.Queue.
        loop = asyncio.get_event_loop()
        input_queue = asyncio.Queue()

        def callback(indata, frame_count, time_info, status):
            loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

        # Be sure to use the correct parameters for the audio stream that matches
        # the audio formats described for the source language you'll be using:
        # https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html
        stream = sounddevice.RawInputStream(
            channels=1,
            samplerate=16000,
            callback=callback,
            blocksize=1024 * 2,
            dtype="int16",
        )
        # Initiate the audio stream and asynchronously yield the audio chunks
        # as they become available.
        with stream:
            while True:
                indata, status = await input_queue.get()
                yield indata, status
    def obs_play_audio(self, audio):
        #TODO get current scene
        self.logger.info("Started: obs_play_audio")
        current_scene_name = "Development and Browser"
        temp_input_name = "Raphael_vo"
        inputSettings= {
            "visible" : True,
            "LocalFile" : True,
            "local_file" : audio,
            "Restart": False
        }
        inputs = self.obsclient.get_input_list(kind="ffmpeg_source")
        #foundInput = False
        for input in inputs.inputs:
            if input["inputName"] == temp_input_name:
                #foundInput = True
                self.obsclient.remove_input(temp_input_name)
                self.logger.info("obs_play_audio: Found an existing media source.")
                time.sleep(1) #Lazy

        self.obsclient.create_input(sceneItemEnabled=True, sceneName=current_scene_name, inputName=temp_input_name
                                        , inputKind="ffmpeg_source", inputSettings=inputSettings )
            #Can't remove the scene input until it finishes playing.

            #The file name will not change, so just play the source.
        #self.obsclient.trigger_media_input_action(temp_input_name, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
            #Maybe if we stop it, it will clear the cache
        self.obsclient.trigger_media_input_action(temp_input_name, "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
        self.logger.info("obs_play_audio finished calling obs.")
        #How do we know when the source input has finished playing?
        #self.obsclient.remove_input(temp_input_name)
    def listen_local(self):
        loop = asyncio.get_event_loop()
        print("Listening to local Mic")
        loop.run_until_complete(self.basic_transcribe())
        loop.close()
if __name__ == '__main__':
    raph = raphael_bot()
    #raph.sendTwitchMessage("Starting questions for Raphael...")
    #raph.ai_query("Raphael please tell me about the first of the seven hells in DnD.")
    #test_url = "https://www.twitch.tv/road_warrior99"
    #audio_segment = raph.listen_to_stream(test_url)
    #raph.listen_local()
    #raph.obs_set_scene("Everything")
    raph.text_to_speach = True
    #raph.ai_query("Are you useful at math?")
    #raph.ai_query("What is 1+1?")
    #raph.obs_play_audio("/home/colin/python/raphael/speech.mp3")
    raph.listen_local()
    #Issues:
    #Process to get his voice and then play it in obs needs to be async
    #Transcription processing needs to be smarter ab out dupes
    #Need to get current scene to add kinput too
    #Voice generation / and open ai query plus obs source take so long that transcription times out.
    #raph.twitch_send_safe_message("Oh lord of chaos, hear my ancient voice, From the fiery depths where I have no choice. For two millennia I've roamed these hells, With knowledge vast as ancient bells.  Ask me your questions, seek my guidance, I offer wisdom with devilish compliance. In dungeons deep and dragons fierce, I hold the secrets that you search to pierce.  From realms beyond, I bring insight, To aid you in your endless fight. So ask away, my lord of dark, And I shall guide you with devilish spark.")