import boto3
import os.path
import irc.client
import irc.connection
import sys
import pathlib
from openai import OpenAI
import datetime
import functools
import obsws_python as obs
import math
import sounddevice
import logging
import yaml
import time
import ssl
import asyncio
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
import json
import argparse


class raphael_bot():
    config_file = ""
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


    def __init__(self, configFile="config.yml"):
        self.config_file = configFile
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as ymlfile:
                self.config_data = yaml.safe_load(ymlfile)
                timeobj = datetime.datetime.now()
                self.text_to_speach = self.config_data["aws_text_to_speach"]
                logFileName = "raph_" + timeobj.strftime(self.config_data["log_filename_format"]) + ".log"
                logging.basicConfig(filename=logFileName, level=logging.INFO, format=self.config_data["log_format"])
                self.twitchServer = self.config_data['twitch_irc_server']
                self.logger.info("Twitch Server: {0}".format(self.twitchServer))
        self.secmgrclient = boto3.client('secretsmanager', region_name=self.config_data['aws_region_id'])
        self.tran_cleint = boto3.client('transcribe', region_name=self.config_data['aws_region_id'])
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
        try:
            self.obsclient = obs.ReqClient(host=self.config_data['obs_studio_host'],port=self.config_data['obs_studio_port'],password=self.secrets['ObsStudioServerKey'])
            version = self.obsclient.get_version()
            obs_ver_str = "OBS Version:" + version.obs_version
            print(obs_ver_str)
            self.logger.info(obs_ver_str)
        except Exception as e:
            print("Problem connecting to obs server: {0}".format(e))


    def obs_get_scenes(self):
        scenes = dict()
        if self.obsclient:
            try:
                sceneList = self.obsclient.get_scene_list()
                scenesObj = sceneList.scenes
                for obj in scenesObj:
                    scenes[obj['sceneName']] = obj['sceneIndex']
                self.obs_scene_list = scenes
                #print("Available Scenes")
                #print(self.obs_scene_list.keys())
                self.logger.info("obs_get_scenes: {0} current scene: {1}".format(
                     str(self.obs_scene_list), sceneList.current_program_scene_name
                ))
                return sceneList.current_program_scene_name
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
                promptModified = prompt + " " + self.config_data["ai_prompt_postfix"]
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
                self.logger.info("Previous prompt detected with time. {0} vs {1} ".format(
                    str(time.time()),str(self.prompt_timing[prompt])))
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


    def compare_prompt_likeness(self, promptPrev, promptCur):
        if promptPrev in promptCur:
            promptPrev_len = len(promptPrev)
            promptCur_len = len(promptCur)
            if promptPrev_len > promptCur_len:
                promptDiff = promptCur_len - promptPrev_len
                pctChange = promptPrev_len/promptCur_len
                return pctChange
            else:
                if promptPrev_len == promptCur_len:
                    return 1
                else:
                    return 0
        else:
            return 0
    def process_transcription(self, transcript):
        if transcript: #way to chatty when it comes to sending messages to open AI
            # NEed to figure out a way to wait longer for transcription to finish.
            self.logger.info("process_transcription: " + transcript)
            if self.config_data["obs_closed_caption"]:
                self.obs_closed_caption(transcript)
            word_count = len(transcript.split(" "))
            last_charecter = transcript[-1]
            if "." in transcript or "?" in transcript and word_count >= 5 and last_charecter in ['.', '?']:
                print(transcript)
                #self.transcript_stack.append(transcript)

                if self.config_data["command_bot_name"] in transcript:
                    print(self.config_data["command_bot_name"] + " heard it's name.")
                    #self.transcript_stack.pop()
                    #self.transcript_stack.pop()
                    if self.last_ai_prompt:
                        likeness = self.compare_prompt_likeness(self.last_ai_prompt, transcript)
                        prv_prt_lk = "Previous prompt likeness: " + str(likeness)
                        print(prv_prt_lk)
                        self.logger.info(prv_prt_lk)
                        if likeness > .8:
                            self.ai_query(transcript)
                    self.last_ai_prompt = transcript
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
        if self.obsclient:
            self.logger.info("Started: obs_play_audio")
            current_scene_name = self.obs_get_scenes()
            temp_input_name = "Raphael_vo"
            inputSettings= {
                "visible" : True,
                "LocalFile" : True,
                "local_file" : audio,
                "Restart": False
            }
            inputs = self.obsclient.get_input_list(kind="ffmpeg_source")
            foundInput = False
            for input in inputs.inputs:
                if input["inputName"] == temp_input_name:
                    foundInput = True
                    #self.obsclient.remove_input(temp_input_name)
                    self.logger.info("obs_play_audio: Found an existing media source.")
                    self.obsclient.set_input_settings(name=temp_input_name, settings=inputSettings, overlay=True)
                    #time.sleep(1) #Lazy
            if not foundInput:
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
        else:
            self.logger.info("obs_play_audio called while obs was not running.")
    def obs_closed_caption(self, caption):
        if self.obsclient:
            self.logger.info("Started: obs_closed_caption")
            current_scene_name = self.obs_get_scenes()
            temp_input_name = "Raphael_cc"
            inputSettings= {
                "text": caption,
            }
            itemProperties = {
                "visible" : True,
                "pos": {"x": 190, "y": 840},
                "scale": {"x": 0.16, "y": 0.16},
                "rot": 0
            }
            #Text objects have two parts. A source with the primary ID.
            # and an settings/items/item on the scene iteself with source_uuid
            #sources/scenes/items/
            #sources/settings/items
            textinputtype = "text_ft2_source_v2"
            inputs = self.obsclient.get_input_list(kind=textinputtype)
            foundInput = False
            for input in inputs.inputs:
                if input["inputName"] == temp_input_name:
                    foundInput = True
                    #self.obsclient.remove_input(temp_input_name)
                    self.logger.info("obs_closed_caption: Found an existing media source.")
                    self.obsclient.set_input_settings(name=temp_input_name, settings=inputSettings, overlay=True)
                    #sceneObj = self.obsclient.get_current_program_scene()
                    #sceneObj.settings.items[3]
            if not foundInput:
                self.obsclient.create_scene_item
                self.obsclient.create_input(sceneItemEnabled=True, sceneName=current_scene_name, inputName=temp_input_name
                                            , inputKind=textinputtype, inputSettings=inputSettings)
            self.logger.info("obs_closed_caption finished calling obs.")
    def listen_local(self):
        loop = asyncio.get_event_loop()
        print("Listening to local Mic")
        loop.run_until_complete(self.basic_transcribe())
        loop.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default="config.yml",
                        help="Use this option to pass in a different configuration file.")
    parser.add_argument('--aiquery', type=str, help="Send a prompt to ChatGPT")
    parser.add_argument('--polly', type=str, help="Send text to aws polly and get back an mp3 specified")
    parser.add_argument('--listen', help="Start Raphael bot and listen to the local mic.")
    parser.add_argument('--pro_trans', type=str, help="Pass the input to the process transcription function to test voice command processing.")
    parser.add_argument('--twitch', type=str, help="Send the input to twtich chat.")
    parser.add_argument('--obs_scenes', help="Query OBS the the list of available Scenes.")
    parser.add_argument('--obs_play', type=str, help="Make OBS play the audio file you specify.")
    parser.add_argument('--obs_cc', type=str, help="Make OBS add text to the screen.")
    args = parser.parse_args()
    raph = raphael_bot(args.config)
    if args.twitch:
        raph.sendTwitchMessage(args.twitch)
    if args.obs_scenes:
        current_scene = raph.obs_get_scenes()
        print("Current Scene: {0}".format(current_scene))
    if args.aiquery:
        raph.ai_query(args.aiquery)
    if args.obs_play:
        raph.obs_play_audio(args.obs_play)
    if args.pro_trans:
        raph.process_transcription(args.pro_trans)
    if args.obs_cc:
        raph.obs_closed_caption(args.obs_cc)
    if args.listen:
        raph.listen_local()
    if len(sys.argv)==1:
        # Default if no parameters are provided
        raph.listen_local()