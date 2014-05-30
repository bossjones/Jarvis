#!/usr/bin/env python
# Origin: http://cgit.freedesktop.org/gstreamer/gst-python/tree/examples/filesrc.py

import sys
import gobject 
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst

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
  
    __gsttemplates__ = (_src_template,)

    def __init__(self, *args, **kwargs):
        gst.BaseSrc.__init__(self)
        gst.info("Creating Kaicong src pad")
        self.src_pad = gst.Pad(self._src_template)
        self.src_pad.use_fixed_caps()

        self.caps = gst.caps_from_string('audio/x-raw-int, rate=7600, endianness=1234, channels=1, width=16, depth=16, signed=true')

        # TODO: Set as property
        self.audio = KaicongAudio("192.168.1.15")
        self.audio.connect()
        gst.info("Connected audio")

    def set_property(self, name, value):
        if name == 'ip':
            self.audio = KaicongAudio(value)
            self.audio.connect()

    def do_create(self, offset, size):
        data = self.audio.read()
        buf = gst.Buffer(data)
        buf.set_caps(self.caps)
        print "do_create", len(buf)
        return gst.FLOW_OK, buf
        
gobject.type_register(KaicongAudioSource)
gst.element_register(KaicongAudioSource, 'kaicongaudiosrc', gst.RANK_MARGINAL)

if __name__ == "__main__":
  pipeline_str = 'kaicongaudiosrc ! audioconvert ! audioresample ! autoaudiosink'
  pipeline = gst.parse_launch(pipeline_str)
  pipeline.set_state(gst.STATE_PLAYING)

  main_loop = gobject.MainLoop()
  main_loop.run()
