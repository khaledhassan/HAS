FROM resin/raspberrypi3-python:3
# docs at https://hub.docker.com/r/resin/raspberrypi3-python/ and https://docs.resin.io/runtime/resin-base-images/
# XXX: perhaps use the 3-onbuild version?

# Uncomment to enable systemd
# XXX: will we need this? for testing, I'm enabling this so that the container continues to run with no CMD
ENV INITSYSTEM on

WORKDIR /app

COPY . /app

# XXX: perhaps use the onbuild version and requirements.txt to install pip packages automatically
RUN pip install \
                paho-mqtt \
		requests

# Pass -u flag to python for unbuffered output according to https://github.com/moby/moby/issues/12447
CMD ["python", "-u", "./main.py"] 

