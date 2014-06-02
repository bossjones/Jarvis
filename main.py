import threading
import logging
logger = logging.getLogger('simple_example')
logger.setLevel(logging.DEBUG)

from Tests.TestSerial import TestSerial

from Inputs.KaicongAudioGst import KaicongAudioSource
from Inputs.KaicongVideo import KaicongVideo

from Brain.Brain import JarvisBrain
from Brain.CommandParser import CommandParser, DummyCommandParser

from Outputs.ArduinoSerial import ArduinoSerial
from Outputs.RFSerial import RFSerial

from Outputs.IRController import IRController
from Outputs.SwitchController import SwitchController

from Outputs.RecordingController import RecordingController
from Outputs.GMusicController import GMusicController
from Outputs.LockitronController import LockitronController
from Outputs.TimerController import TimerController
from Outputs.ScriptController import ScriptController

# Spool up output devices, create room contexts
logging.debug("Initializing serial devices")
LIVINGROOM_IR = ArduinoSerial("/dev/ttyUSB0", 9600) #serial.Serial("COM2", 9600)
TRACKLIGHT = TestSerial("TL", 9600) #serial.Serial("COM4", 9600)
RF_BROADCAST = TestSerial("RF", 9600) #serial.Serial("COM1", 9600)

MAINLIGHT = RFSerial(RF_BROADCAST, "LIVINGROOM")
HACKSPACE_IR = RFSerial(RF_BROADCAST, "HACKIR")
HACKSPACE = RFSerial(RF_BROADCAST, "HACK")
KITCHEN = RFSerial(RF_BROADCAST, "KITCHEN")
TODDROOM = RFSerial(RF_BROADCAST, "TODD")

KAICONG_LIVINGROOM = "192.168.1.19"
KAICONG_KITCHEN = "192.168.1.17"
KAICONG_HACKSPACE = "192.168.1.19"
KAICONG_TODDROOM = "192.168.1.20"

logging.debug("Initializing room contexts")
livingroom_ctx = {
  "AC": IRController(LIVINGROOM_IR),
  "projector": IRController(LIVINGROOM_IR),
  "speakers": IRController(LIVINGROOM_IR),
  "projectorscreen": IRController(LIVINGROOM_IR),
  "mainlight": SwitchController(MAINLIGHT),
  "tracklight": SwitchController(TRACKLIGHT),
}

kitchen_ctx = {
  "mainlight": SwitchController(KITCHEN),
  "speakers": SwitchController(KITCHEN),
}

toddroom_ctx = {
  "mainlight": SwitchController(TODDROOM),
}

hackspace_ctx = {
  "mainlight": SwitchController(HACKSPACE),
  "recording": RecordingController(KAICONG_HACKSPACE),
  "AC": IRController(HACKSPACE_IR),
  "projector": IRController(HACKSPACE_IR),
}

global_ctx = {
  "music": GMusicController(),
  "lockitron": LockitronController(),
  "timer": TimerController(),
  "scripts": ScriptController(),
}

# Initialize the brain
brain = JarvisBrain()

# TODO: We're probably going to have to figure out how to run 
# multiple gstreamer streams within a single 
logger.info("Spooling up audio pipelines")
import gobject 
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst

gobject.type_register(KaicongAudioSource)
gst.element_register(KaicongAudioSource, 'kaicongaudiosrc', gst.RANK_MARGINAL)

def gen_kaicong_audio_src(ip):
  src = gst.element_factory_make("kaicongaudiosrc", "audiosrc")
  src.set_property("ip", ip)
  src.set_property("user", "jarvis_admin")
  src.set_property("pwd", "oakdale43")
  src.set_property("on", True)
  return src

# Initialize input devices and attach callbacks (with contexts)
def gen_callback(ctx):
  joined_ctx = dict(global_ctx.items() + ctx.items())
  def cb(input):
    # TODO: Buffer until "Jarvis" is spoken. Command parser class?
    return brain.processInput(joined_ctx, input)
  return cb

audio_sources = {
  "livingroom": CommandParser(
    gen_kaicong_audio_src(KAICONG_LIVINGROOM), gen_callback(livingroom_ctx)
  ),  
#  "kitchen": SpeechParser(
#    gen_kaicong_audio_src(KAICONG_KITCHEN), gen_callback(kitchen_ctx)
#  ),
#  "hackspace": SpeechParser(
#    gen_kaicong_audio_src(KAICONG_HACKSPACE), gen_callback(hackspace_ctx)
#  ),
#  "toddroom": SpeechParser(
#    gen_kaicong_audio_src(KAICONG_TODDROOM), gen_callback(toodroom_ctx)
#  ),
}

# Loop the gstreamer pipeline in the background
logger.info("Starting main audio thread")
g_loop = threading.Thread(target=gobject.MainLoop().run)
g_loop.daemon = True
g_loop.start()

# TODO: Setup and run CV stuff as well
running = True
while running:
  #cmd = raw_input("ROOM:")
  cmd = raw_input("CMD: ")

  if cmd == "quit":
    print "Exiting..."
    running = False
  else:
    audio_sources['livingroom'].inject(cmd)
    audio_sources['livingroom'].send()

