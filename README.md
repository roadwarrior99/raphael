# Raphael Twitch bot

### Use venv to create a python virtual environment for Raphael to live in.


### The following packages should be installed with: pip3 install
- boto3
- pyyaml
- irc
- numpy
- obsws_python
- sounddevice
- pydub

Other packages may currently be referenced but unused.

### Web Service Integrations
- OpenAI
- AWS

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

# Running Raphael
(from your venv activated project folder)
python3 raph.py
