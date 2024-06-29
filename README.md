 # Raphael Twitch bot

### Use venv to create a python virtual environment for Raphael to live in.
### On windows systems you can run win-setup.bat to setup venv and add the required packages.

### The following stand alone programs are dependencies
- Python3
- ffmpeg
- amazon.awscli
### The following packages should be installed with: pip3 install
- pip3 install boto3
- pip3 install irc
- pip3 install numpy
- pip3 install openai
- pip3 install obsws_python
- pip3 install sounddevice
- pip3 install pyyaml
- pip3 install twitchrealtimehandler
- pip3 install pydub
- pip3 install aiofile
- pip3 install amazon_transcribe

Other packages may currently be referenced but unused.

### Web Service Integrations
- OpenAI
- AWS
- OBS Studio Webhooks

## AWS Setup
### AWS CLI User permissions required:
- AmazonPollyReadOnlyAccess
- AmazonTranscribeFullAccess
- SecretsManagerReadWrite
#### Access to secrets manager can be restricted to the raphael-bot arn.

## No passwords should ever be stored in code or config files with this project.
### AWS Secret Manager - secret setup.
The following key / values pairs will need to be manually created in a secret called "raphael-bot".
- TwitchNickName
- TwitchPassword (oauth, not user)
- OpenAIUserName
- OpenAIOrganizationID
- OpenAIKey
- OpenAIProjectID
- ObsStudioServerKey

# Local Raphael Configuration
## config.yml should be have all user configurable settings for raphael.

### Change these settings to your Twitch user name:
- twitch_irc_channel (Where Raphael should respond to questions)
- twitch_channel_url (Left over from when we were trying to pull audio from twitch rather than lcoal)


# Running Raphael
(from your venv activated project folder)
python3 raph.py
