import os
import sys
import bluezutils
import dbus
import dbus.mainloop.glib
try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject
import threading
from bt_manager import codecs
from collections import namedtuple
import logging as log
import subprocess

CONFIG = codecs.SBCCodecConfig
CONFIG.frequency = codecs.SBCSamplingFrequency.FREQ_44_1KHZ
CONFIG.block_length = codecs.SBCBlocks.BLOCKS_16
CONFIG.channel_mode = codecs.SBCChannelMode.CHANNEL_MODE_STEREO
CONFIG.allocation_method = codecs.SBCAllocationMethod.LOUDNESS
CONFIG.subbands = codecs.SBCSubbands.SUBBANDS_8
CONFIG.min_bitpool = 2
CONFIG.max_bitpool = 53

class Player(dbus.service.Object):
    '''
    custom class object for reading and decoding a2dp stream and writing it to stdout
    '''
    fd = None
    mtu = None
    streaming = False
    transport = None

    def __init__(self, bus, obj_path, name):
	self.name = name
        self.obj_path = obj_path
        self.bus = bus
        log.basicConfig(stream=sys.stderr, level=log.DEBUG, format = u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s  %(message)s')
        dbus.service.Object.__init__(self, bus, self.obj_path, self.name)
        GObject.threads_init()
        self.audio_player = subprocess.Popen("aplay -f cd", shell=True, stdin=subprocess.PIPE)
        self.decoder = codecs.SBCCodec(CONFIG)
        log.debug('started')

    def decoder_start(self):
        self.dc_process = threading.Thread(target=self.read_input_stream, name='decoder')
        self.dc_process.setDaemon(True)
        self.dc_process.start()

    def pass_fd_path(self, fd_path):
	#self.bus.add_signal_receiver(self.detect_stream, dbus_interface="org.freedesktop.DBus.Properties", 
            #signal_name="PropertiesChanged", path=fd_path)
        s = fd_path.split('/fd')
        player_path = s[0] + '/player0'
        self.bus.add_signal_receiver(self.detect_track, dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged", path=player_path)
	self.transport = dbus.Interface(self.bus.get_object('org.bluez', fd_path),
            'org.bluez.MediaTransport1')
        log.debug('got fd')
        return

    def get_fd_desc(self):
        unix_fd, mtu_r, mtu_w = self.transport.Acquire()
        self.mtu = mtu_r
        self.fd = unix_fd.take()
        

    def read_input_stream(self):
        try:
            while self.streaming:
                buf = self.decoder.decode(self.fd, self.mtu)
                self.audio_player.stdin.write(buf)
                #log.debug('streaming')
        except IOError:
            log.debug('ioerror')
        else:
            #log.debug('else')
            pass
        finally:
            #log.debug('finally')
            pass

    def detect_stream(self, *args, **kwargs):
        prop = args[1]
        if prop.has_key('State'):
           state = prop.get('State')
        else: 
            return
        if state == 'pending':
            log.debug("pending")
            if not self.fd:
                self.get_fd_desc()
            self.streaming = True
            self.decoder_start()
        elif state == 'idle':
            self.streaming = False
            log.debug('idle')
#        elif state == 'active':
#            log.debug('active')

    def detect_track(self, *args, **kwargs):
        prop = args[1]
        if prop.has_key('Status'):
            state = prop.get('Status')
        else:
            return
        if state == 'playing':
            log.debug('playing')
            if not self.fd:
                self.get_fd_desc()
            self.streaming = True
            self.decoder_start()
        else:
            self.streaming = False
            log.debug('not playing')


    def clear_conn(self):
        log.debug(self.fd)
        os.close(self.fd)
        del self.fd
        self.transport.Release()


if __name__ == '__main__':

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    
    name = "jukebox_player"    
    path = "/jukebox/player"
    
    bus = dbus.SystemBus()

    player = Player(bus, path, name)
    
    loop = GObject.MainLoop()
    loop.run()


