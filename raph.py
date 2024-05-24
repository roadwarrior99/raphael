import boto3
from twitch_chat_irc import twitch_chat_irc # <- Fail
import os.path
envfile  = '.' + os.sep + '.env'
import json

class raphael_bot():
    twitchChatCon = ""
    twitchNick = ""
    secmgrclient = boto3.client('secretsmanager', region_name='us-east-1')
    def __init__(self):
        secResponse = self.secmgrclient.get_secret_value(SecretId='raphael-bot')
        if secResponse['SecretString']:
            secrets = json.loads(secResponse['SecretString'])
            if secrets['TwitchNickName']:
                self.twitchNick = secrets['TwitchNickName']
                if os.path.exists(envfile):
                    print("Writing temp secrets from Secret Manager.")
                else:
                    with open('.env', 'w') as f:
                        f.writelines(["NICK={0}".format(self.twitchNick)])
                        f.writelines(["PASS={0}".format(secrets['TwitchPassword'])])
                        f.close()
            else:
                print("Problem pulling AWS Secret")

    def connect(self):
        self.twitchChatCon = twitch_chat_irc.TwitchChatIRC()

    def sendTwitchMessage(self, message):
        if self.twitchChatCon:
            self.twitchChatCon.send('road_warrior99', message)
            messagesIn = []
            self.twitchChatCon.listen(channel_name="#road_warrior99", messages=messagesIn)
            print(messagesIn)
        else:
            print("Problem sending message")
    def listenTwitch(self):
        if self.twitchChatCon:
            messagesIn = []
            self.twitchChatCon.listen(channel_name="#road_warrior99", messages=messagesIn)
            print(messagesIn)
        else:
            print("Problem reading message")

if __name__ == '__main__':
    raph = raphael_bot()
    raph.connect()
    raph.sendTwitchMessage("Hello World!")
if os.path.exists(envfile):
    os.remove(envfile)