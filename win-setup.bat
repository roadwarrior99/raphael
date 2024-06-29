:: Install Python3
winget install python3
:: Install ffmpeg
winget install ffmpeg
:: Install AWS CLI
winget install amazon.awscli

:: Setup a python virtual environment for the local system for raph
python3 -m venv %cd%
:: Launch the virtual python enviornment
call Scripts\activate.bat
#Install dependecies
pip3 install boto3
pip3 install irc
pip3 install numpy
pip3 install openai
pip3 install obsws_python
pip3 install sounddevice
pip3 install pyyaml
pip3 install twitchrealtimehandler
pip3 install pydub
pip3 install aiofile
pip3 install amazon_transcribe
:: Launch aws configuration
aws configure

::
echo "Please turn on the OBS Studio WebSocket Server.
