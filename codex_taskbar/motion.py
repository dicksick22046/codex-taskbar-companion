"""Short, critically damped transitions that can reverse without a value/velocity reset."""
import math
import time
from PySide6.QtCore import QObject,QTimer,Signal


def critical_step(value,velocity,target,seconds,response=.2):
    omega=6/response;offset=value-target;term=velocity+omega*offset;decay=math.exp(-omega*max(0,seconds))
    return target+(offset+term*seconds)*decay,(velocity-omega*term*seconds)*decay


class Spring(QObject):
    changed=Signal(float)
    finished=Signal()
    def __init__(self,parent=None,value=0.,response=.2):
        super().__init__(parent);self.value=float(value);self.velocity=0.;self.target=float(value);self.response=response
        self.last_time=time.monotonic();self.timer=QTimer(self);self.timer.setInterval(16);self.timer.timeout.connect(self.tick)
    def stop(self):self.timer.stop();self.velocity=0.
    def snap(self,value):
        self.stop();self.value=self.target=float(value);self.changed.emit(self.value)
    def retarget(self,target):
        target=float(target)
        if target==self.target and self.timer.isActive():return
        self.target=target;self.last_time=time.monotonic()
        if abs(self.value-target)<.001 and abs(self.velocity)<.04:
            self.snap(target);self.finished.emit()
        else:self.timer.start()
    def tick(self):
        now=time.monotonic();elapsed=now-self.last_time;self.last_time=now;self.advance(elapsed)
    def advance(self,elapsed):
        self.value,self.velocity=critical_step(self.value,self.velocity,self.target,max(0,elapsed),self.response)
        if abs(self.value-self.target)<.001 and abs(self.velocity)<.04:
            self.snap(self.target);self.finished.emit()
        else:self.changed.emit(self.value)
