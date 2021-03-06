
import requests
from websocket import create_connection
import time
from .color_print import color_print
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
import json
import dill
import os
from tqdm import tqdm
from .dummies import import_all, unimport_all

class ServerConnector():

    def __init__(self, username, instanceType):  
        self.GPU_SERVER_PORT = '8000'
        self.username = username
        self.type = instanceType
        if instanceType == 'local':
            self.CATALEARN_URL = 'localhost'
        else:
            self.CATALEARN_URL = 'catalearn.com'


    def contact_server(self):

        color_print("Starting server, this will take about 10 seconds")
        r = requests.post('http://{}/api/computeRequest'.format(self.CATALEARN_URL), 
        data={'username' : self.username,
                'type' : self.type})
        res = r.json()
        if 'err' in res:
            color_print(res['err'])
            return (None, None, None)
        else:
            gpu_hash = res['hash']
            gpu_ip = res['ip']
            ws_port = res['ws_port']
            return (gpu_hash, gpu_ip, ws_port)


    def upload_params_decorator(self, gpu_ip, job_hash):
        url = 'http://{}:{}/uploadDecorator'.format(gpu_ip, self.GPU_SERVER_PORT, job_hash)
        self.upload_params(url, job_hash)


    def upload_params_magic(self, gpu_ip, job_hash):
        url = 'http://{}:{}/uploadMagic'.format(gpu_ip, self.GPU_SERVER_PORT, job_hash)
        self.upload_params(url, job_hash)
 

    def upload_params(self, url, job_hash):
        color_print("Uploading data")
        time.sleep(0.5)
        file_size = os.path.getsize('uploads.pkl')

        pbar = tqdm(total=file_size, unit='B', unit_scale=True)
        
        def callback(monitor):

            progress = monitor.bytes_read - callback.last_bytes_read
            pbar.update(progress)
            callback.last_bytes_read = monitor.bytes_read
        callback.last_bytes_read = 0

        with open('uploads.pkl', 'rb') as pickle_file:
            encoder = MultipartEncoder(
                {
                    'file': ('uploads.pkl', pickle_file),
                    'hash': job_hash
                }
            )
            monitor = MultipartEncoderMonitor(encoder, callback)
            r = requests.post(url, data=monitor, headers={'Content-Type': monitor.content_type})
            pbar.close()

    def stream_output(self, gpu_ip, gpu_hash, ws_port):

        gpuUrl = 'ws://{}:{}'.format(gpu_ip, ws_port)

        ws = create_connection(gpuUrl)

        outUrl = None
        ws.send(gpu_hash)
        while True:
            message = ws.recv()
            msgJson = json.loads(message)
            if 'end' in msgJson:
                if 'error' in msgJson: 
                    outUrl = None
                else:
                    outUrl = msgJson['outUrl']
                ws.close()
                break
            else:
                print(msgJson['message'], end='')
        return outUrl    


    def get_return_object(self, outUrl):

        color_print("Downloading result")

        r = requests.get(outUrl, stream=True)
        total_size = int(r.headers.get('content-length', 0)); 
        with open('return.pkl', 'wb') as f:
            pbar = tqdm(total=total_size, unit='B', unit_scale=True)
            chunck_size = 32768
            for data in r.iter_content(chunck_size):
                f.write(data)
                pbar.update(chunck_size)
            pbar.close()

        with open('return.pkl', "rb" ) as f:

            import_all() # Hack: a workaround for dill's pickling problem
            result = dill.load(f)['return_env']  
            unimport_all()
            if result is None:
                color_print('Computation failed')
            color_print("Done!")
            return result