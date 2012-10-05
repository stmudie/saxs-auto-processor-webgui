from gevent import monkey; monkey.patch_all()
import gevent
from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
from time import sleep, time
from flask import Flask, request, send_file, render_template
import cPickle as pickle
import redis
from os.path import basename

app = Flask(__name__)

app.debug = True

redisObj = redis.StrictRedis(host='10.138.11.70', port=6379, db=0)

attributes = { 'nicknames': [] }


class GraphNamespace(BaseNamespace):
    def sendProfile(self, name, data):
        filename = basename(data['filename'])
        fullProfile =[(element[0],element[1]) for element in data['profile'] if element[1]>0]
        self.emit(name, {'filename':filename,'profile':fullProfile})

    def checkForNewRedisProfile(self):
        self.sub = redisObj.pubsub()
        subChannels = redisObj.smembers('logline:channels')
       
        profileNames = [channel.split(':')[-1] for channel in subChannels]
        print 'Reloading: %s' %(profileNames,)
        profiles = redisObj.mget(["logline:%s" % profile for profile in profileNames])
        for profileIndex, profileName in enumerate(profileNames):
            profile = profiles[profileIndex]
            if profile != None :
                data = pickle.loads(profile)
                self.sendProfile(profileName, data)

        print 'Reloading autowater'
        if redisObj.llen('logline:autowater') > 0:
            print 'There are %s autowater profiles to reload' %(redisObj.llen('logline:autowater'),)
            autoWaterNames = redisObj.lrange('logline:autowater',0,redisObj.llen('logline:autowater'))
            autoWaterProfiles = redisObj.mget([profile for profile in autoWaterNames])
            for autoWaterIndex, autoWaterName in enumerate(autoWaterNames):
                autoWaterProfile = autoWaterProfiles[autoWaterIndex]
                if autoWaterProfile != None :
                    print 'Reload %s' %(autoWaterName,)
                    data = pickle.loads(autoWaterProfile)
                    #self.sendProfile('autowater', data)

        self.sub.subscribe(subChannels)
        self.sub.subscribe('logline:pub:autowater')
        zeros = [0]*len(subChannels)
        print 'listening'
        lastTimeSent = dict(zip(subChannels, zeros))
        for message in self.sub.listen():
            print 'Message from channel %s' %(message['channel'],)
            if (message['type'] != 'message'):
                print 'Wrong message type: %s' %(message['type'],)
                continue
            try:
                if (message['channel'] == 'logline:pub:autowater') :
                    print 'send autowater'
                    data = pickle.loads(message['data'])
                    #self.sendProfile('autowater', data)
                else :
                    if time()-lastTimeSent[message['channel']] < 0.5:
                        continue
                    print 'send %s' %(message['channel'],)
                    data = pickle.loads(message['data'])
                    self.sendProfile(message['channel'].split(':')[-1], data)
                    lastTimeSent[message['channel']] = time()
            except Exception, e:
                print 'There was an exception in checkForNewRedisProfile: %s' %(e,)

    def recv_connect(self):
        print 'connect'
        g = self.spawn(self.checkForNewRedisProfile)
        # g1 = self.spawn(self.checkForAutoWater)
        
    
    def recv_disconnect(self):
        self.sub.unsubscribe()
        self.kill_local_jobs()
        print 'disconnect'

    def recv_message(self, message):
        print "PING!!!", message

@app.route("/socket.io/<path:path>")
def run_socketio(path):
    socketio_manage(request.environ, {'/graph': GraphNamespace}, attributes)
    return ''

@app.route("/")
def login():
    return render_template("graphSAXS.html")

if __name__ == '__main__':
    print 'Listening on port 80 and on port 843 (flash policy server)'
    SocketIOServer(('0.0.0.0', 80), app).serve_forever()
