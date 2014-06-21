from Holodeck.pipe import Pipe as P
from serial import Serial
from Tests.TestSerial import TestSerial
from Outputs.RelayController import RelayController
from Outputs.RGBSingleController import RGBSingleController
from Outputs.RGBMultiController import RGBMultiController, RGBState, NTOWER, NRING
from Outputs.IRController import IRController
from Outputs.ScreenController import ScreenController
from Outputs.AudioController import AudioController
import time
import json
import logging
import threading
import Queue
import socket

from mod_pywebsocket.msgutil import MessageReceiver
from Holodeck.holodeck import classname_to_id
from Holodeck.holodeck_server import HolodeckServer, PORT


# TODO: Move to websockets?
class HolodeckController():
  TIMEOUT = 5.0

  def __init__(self, ws_request, server_list, port=PORT):
    self.logger = logging.getLogger(self.__class__.__name__)
    self.logger.setLevel(logging.DEBUG)
    self.servers = []
    self.q = Queue.Queue()
    self.request = ws_request

    for host in server_list:
      try:
        s = socket.create_connection((host,port), timeout=self.TIMEOUT)
        self.servers.append(s)
        t = threading.Thread(target=self.handle_deck, args=(s,))
        t.daemon = True
        t.start()
        self.logger.debug("Connection to %s established" % host)
      except socket.timeout:
        self.logger.error("Connection to %s timed out" % host)

  def __del__(self):
    for s in self.servers:
      s.close()

  def get_meta(self):
    effect_list = get_all_effects()
    
    icon_meta = {}
    for (ename, eclass) in effect_list.items():
      meta = eclass.get_meta()
      #TODO: Show active state
      #meta['active'] = deck.is_active(meta['id'])
      meta['active'] = False

      # Create this tab if not already made
      if not icon_meta.get(meta['tab'], None):
        icon_meta[meta['tab']] = {}
      icon_meta[meta['tab']][meta['id']] = meta 

    return icon_meta

  def deck_broadcast(self, cmd_json):

    for s in self.servers:
      if not s:
        self.logger.debug("Connection not open, skipping...")
        continue
      s.send(cmd_json+"\n")

    self.logger.debug("Sent %s to all decks" % cmd_json)

  def get_response(self):
    return {"day": False}

  def handle_deck(self, deck):
    while True: #TODO: could be done better
      try:
        msg = deck.recv(2048)
        if not msg:
          self.logger.warn("Deck connection closed")
          return

        self.logger.debug("Got %s" % ((msg[:40] + '..') if len(msg) > 40 else msg))
        self.q.put(msg)
      except socket.timeout:
        continue
  
  def handle_ws(self):
    rcvr = MessageReceiver(self.request, self.deck_broadcast)
    init_received = False
    while not rcvr._stop_requested:
      try:
        msg = self.q.get(True, 5.0)
      except Queue.Empty:
        continue
  
      if json.loads(msg).get("type") == "init":
        if init_received:
          self.logger.debug("Ignoring duplicate init")
          continue
        else:
          init_received = True


      self.request.ws_stream.send_message(msg, binary=False)
      self.logger.debug("Sent %s" % ((msg[:40] + '..') if len(msg) > 40 else msg))





class JarvisHolodeck(HolodeckServer):
  def __init__(self):
    self.devices = {
      "window": RGBSingleController(Serial("/dev/ttyUSB1", 9600)),
      "couch": RGBSingleController(Serial("/dev/ttyUSB0", 9600)),
      "tower": RGBMultiController(Serial("/dev/ttyACM0", 115200)),
      "proj_wall": ScreenController(socket.gethostname(), imgpath="Assets/Images/"),
      "lights": RelayController(Serial("/dev/ttyUSB2", 9600)),
    }

    time.sleep(2.5) # Need delay at least this long for arduino to startup
    self.devices['tower'].setState(RGBState.STATE_MANUAL)
    time.sleep(1.0)

    HolodeckServer.__init__(self)

  def get_pipeline_handlers(self):
    return [
      ([P.WINDOWTOP, P.WINDOWBOT], self.window_leds),
      ([P.FLOOR], self.floor_leds),
      ([P.TOWER, P.RING], self.tower_ring),
      ([P.WALLIMG], self.wall_img),
      ([P.LIGHTS], self.lights),
    ]

  def get_pipeline_defaults(self):
    return {
      P.WINDOWTOP:  [0,0,0],
      P.WINDOWBOT:  [0,0,0],
      P.FLOOR:      [0,0,0],
      P.TOWER:      [[0,0,0]]*NTOWER,
      P.RING:       [[0,0,0]]*NRING,
      P.WALLIMG:    None,
      P.LIGHTS:     False,
    }

  def window_leds(self, top, bot):
    self.devices['window'].write(top, bot)  

  def floor_leds(self, rgb):
    self.devices['couch'].write(rgb)
  
  def tower_ring(self, trgb, rrgb):
    for (i,c) in enumerate(trgb+rrgb):
      self.devices['tower'].manual_write(i, c)
    self.devices['tower'].manual_update()

  def wall_img(self, img):
    self.devices['proj_wall'].slide_to(img)

  def lights(self, is_on):
    self.devices['lights'].set_state(is_on)
  

class ToddHolodeck(HolodeckServer):
  def __init__(self):
    HolodeckServer.__init__(self)
    
    self.devices = {
      "proj_window": ScreenController(socket.gethostname()),
      "audio": AudioController(socket.gethostname()),
    }
    self.last_sounds = []

  def get_pipeline_handlers(self):
    return [
      ([P.WINDOWTOP, P.WINDOWBOT], self.window_leds),
      ([P.FLOOR], self.floor_leds),
      ([P.TOWER, P.RING], self.tower_ring),
      ([P.WINDOWIMG], self.window_img),
      ([P.WALLIMG], self.wall_img),
      ([P.LIGHTS], self.lights),
      ([P.SOUND], self.sound),
    ]

  def get_pipeline_defaults(self):
    return {
      P.WINDOWTOP:  [0,0,0],
      P.WINDOWBOT:  [0,0,0],
      P.FLOOR:      [0,0,0],
      P.TOWER:      [[0,0,0]]*NTOWER,
      P.RING:       [[0,0,0]]*NRING,
      P.WINDOWIMG:  None,
      P.WALLIMG:    None,
      P.LIGHTS:     False,
      P.SOUND:      [], 
      P.TEMP:       None,
    }

  def window_img(self, img):
    self.devices['proj_window'].zoom_to(img)
  
  def sound(self, sounds=[]):
    for s in sounds:
      if s not in self.last_sounds:
        self.devices['audio'].play(s)
    for s in self.last_sounds:
      if s not in sounds:
        self.devices['audio'].fade_out(s)
    self.last_sounds = sounds


if __name__ == "__main__":
  #import logging
  #logging.basicConfig()
  deck = JarvisHolodeck()

  # Test to see what the deck does
  print deck.handle({'day': True})

  raw_input("Enter to exit:")
