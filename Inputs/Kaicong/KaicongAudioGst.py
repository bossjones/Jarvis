#!/usr/bin/env python
# Origin: http://cgit.freedesktop.org/gstreamer/gst-python/tree/examples/filesrc.py

import pygst
pygst.require('0.10')
import gst

import gobject

from KaicongAudio import KaicongAudio

class KaicongAudioSource(gst.BaseSrc):
    __gstdetails__ = (
        "Kaicong Audio src plugin",
        "KaicongAudioGst.py",
        "Source element that rips sound from a Kaicong IP camera",
        "Scott Martin (github: smartin015)"
    )

    _src_template = gst.PadTemplate("src",
                          gst.PAD_SRC,
                          gst.PAD_ALWAYS,
                          gst.caps_new_any()
                    )

    __gsignals__ = {
      'packet_received' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }  

    __gsttemplates__ = (_src_template,)

    def __init__(self, *args, **kwargs):
        self.caps = gst.caps_from_string('audio/x-raw-int, rate=7600, endianness=1234, channels=1, width=16, depth=16, signed=true')
        gst.BaseSrc.__init__(self)
        gst.info("Creating Kaicong src pad")
        self.src_pad = gst.Pad(self._src_template)
        self.src_pad.use_fixed_caps()

    def set_property(self, name, value):
        if name == 'ip':
            self.ip = value
        elif name == 'user':
            self.user = value
        elif name == "pwd":
            self.pwd = value
        elif name == "on" and value:
            self.audio = KaicongAudio(self.ip, user=self.user, pwd=self.pwd)
            self.audio.connect()
            gst.info("Connected audio")

    def do_create(self, offset, size):
        self.emit("packet_received")
        assert self.audio
        data = self.audio.read()
        buf = gst.Buffer(data)
        buf.set_caps(self.caps)
        print "do_create", len(buf)
        return gst.FLOW_OK, buf
        


if __name__ == "__main__":
  import sys
  import gobject 
  gobject.threads_init()

  if len(sys.argv) != 4:
    print "Usage: %s <ip_address> <user> <pass>" % sys.argv[0]
    sys.exit(-1)

  pipeline = gst.Pipeline("pipe")

  gobject.type_register(KaicongAudioSource)
  gst.element_register(KaicongAudioSource, 'kaicongaudiosrc', gst.RANK_MARGINAL)

  src = gst.element_factory_make("kaicongaudiosrc", "audiosrc")
  src.set_property("ip", sys.argv[1])
  src.set_property("user", sys.argv[2])
  src.set_property("pwd", sys.argv[3])
  src.set_property("on", True)
  conv = gst.element_factory_make("audioconvert", "audioconv")
  amp = gst.element_factory_make("audioamplify", "audioamp")
  amp.set_property("amplification", 20)
  res = gst.element_factory_make("audioresample", "audioresamp")
  sink = gst.element_factory_make("autoaudiosink", "audiosink")
  
  pipeline.add(src, conv, amp, res, sink)
  gst.element_link_many(src, conv, amp, res, sink)
  pipeline.set_state(gst.STATE_PLAYING)

  main_loop = gobject.MainLoop()
  main_loop.run()
  
