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
::Install dependecies
pip3 install -r requirements.txt
:: Launch aws configuration
aws configure

::
echo "Please turn on the OBS Studio WebSocket Server.
