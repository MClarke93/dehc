FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get upgrade

RUN apt-get install -y python-is-python3 python3.9 python3.9-dev python3.9-venv python3-pip swig curl git
# opencv deps
RUN apt-get install -y libgl1-mesa-glx ffmpeg libsm6 libxext6
# tkinter
RUN apt-get install -y python3.9-tk
# smartcard deps
RUN apt-get install -y libpcsclite-dev

# fonts
RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections
RUN apt-get install -y --no-install-recommends fontconfig ttf-mscorefonts-installer
RUN fc-cache -f -v

# fetch just requirements so minor code edits don't trigger a docker rebuild
COPY ./requirements.txt /dehc/requirements.txt
WORKDIR "/dehc"

RUN python3.9 -m venv env

# pywin dependency will crash on ubuntu
RUN . env/bin/activate && pip install wheel
RUN . env/bin/activate && pip install -r requirements.txt

COPY ./ /dehc
RUN chown 1000:1000 /dehc/logs
#COPY ./entrypoint.sh ./entrypoint.sh

#ENTRYPOINT ./entrypoint.sh


