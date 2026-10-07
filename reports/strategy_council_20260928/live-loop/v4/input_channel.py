"""Persistent pixel-player input. No game probe, evaluator, or renderer state imports."""
import importlib.util
from pathlib import Path
import time

class GrpcInput:
    def __init__(self, port, proto_dir, discovery):
        import grpc
        spec = importlib.util.spec_from_file_location('v4_pb', Path(proto_dir)/'emulator_controller_pb2.py')
        self.pb = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.pb)
        settings = dict(line.strip().split('=',1) for line in Path(discovery).read_text().splitlines() if '=' in line)
        assert int(settings['grpc.port']) == port
        self.metadata = (('authorization', 'Bearer '+settings['grpc.token']),)
        self.channel = grpc.insecure_channel(f"127.0.0.1:{port}")
        self.rpc = self.channel.unary_unary('/android.emulation.control.EmulatorController/sendTouch',
            request_serializer=self.pb.TouchEvent.SerializeToString)

    def tap(self, x, y):
        for pressure in (1024, 0):
            self.rpc(self.pb.TouchEvent(touches=[self.pb.Touch(x=int(x), y=int(y), identifier=0, pressure=pressure)]), metadata=self.metadata, timeout=2)

    def play(self, slot, x, y, delay=0):
        start = time.perf_counter()
        self.tap([211,354,497,640][slot], 1749)
        if delay: time.sleep(delay)
        self.tap(round(111+x/18*856), round(436+y/32*1230))
        return (time.perf_counter()-start)*1000

    def close(self): self.channel.close()
