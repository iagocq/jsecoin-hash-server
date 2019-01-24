import queue
import socket
import struct
import sys
import threading

from flask import Flask
from flask_restful import Api, Resource

app = Flask(__name__)
api = Api(app)

prehash_queue = queue.Queue()
current_prehash = ''
hash_queue = queue.Queue()
auth = ''
threads = []

class UpdatePrehash(Resource):
    def get(self, prehash, start_nonce, difficulty, authorization):
        global current_prehash
        if authorization == auth:
            if len(prehash) != 64:
                return {'result': 'prehash_fail'}
            while True:
                try:
                    hash_queue.get_nowait()
                except queue.Empty:
                    break
            current_prehash = prehash
            prehash_queue.put((prehash, start_nonce, difficulty))
            print(prehash_queue.qsize())
            return {'result': 'ok'}
        return {'result': 'auth_fail'}

class GetHash(Resource):
    def get(self):
        if not hash_queue.empty():
            prehash, nonce = hash_queue.get()
            return {'prehash': prehash, 'nonce': str(nonce)}
        else:
            return {'prehash': '', 'nonce': '-1'}

def usage(argv):
    print(f'Usage: {argv[0]} <host> <port> <auth>')

def main():
    global auth

    if len(sys.argv) < 4:
        usage(sys.argv)
        exit(0)

    host, port, auth = sys.argv[1:4]

    sock = socket.socket()
    sock.connect((host, int(port)))

    api.add_resource(UpdatePrehash, '/<string:prehash>/<int:start_nonce>/<int:difficulty>/<string:authorization>')
    api.add_resource(GetHash, '/')

    threads.append(threading.Thread(target=send_worker, args=(sock,)))
    threads.append(threading.Thread(target=recv_worker, args=(sock,)))

    for thread in threads:
        thread.start()

    app.run(debug=False)

def send_worker(sock):
    while True:
        prehash, start_nonce, difficulty = prehash_queue.get()
        difficulty_mask = 0
        for i in range(difficulty):
            difficulty_mask |= 0xF << (28 - i * 4)
        packed = struct.pack('!IQ64s', difficulty_mask, start_nonce, prehash.encode())
        print(packed)
        sock.send(packed)

def recv_worker(sock):
    buf = b''
    while True:
        buf += sock.recv(72)
        while len(buf) >= 72:
            data = buf[:72]
            buf = buf[72:]
            prehash, nonce = struct.unpack('!64sQ', data)
            prehash = prehash.decode()
            if prehash == current_prehash:
                print(prehash, nonce)
                hash_queue.put((prehash, nonce))

if __name__ == '__main__':
    main()
